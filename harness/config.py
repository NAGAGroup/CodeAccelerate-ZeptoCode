"""
Constants for the ZeptoCode prompt optimization harness.
"""
from pathlib import Path

# Repo root is two levels up from this file (harness/config.py → harness/ → repo root)
REPO_ROOT = Path(__file__).parent.parent

# Harness directory
HARNESS_DIR = Path(__file__).parent

# Scenario project directory
SCENARIOS_DIR = REPO_ROOT / "optimization-scenarios"

# OpenCode server configuration
OPENCODE_PORT = 4096
OPENCODE_OLLAMA_PORT = 8000

# Timeout for waiting on OpenCode session completion (seconds)
IDLE_TIMEOUT_SECONDS = 60

# Output directory for JSON results
RESULTS_DIR = REPO_ROOT / "harness" / "results"

# Agent files excluded from prompt optimization (not yet used in DAG system)
OPTIMIZATION_EXCLUDED_AGENTS = {
    "deep-researcher.md",
}
