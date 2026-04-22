"""
Full GEPA optimization loop for a single ZeptoCode scenario.

Usage:
    cd /home/jack/ZeptoCode/harness
    pixi run python optimize.py --scenario cpp-demo-fmt-argparse-extension

GEPA will run the scenario repeatedly, mutating the prompt surface derived
from the scenario's phase-plan.toml, until convergence or until interrupted.
Optimized prompts are written back to files/ and synced to OpenCode config.
Results are saved to harness/results/<scenario>-optimized.json.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import dspy

sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT, RESULTS_DIR, HARNESS_DIR
from module import ZeptocodeModule, SCENARIO_PROJECT_DIR, prompt_surface_for_plan
from judge import score_execution_run, score_planning_run
import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_manifest(manifest_path: Path) -> list[dict]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("scenarios", [])


def build_metric(scenario_type: str, scenario_name: str):
    """
    Return a GEPA-compatible metric function for the given scenario type.

    The metric receives (gold, pred, trace=None) where:
    - gold is a dspy.Example (unused — we don't have gold labels)
    - pred is the dspy.Prediction returned by ZeptocodeModule.forward()

    Returns the score float directly so GEPA can optimise toward 1.0.
    """
    def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        score = getattr(pred, "score", 0.0)
        feedback = getattr(pred, "feedback", "")
        logger.info(f"[metric] {scenario_name}: score={score:.3f}  feedback={feedback[:120]}")
        return float(score)

    return metric


def main():
    parser = argparse.ArgumentParser(description="Run full GEPA optimization for a scenario")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario name as declared in manifest.yaml (e.g. cpp-demo-fmt-argparse-extension)",
    )
    args = parser.parse_args()

    # ── Load scenario from manifest ──────────────────────────────────────────
    scenarios = load_manifest(HARNESS_DIR / "manifest.yaml")
    scenario = next((s for s in scenarios if s["name"] == args.scenario), None)
    if scenario is None:
        logger.error(f"Scenario '{args.scenario}' not found in manifest.yaml")
        sys.exit(1)

    name = scenario["name"]
    stype = scenario["type"]
    kickoff_command = scenario["command"]
    kickoff_arguments = scenario["arguments"]

    phase_plan_toml = (
        SCENARIO_PROJECT_DIR / ".opencode" / "session-plans" / name / "phase-plan.toml"
    )
    if not phase_plan_toml.exists():
        logger.error(f"phase-plan.toml not found: {phase_plan_toml}")
        sys.exit(1)

    logger.info(f"Optimizing scenario: {name} (type={stype})")

    # ── Configure DSPy ───────────────────────────────────────────────────────
    ollama_lm = dspy.LM(
        "ollama_chat/gemma4:4b",
        api_base="http://localhost:8000/v1",
        api_key="",
    )
    dspy.configure(lm=ollama_lm)

    reflection_lm = dspy.LM(
        "anthropic/claude-sonnet-4-5-20250929",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    # ── Build module ─────────────────────────────────────────────────────────
    module = ZeptocodeModule(
        repo_root=REPO_ROOT,
        scenario_name=name,
        scenario_type=stype,
        kickoff_command=kickoff_command,
        kickoff_arguments=kickoff_arguments,
        phase_plan_toml=phase_plan_toml,
    )

    surface = prompt_surface_for_plan(phase_plan_toml, REPO_ROOT)
    logger.info(f"Prompt surface: {len(surface)} files will be optimized")

    # ── Build trainset ───────────────────────────────────────────────────────
    # GEPA needs at least 2 examples. We have one scenario, so we use the same
    # example twice (GEPA uses the trainset to propose diverse candidates, not
    # as gold labels — duplication is harmless and documented as acceptable).
    example = dspy.Example(
        scenario_name=name,
        scenario_type=stype,
    ).with_inputs("scenario_name", "scenario_type")
    trainset = [example, example]

    # ── GEPA metric ──────────────────────────────────────────────────────────
    metric = build_metric(stype, name)

    # ── Run GEPA ─────────────────────────────────────────────────────────────
    gepa = dspy.GEPA(
        metric=metric,
        reflection_lm=reflection_lm,
        max_full_evals=2,
        num_threads=1,           # one at a time — single OpenCode server
        seed=42,
    )

    logger.info("Starting GEPA optimization — this will run until convergence")
    logger.info("Each iteration = one full OpenCode session (~minutes per run)")

    optimized = gepa.compile(
        student=module,
        trainset=trainset,
        valset=trainset,
    )

    # ── Save optimized prompts back to files/ ─────────────────────────────────
    # The optimized module's Predict instructions now hold the best-found prompts.
    # Write them back to the repo so they're preserved and can be committed.
    logger.info("Writing optimized prompts back to files/")
    for attr_name, rel_path in optimized._predict_keys.items():
        predict: dspy.Predict = getattr(optimized, attr_name)
        new_body = predict.signature.instructions
        file_path = REPO_ROOT / rel_path
        try:
            content = file_path.read_text(encoding="utf-8")
            import re
            fm_re = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*?)$", re.DOTALL)
            m = fm_re.match(content)
            updated = f"---\n{m.group(1)}\n---\n{new_body}" if m else new_body
            file_path.write_text(updated, encoding="utf-8")
            logger.debug(f"Saved optimized prompt: {rel_path}")
        except Exception as e:
            logger.warning(f"Failed to save optimized prompt {rel_path}: {e}")

    # ── Save result summary ───────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "scenario": name,
        "type": stype,
        "prompt_files_optimized": len(surface),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out_path = RESULTS_DIR / f"{name}-optimized.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Optimization complete. Summary saved to {out_path}")
    logger.info(f"Optimized prompts written to files/ — review and commit when satisfied")


if __name__ == "__main__":
    main()
