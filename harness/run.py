"""
Main entry point for the ZeptoCode prompt optimization harness.
Runs a single baseline evaluation pass for each scenario in the manifest.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import dspy

# Ensure harness/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT, RESULTS_DIR, HARNESS_DIR
from module import ZeptocodeModule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_manifest(manifest_path: Path) -> list[dict]:
    """Load and return the list of scenarios from manifest.yaml."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    return manifest.get("scenarios", [])


def save_result(scenario_name: str, scenario_type: str, score: float, feedback: str) -> Path:
    """Save evaluation result to harness/results/<scenario-name>.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "scenario": scenario_name,
        "type": scenario_type,
        "score": score,
        "feedback": feedback,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out_path = RESULTS_DIR / f"{scenario_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Result saved to {out_path}")
    return out_path


def main() -> None:
    # ── Configure DSPy global LM (gemma4:4b via llama.cpp at port 8000) ─────
    ollama_lm = dspy.LM(
        "ollama_chat/gemma4:4b",
        api_base="http://localhost:8000/v1",
        api_key="",
    )
    dspy.configure(lm=ollama_lm)
    logger.info(f"DSPy global LM configured: {dspy.settings.lm}")

    # ── Claude Sonnet as GEPA reflection LM (not used in single-pass mode) ───
    # Kept here for future gepa.compile() use.
    reflection_lm = dspy.LM(  # noqa: F841
        "anthropic/claude-sonnet-4-5-20250929",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    # ── Load scenarios from manifest ─────────────────────────────────────────
    manifest_path = HARNESS_DIR / "manifest.yaml"
    scenarios = load_manifest(manifest_path)
    logger.info(f"Loaded {len(scenarios)} scenario(s) from {manifest_path}")

    # ── GEPA (future use — not called for single-pass baseline) ──────────────
    # gepa = dspy.GEPA(metric=metric_fn, reflection_lm=reflection_lm, max_full_evals=1, auto='light')
    # gepa.compile(student=module, trainset=trainset, valset=trainset)

    results = []

    for scenario in scenarios:
        name = scenario["name"]
        stype = scenario["type"]
        kickoff_command = scenario.get("command")
        kickoff_arguments = scenario.get("arguments", "")

        if not kickoff_command:
            logger.warning(f"No command defined for scenario '{name}' in manifest — skipping")
            continue

        logger.info(f"─── Running scenario: {name} (type={stype}) ───")

        module = ZeptocodeModule(
            repo_root=REPO_ROOT,
            scenario_name=name,
            scenario_type=stype,
            kickoff_command=kickoff_command,
            kickoff_arguments=kickoff_arguments,
        )

        try:
            prediction = module.forward()
            score = float(prediction.score)
            feedback = str(prediction.feedback)
        except Exception as e:
            logger.error(f"Scenario {name} failed: {e}")
            score = 0.0
            feedback = f"Harness error: {str(e)}"

        out_path = save_result(name, stype, score, feedback)
        results.append({"scenario": name, "type": stype, "score": score, "result_path": str(out_path)})
        logger.info(f"Scenario {name}: score={score:.3f}")

    logger.info("═══ Evaluation Complete ═══")
    for r in results:
        logger.info(f"  {r['scenario']} ({r['type']}): score={r['score']:.3f} → {r['result_path']}")


if __name__ == "__main__":
    main()
