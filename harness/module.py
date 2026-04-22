"""
ZeptoCode DSPy Module — wraps OpenCode session execution as a dspy.Module.
"""
import logging
import os
import re
import subprocess
from pathlib import Path

import anthropic
import dspy

import tomllib

from config import REPO_ROOT, RESULTS_DIR, OPTIMIZATION_EXCLUDED_AGENTS
from opencode_client import OpenCodeClient
from judge import score_execution_run, score_planning_run

logger = logging.getLogger(__name__)

# Scenario project directory (all harness runs target this project)
SCENARIO_PROJECT_DIR = REPO_ROOT / "optimization-scenarios" / "cpp-greenfield-project"

# Frontmatter regex — splits at second '---' delimiter
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*?)$", re.DOTALL)

# Node-library root
_NODE_LIB = REPO_ROOT / "files" / "planning" / "plan-session" / "node-library"

# Agent files root
_AGENTS_DIR = REPO_ROOT / "files" / "agents"


def prompt_surface_for_plan(phase_plan_toml: Path, repo_root: Path) -> dict[str, str]:
    """
    Parse a phase-plan.toml and return a mapping of {repo-relative-path: current-body}
    for every prompt file that this plan actually uses.

    The surface includes:
    - All agent .md files (bodies only — always relevant regardless of phase types)
    - All prompt.md files under node-library/<phase-type>/ for each unique phase type
      present in the TOML

    This means the surface expands and contracts automatically as plans are updated —
    no hardcoded file lists anywhere.

    Args:
        phase_plan_toml: Absolute path to the scenario's phase-plan.toml
        repo_root: Absolute path to the ZeptoCode repo root

    Returns:
        dict mapping repo-relative path strings to the current body text of each file
        (i.e. everything after the second '---' frontmatter delimiter, or the full
        content if no frontmatter is present)
    """
    with open(phase_plan_toml, "rb") as f:
        plan = tomllib.load(f)

    # Collect unique phase types from the plan
    phase_types = {phase["type"] for phase in plan.get("phases", []) if "type" in phase}
    logger.debug(f"Phase types in plan: {phase_types}")

    surface: dict[str, str] = {}
    node_lib = repo_root / "files" / "planning" / "plan-session" / "node-library"
    agents_dir = repo_root / "files" / "agents"

    # 1. Agent .md files (excluding agents not yet wired into the DAG system)
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name in OPTIMIZATION_EXCLUDED_AGENTS:
            logger.debug(f"Skipping excluded agent: {agent_file.name}")
            continue
        rel = str(agent_file.relative_to(repo_root))
        body = _extract_body(agent_file)
        if body is not None:
            surface[rel] = body

    # 2. All prompt.md files under each used phase type directory
    for phase_type in sorted(phase_types):
        type_dir = node_lib / phase_type
        if not type_dir.exists():
            logger.warning(f"No node-library directory for phase type '{phase_type}' — skipping")
            continue
        for prompt_file in sorted(type_dir.rglob("prompt.md")):
            rel = str(prompt_file.relative_to(repo_root))
            body = _extract_body(prompt_file)
            if body is not None:
                surface[rel] = body

    logger.info(
        f"Prompt surface: {len(surface)} files "
        f"({len([k for k in surface if 'agents' in k])} agents, "
        f"{len([k for k in surface if 'node-library' in k])} node prompts)"
    )
    return surface


def _extract_body(path: Path) -> str | None:
    """
    Read a .md file and return only the body — everything after the second '---'.
    Returns the full content if no frontmatter is found.
    Returns None on read error.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        return None
    m = _FM_RE.match(content)
    return m.group(2) if m else content


class ZeptocodeModule(dspy.Module):
    """
    DSPy Module wrapping a ZeptoCode DAG scenario execution as a black-box forward pass.

    At construction time, reads the scenario's phase-plan.toml to determine which
    prompt files are actually used by the plan, then registers one dspy.Predict per
    file. GEPA mutates the .instructions on those Predict instances; forward() reads
    them back out, writes the mutations to disk, and runs the full OpenCode session.

    Each forward() call:
      1. Harvests current Predict instructions → writes to prompt files
      2. Syncs prompt files to OpenCode config
      3. Starts OpenCode server (cwd = scenario project dir)
      4. Creates session + fires slash command via /command endpoint
      5. Streams SSE events until idle/error/timeout
      6. Scores transcript via appropriate judge
      7. Cleans up (delete session, stop server, git restore)
      8. Returns dspy.Prediction(score, feedback)
    """

    def __init__(
        self,
        repo_root: Path,
        scenario_name: str,
        scenario_type: str,
        kickoff_command: str,
        kickoff_arguments: str,
        phase_plan_toml: Path,
    ):
        """
        Args:
            repo_root: ZeptoCode git repo root
            scenario_name: Scenario name matching manifest.yaml entry
            scenario_type: "execution" or "planning"
            kickoff_command: Slash command name without leading slash
            kickoff_arguments: Command arguments string
            phase_plan_toml: Path to the scenario's phase-plan.toml (determines prompt surface)
        """
        super().__init__()
        self.repo_root = Path(repo_root)
        self.scenario_name = scenario_name
        self.scenario_type = scenario_type
        self.kickoff_command = kickoff_command
        self.kickoff_arguments = kickoff_arguments
        self.client = OpenCodeClient(
            repo_root=self.repo_root,
            scenario_dir=SCENARIO_PROJECT_DIR,
        )
        self.anthropic_client = anthropic.Anthropic()
        self.reference_transcript_path = (
            SCENARIO_PROJECT_DIR
            / ".opencode"
            / "session-plans"
            / "tui-widget-library-cpp"
            / "sonnet-planning-transcript.md"
        )

        # Build prompt surface from phase-plan.toml and register one Predict per file.
        # The repo-relative path is stored as the Predict's signature field name
        # (with slashes replaced by underscores to form a valid Python identifier).
        # GEPA mutates .instructions on these; forward() reads them back.
        self._prompt_surface = prompt_surface_for_plan(phase_plan_toml, self.repo_root)
        self._predict_keys: dict[str, str] = {}  # attr_name → repo-relative path

        for rel_path, body in self._prompt_surface.items():
            attr_name = rel_path.replace("/", "__").replace(".", "_")
            self._predict_keys[attr_name] = rel_path
            # Create a Predict with a minimal signature; instructions holds the prompt body
            sig = dspy.Signature(
                f"context -> response",
                instructions=body,
            )
            setattr(self, attr_name, dspy.Predict(sig))

    def _collect_mutations(self) -> dict[str, str]:
        """
        Read current .instructions from each registered Predict and return a
        {repo-relative-path: new_body} dict ready for _write_and_sync_prompts.
        """
        mutations = {}
        for attr_name, rel_path in self._predict_keys.items():
            predict: dspy.Predict = getattr(self, attr_name)
            mutations[rel_path] = predict.signature.instructions
        return mutations

    def _write_and_sync_prompts(self, mutations: dict[str, str]) -> None:
        """
        Write mutated prompt bodies to repo files (preserving YAML frontmatter),
        then sync to OpenCode config directories synchronously before server launch.
        """
        for rel_path, new_body in mutations.items():
            file_path = self.repo_root / rel_path
            try:
                content = file_path.read_text(encoding="utf-8")
                m = _FM_RE.match(content)
                updated = f"---\n{m.group(1)}\n---\n{new_body}" if m else new_body
                file_path.write_text(updated, encoding="utf-8")
                logger.debug(f"Wrote mutation to {rel_path}")
            except Exception as e:
                logger.warning(f"Failed to write mutation to {rel_path}: {e}")

        # Sync files/planning → ~/.config/opencode/planning
        subprocess.run(
            ["cp", "-r",
             str(self.repo_root / "files" / "planning"),
             os.path.expanduser("~/.config/opencode/planning")],
            check=True, timeout=30,
        )
        # Sync files/agents → ~/.config/opencode/profiles/naga-ollama/agents
        subprocess.run(
            ["cp", "-r",
             str(self.repo_root / "files" / "agents"),
             os.path.expanduser("~/.config/opencode/profiles/naga-ollama/agents")],
            check=True, timeout=30,
        )
        logger.info("Prompt sync complete")

    def forward(self, **kwargs) -> dspy.Prediction:
        """
        Run one complete scenario evaluation pass.

        GEPA calls forward() after mutating .instructions on the registered Predicts.
        We harvest those instructions, write them to disk, run the session, and score.

        Returns:
            dspy.Prediction(score=float [0.0, 1.0], feedback=str)
        """
        # Harvest current instructions from all Predicts → write to disk
        mutations = self._collect_mutations()
        self._write_and_sync_prompts(mutations)

        # Run the OpenCode session
        try:
            transcript = self.client.run_scenario_session(
                scenario_name=self.scenario_name,
                kickoff_command=self.kickoff_command,
                kickoff_arguments=self.kickoff_arguments,
            )
        except Exception as e:
            logger.error(f"Scenario session failed for {self.scenario_name}: {e}")
            return dspy.Prediction(score=0.0, feedback=f"Session error: {str(e)}")

        # Score via appropriate judge
        try:
            if self.scenario_type == "execution":
                return score_execution_run(
                    transcript=transcript,
                    anthropic_client=self.anthropic_client,
                )
            else:
                return score_planning_run(
                    candidate_plan=transcript,
                    reference_transcript_path=self.reference_transcript_path,
                    anthropic_client=self.anthropic_client,
                )
        except Exception as e:
            logger.error(f"Judge failed for {self.scenario_name}: {e}")
            return dspy.Prediction(score=0.0, feedback=f"Judge error: {str(e)}")
