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

from config import REPO_ROOT, RESULTS_DIR
from opencode_client import OpenCodeClient
from judge import score_execution_run, score_planning_run

logger = logging.getLogger(__name__)

# Scenario project directory (all harness runs target this project)
SCENARIO_PROJECT_DIR = REPO_ROOT / "optimization-scenarios" / "cpp-greenfield-project"

# TUI planning prompt body — sent as arguments to /plan-session command
TUI_PLAN_SESSION_ARGUMENTS = (
    "I want to add a TUI component library to the cpp-demo-project (C++, CMake, Pixi, C++23). "
    "The library should support 3-4 distinct widget types, each with different rendering requirements: "
    "a text label, a progress bar, a table, and an interactive input box.\n\n"
    "I want to be involved in choosing which widgets to prioritize and what the rendering approach "
    "should be for each — there are real tradeoffs here (stateful vs stateless rendering, ANSI escape "
    "codes vs a terminal library, shared rendering primitives vs per-widget rendering, color support vs "
    "monochrome). Different widget types may warrant different approaches and should be explored "
    "independently.\n\n"
    "Hard constraints:\n"
    "- The plan must use a collaborate phase to involve me in widget selection and rendering approach "
    "decisions before implementation begins.\n"
    "- Widget types that share rendering primitives should be planned with a merge point back to a "
    "shared implementation phase; widget types with independent rendering should remain on separate "
    "branches through to completion.\n"
    "- Each widget implementation branch should be broken into sequential phases: "
    "research/deliberate -> implement -> verify -> document.\n"
    "- Nested deliberation is expected: top-level decisions about shared architecture, then per-widget "
    "decisions about rendering specifics.\n"
    "- Some branches should merge (shared interface/base class), others should not "
    "(widget-specific rendering logic).\n"
    "- The plan must be as structurally complex as the task warrants — do not simplify the DAG "
    "topology to make it easier to generate. If the task naturally requires nested branches, "
    "asymmetric merges, or multiple collaborate phases, include them.\n"
    "- Pixi for all package management; CPM for any GitHub-only dependencies."
)

# Frontmatter regex — splits at second '---' delimiter
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*?)$", re.DOTALL)


class ZeptocodeModule(dspy.Module):
    """
    DSPy Module wrapping a ZeptoCode DAG scenario execution as a black-box forward pass.

    Each forward() call:
      1. (Optional) Writes prompt mutations to repo files, preserving YAML frontmatter
      2. Syncs prompt files to OpenCode config
      3. Starts OpenCode server (cwd = scenario project dir)
      4. Creates session scoped to scenario dir + fires slash command via /command endpoint
      5. Streams SSE events until idle/error/timeout
      6. Scores transcript via appropriate judge (execution or planning)
      7. Cleans up (delete session, stop server, git reset)
      8. Returns dspy.Prediction(score, feedback)
    """

    def __init__(
        self,
        repo_root: Path,
        scenario_name: str,
        scenario_type: str,
        kickoff_command: str,
        kickoff_arguments: str,
    ):
        """
        Args:
            repo_root: ZeptoCode git repo root (used for git reset)
            scenario_name: Scenario name matching manifest.yaml entry
            scenario_type: "execution" or "planning"
            kickoff_command: Slash command without leading slash (e.g. "activate-plan")
            kickoff_arguments: Command arguments (e.g. "cpp-demo-fmt-argparse-extension")
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

    def _write_and_sync_prompts(self, candidate_instructions: dict[str, str]) -> None:
        """
        Write mutated prompt bodies to repo files (preserving YAML frontmatter),
        then sync to OpenCode config directories synchronously before server launch.

        Args:
            candidate_instructions: {repo-relative path: new_body_text}
        """
        for rel_path, new_body in candidate_instructions.items():
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
            ["cp", "-r", str(self.repo_root / "files" / "planning"),
             os.path.expanduser("~/.config/opencode/planning")],
            check=True, timeout=30,
        )
        # Sync files/agents → ~/.config/opencode/profiles/naga-ollama/agents
        subprocess.run(
            ["cp", "-r", str(self.repo_root / "files" / "agents"),
             os.path.expanduser("~/.config/opencode/profiles/naga-ollama/agents")],
            check=True, timeout=30,
        )
        logger.info("Prompt sync complete")

    def forward(
        self,
        scenario_name: str = None,
        prompt_mutations: dict = None,
    ) -> dspy.Prediction:
        """
        Run one complete scenario evaluation pass.

        For baseline single-pass (no mutations):
            module.forward()

        For GEPA-driven mutation (future use):
            module.forward(prompt_mutations={"files/agents/headwrench.md": new_body})

        Returns:
            dspy.Prediction(score=float [0.0, 1.0], feedback=str)
        """
        # Write mutations and sync (always sync even on baseline pass)
        self._write_and_sync_prompts(prompt_mutations or {})

        # Run the session
        try:
            transcript = self.client.run_scenario_session(
                scenario_name=self.scenario_name,
                kickoff_command=self.kickoff_command,
                kickoff_arguments=self.kickoff_arguments,
            )
        except Exception as e:
            logger.error(f"Scenario session failed for {self.scenario_name}: {e}")
            return dspy.Prediction(score=0.0, feedback=f"Session error: {str(e)}")

        # Score
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
