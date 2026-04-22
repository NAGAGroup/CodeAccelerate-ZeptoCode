"""
ZeptoCode DSPy Module — wraps OpenCode session execution as a dspy.Module.
Implements the 11-step per-candidate run sequence.
"""
import json
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

# Full TUI planning kickoff message (from docs/prompt-optimization/planning-dag-spec.md §7)
TUI_KICKOFF_MESSAGE = """/plan-session I want to add a TUI component library to the cpp-demo-project (C++, CMake, Pixi, C++23). The library should support 3-4 distinct widget types, each with different rendering requirements: a text label, a progress bar, a table, and an interactive input box.

I want to be involved in choosing which widgets to prioritize and what the rendering approach should be for each — there are real tradeoffs here (stateful vs stateless rendering, ANSI escape codes vs a terminal library, shared rendering primitives vs per-widget rendering, color support vs monochrome). Different widget types may warrant different approaches and should be explored independently.

Hard constraints:
- The plan must use a collaborate phase to involve me in widget selection and rendering approach decisions before implementation begins.
- Widget types that share rendering primitives should be planned with a merge point back to a shared implementation phase; widget types with independent rendering should remain on separate branches through to completion.
- Each widget implementation branch should be broken into sequential phases: research/deliberate -> implement -> verify -> document.
- Nested deliberation is expected: top-level decisions about shared architecture, then per-widget decisions about rendering specifics.
- Some branches should merge (shared interface/base class), others should not (widget-specific rendering logic).
- The plan must be as structurally complex as the task warrants — do not simplify the DAG topology to make it easier to generate. If the task naturally requires nested branches, asymmetric merges, or multiple collaborate phases, include them.
- Pixi for all package management; CPM for any GitHub-only dependencies."""

# Frontmatter regex — splits at second '---' delimiter
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*?)$", re.DOTALL)


class ZeptocodeModule(dspy.Module):
    """
    DSPy Module that wraps a ZeptoCode DAG scenario execution as a black-box forward pass.
    For each forward() call, runs the full per-candidate sequence:
      1. (Optional) Write prompt mutations
      2. Sync prompt files to OpenCode config
      3. Start OpenCode server
      4. Create session + send kickoff message
      5. Wait for completion via SSE/polling
      6. Extract transcript
      7. Score via appropriate judge
      8. Cleanup (delete session, stop server, git reset)
      9. Return dspy.Prediction(score, feedback)
    """

    def __init__(
        self,
        repo_root: Path,
        scenario_name: str,
        scenario_type: str,
        kickoff_message: str,
    ):
        super().__init__()
        self.repo_root = Path(repo_root)
        self.scenario_name = scenario_name
        self.scenario_type = scenario_type
        self.kickoff_message = kickoff_message
        self.client = OpenCodeClient(repo_root=self.repo_root)
        self.anthropic_client = anthropic.Anthropic()
        self.reference_transcript_path = (
            self.repo_root
            / "optimization-scenarios"
            / "cpp-greenfield-project"
            / ".opencode"
            / "session-plans"
            / "tui-widget-library-cpp"
            / "sonnet-planning-transcript.md"
        )

    def _write_and_sync_prompts(self, candidate_instructions: dict[str, str]) -> None:
        """
        Write mutated prompt bodies to repo files (preserving YAML frontmatter),
        then sync to OpenCode config directories synchronously.

        Args:
            candidate_instructions: {relative_file_path: new_body_text}
                Paths are relative to repo_root. Only the body after second '---' is replaced.
        """
        for rel_path, new_body in candidate_instructions.items():
            file_path = self.repo_root / rel_path
            try:
                content = file_path.read_text(encoding="utf-8")
                m = _FM_RE.match(content)
                if m:
                    # Preserve frontmatter exactly; replace only body
                    updated = f"---\n{m.group(1)}\n---\n{new_body}"
                else:
                    # No frontmatter — replace entire file content
                    updated = new_body
                file_path.write_text(updated, encoding="utf-8")
                logger.debug(f"Wrote mutation to {rel_path}")
            except Exception as e:
                logger.warning(f"Failed to write mutation to {rel_path}: {e}")

        # Sync files/planning/* → ~/.config/opencode/planning (synchronous)
        planning_src = str(self.repo_root / "files" / "planning")
        planning_dst = os.path.expanduser("~/.config/opencode/planning")
        subprocess.run(
            ["cp", "-r", planning_src, planning_dst],
            cwd=str(self.repo_root),
            check=True,
            timeout=30,
        )

        # Sync files/agents/* → ~/.config/opencode/profiles/naga-ollama/agents (synchronous)
        agents_src = str(self.repo_root / "files" / "agents")
        agents_dst = os.path.expanduser("~/.config/opencode/profiles/naga-ollama/agents")
        subprocess.run(
            ["cp", "-r", agents_src, agents_dst],
            cwd=str(self.repo_root),
            check=True,
            timeout=30,
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
            module.forward()  # uses stored kickoff_message; no prompt mutations applied

        For GEPA-driven optimization (future use):
            module.forward(prompt_mutations={"files/agents/headwrench.md": new_body})

        Returns:
            dspy.Prediction(score=float [0.0, 1.0], feedback=str)
        """
        # Step 1-3: Write and sync prompt mutations if provided
        if prompt_mutations:
            self._write_and_sync_prompts(prompt_mutations)
        else:
            # Baseline pass: still sync current files to OpenCode config
            self._write_and_sync_prompts({})

        # Steps 4-8: Run the scenario session (start server, session, kickoff, wait, cleanup, reset)
        try:
            transcript = self.client.run_scenario_session(
                scenario_name=self.scenario_name,
                kickoff_message=self.kickoff_message,
            )
        except Exception as e:
            logger.error(f"Scenario session failed for {self.scenario_name}: {e}")
            return dspy.Prediction(score=0.0, feedback=f"Session error: {str(e)}")

        # Step 9: Score via appropriate judge
        try:
            if self.scenario_type == "execution":
                prediction = score_execution_run(
                    transcript=transcript,
                    anthropic_client=self.anthropic_client,
                )
            else:
                # Planning scenario — pass candidate plan (transcript) to planning judge
                prediction = score_planning_run(
                    candidate_plan=transcript,
                    reference_transcript_path=self.reference_transcript_path,
                    anthropic_client=self.anthropic_client,
                )
        except Exception as e:
            logger.error(f"Judge failed for {self.scenario_name}: {e}")
            return dspy.Prediction(score=0.0, feedback=f"Judge error: {str(e)}")

        return prediction
