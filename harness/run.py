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

from config import REPO_ROOT, SCENARIOS_DIR, RESULTS_DIR
from module import ZeptocodeModule, TUI_KICKOFF_MESSAGE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Kickoff messages per scenario name ──────────────────────────────────────
KICKOFF_MESSAGES = {
    "cpp-demo-fmt-argparse-extension": "/activate-plan cpp-demo-fmt-argparse-extension",
    "tui-widget-library-cpp": TUI_KICKOFF_MESSAGE,
}


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
    # ── Configure DSPy global LM (gemma4:4b via llama.cpp at port 8000) ───
    ollama_lm = dspy.LM(
        "ollama_chat/gemma4:4b",
        api_base="http://localhost:8000/v1",
        api_key="",
    )
    dspy.configure(lm=ollama_lm)
    logger.info(f"DSPy global LM configured: {dspy.settings.lm}")

    # ── Claude Sonnet as GEPA reflection LM (not used in single-pass mode) ─
    reflection_lm = dspy.LM(
        "anthropic/claude-sonnet-4-5-20250929",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    # ── Load scenarios from manifest ────────────────────────────────────────
    manifest_path = SCENARIOS_DIR / "cpp-greenfield-project" / "manifest.yaml"
    scenarios = load_manifest(manifest_path)
    logger.info(f"Loaded {len(scenarios)} scenario(s) from {manifest_path}")

    # ── GEPA instantiation (for documentation/future use — NOT called here) ─
    # To run full optimization in future, replace forward() calls below with:
    #   gepa = dspy.GEPA(metric=metric_fn, reflection_lm=reflection_lm, max_full_evals=1, auto='light')
    #   gepa.compile(student=module, trainset=trainset, valset=trainset)
    # For now: single-pass baseline evaluation only.

    results = []

    for scenario in scenarios:
        name = scenario["name"]
        stype = scenario["type"]
        kickoff = KICKOFF_MESSAGES.get(name)

        if kickoff is None:
            logger.warning(f"No kickoff message defined for scenario '{name}' — skipping")
            continue

        logger.info(f"─── Running scenario: {name} (type={stype}) ───")

        module = ZeptocodeModule(
            repo_root=REPO_ROOT,
            scenario_name=name,
            scenario_type=stype,
            kickoff_message=kickoff,
        )

        # Single baseline forward pass (no mutations — evaluates current prompts as-is)
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

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("═══ Evaluation Complete ═══")
    for r in results:
        logger.info(f"  {r['scenario']} ({r['type']}): score={r['score']:.3f} → {r['result_path']}")


if __name__ == "__main__":
    main()
