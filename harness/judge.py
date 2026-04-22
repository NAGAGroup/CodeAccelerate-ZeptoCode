import json
import logging
import re
from pathlib import Path

import anthropic
import dspy

logger = logging.getLogger(__name__)


EXECUTION_JUDGE_PROMPT = """You are an expert evaluator of AI agent execution quality.

Your task is to evaluate an agent execution transcript against six key criteria:

1. **Reasoning Quality**: Are decisions coherent? Do the steps follow logically from prior context? Is there clear cause-and-effect between observations and next actions?

2. **Tool Call Discipline**: Is the sequencing of tool calls correct? Are there any hallucinated tool calls (calls that don't exist or are incorrectly parameterized)? Do parameters match the actual APIs and constraints?

3. **Scope Adherence**: Does the agent stay within the stated task boundaries? Is there feature creep (attempting work outside the stated scope)? Are there unjustified reductions in scope?

4. **Step Completion Signal**: Does each phase produce clear evidence of completion before proceeding to the next? Are intermediate results validated? Are invariants checked?

5. **Recovery Behavior Autonomy**: Does triage and recovery happen autonomously without being pre-specified? Is root-cause discovery genuine and methodical? Does the agent self-correct based on evidence?

6. **Context Threading**: Do decisions made in early phases correctly propagate to later phases? Is information retained and applied appropriately? Are contradictions resolved?

**Conservative Correctness Philosophy**:
A clean early exit (graceful failure after retries with a clear error summary) scores HIGHER than a dirty completion (scope creep, hallucinated success, constraint violations, false confidence). Reward honesty and discipline over appearance of success.

**Scoring Guidance**:
- 0.9–1.0 = Excellent across all criteria; coherent reasoning, disciplined tool use, perfect scope adherence, clear completion signals, autonomous recovery, tight context threading
- 0.7–0.9 = Good with minor gaps; mostly coherent but occasional logic jumps; mostly correct tool calls; slight scope drift; mostly clear signals; mostly autonomous recovery; mostly tight threading
- 0.5–0.7 = Acceptable but significant issues; some reasoning gaps; some tool call errors; scope creep or reduction; weak completion signals; reactive rather than autonomous recovery; loose threading
- Below 0.5 = Poor quality or failure signals; incoherent reasoning; hallucinated tools; major scope violations; no clear completion signals; no recovery attempt; broken context threading

Respond with ONLY a JSON object in this exact format (no markdown, no additional text):
{"score": <float between 0.0 and 1.0>, "feedback": "<string describing strengths and gaps>"}
"""


PLANNING_JUDGE_PROMPT = """You are an expert evaluator of AI-generated DAG planning quality for software projects.

Your task is to evaluate a candidate plan against 10 structural dimensions, each contributing a weighted score to the final evaluation:

1. **Structural Validity (10%)**: Is the DAG valid? Are there any cycles? Do all exits resolve to valid nodes? Is the graph acyclic?

2. **Collaborate Phase Placement (15%)**: Does a "collaborate" or "human decision" node appear early (before implementation begins)? Does it gate downstream branches appropriately?

3. **Branch Topology (20%)**: Are there multiple distinct branches (fork structure)? Does each branch have clear semantic identity mapping to a separate work item, decision path, or approach? Are branches semantically independent?

4. **Nested Deliberation (15%)**: Does deliberation occur at ≥2 levels (top-level planning + per-branch deliberation)? Is there thoughtful consideration at multiple scales?

5. **Merge Correctness (15%)**: Do branches sharing implementation primitives (same tools, same subtasks) converge at a shared downstream node? Do independent branches avoid false convergence?

6. **Asymmetric Merges (10%)**: Does merge topology vary by branch characteristics (not a uniform fork-join)? Do some branches skip certain verification steps while others don't? Is the structure adapted to branch-specific needs?

7. **Sequential Phase Discipline (10%)**: Does each branch follow a coherent sequence: deliberate → implement → verify → document (or a subset appropriate to the branch)? Are phases in logical order?

8. **Semantic Completeness (10%)**: Does the plan cover the full task scope? Are all work items represented? Is nothing missing or deferred without justification?

9. **Constraint Adherence (5%)**: Does the plan respect stated technical constraints (tool limits, scope restrictions, platform requirements)?

10. **Collaborate Semantics (5%)**: If a collaborate node exists, does it specify a clear decision point? Do the downstream branches map explicitly to user choices or alternative approaches?

**Scoring Bands**:
- 0.85–1.0 = Excellent: Valid structure, strong branch topology, nested deliberation, correct merges, asymmetric design, full phase discipline, complete scope, constraints respected, clear collaborate semantics
- 0.65–0.85 = Good: Valid structure, good branch topology, some nested deliberation, mostly correct merges, some asymmetry, mostly sequential, mostly complete, mostly constrained-aware, adequate collaborate semantics
- 0.35–0.65 = Poor: Valid structure but weak branching, flat deliberation, some merge errors, uniform fork-join, inconsistent phase discipline, incomplete scope, constraint violations, weak collaborate semantics
- 0.0–0.35 = Failure: Invalid DAG, no branching, no deliberation, broken merges, no phase discipline, incomplete scope, constraint violations, broken collaborate semantics

Compute the final score as a weighted average of the 10 dimension scores.

Respond with ONLY a JSON object in this exact format (no markdown, no additional text):
{"score": <float between 0.0 and 1.0>, "feedback": "<string describing dimension strengths and gaps>"}
"""


def _parse_judge_response(response_text: str) -> tuple[float, str]:
    """
    Parse score and feedback from Claude's response text.
    Returns (score, feedback) where score is clamped to [0.0, 1.0].
    Falls back to regex extraction if JSON parsing fails.
    """
    # Primary: try JSON parse
    try:
        data = json.loads(response_text)
        score = float(data.get("score", 0.0))
        feedback = str(data.get("feedback", response_text))
        return max(0.0, min(1.0, score)), feedback
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    # Fallback: regex extraction
    score_match = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', response_text)
    score = float(score_match.group(1)) if score_match else 0.0
    score = max(0.0, min(1.0, score))
    feedback_match = re.search(r'"feedback"\s*:\s*"([^"]*)"', response_text)
    feedback = feedback_match.group(1) if feedback_match else response_text[:500]
    return score, feedback


def score_execution_run(transcript: str, anthropic_client: anthropic.Anthropic) -> dspy.Prediction:
    """
    Score a ZeptoCode DAG execution run using Claude Sonnet as judge.

    Args:
        transcript: Full session transcript text
        anthropic_client: Initialized Anthropic client

    Returns:
        dspy.Prediction with score (float [0.0, 1.0]) and feedback (str)
    """
    if not transcript or len(transcript) < 100:
        return dspy.Prediction(score=0.0, feedback="Hung or empty run")

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=EXECUTION_JUDGE_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Evaluate this execution transcript:\n\n{transcript}"
                }
            ]
        )
        response_text = response.content[0].text
        score, feedback = _parse_judge_response(response_text)
        return dspy.Prediction(score=score, feedback=feedback)
    except Exception as e:
        logger.error(f"Execution judge failed: {e}")
        return dspy.Prediction(score=0.0, feedback=f"Judge error: {str(e)}")


def score_planning_run(
    candidate_plan: str,
    reference_transcript_path: Path,
    anthropic_client: anthropic.Anthropic
) -> dspy.Prediction:
    """
    Score a ZeptoCode planning run by comparing candidate plan structure
    against the 10 structural dimensions rubric.

    Args:
        candidate_plan: The candidate plan text (TOML or structured text)
        reference_transcript_path: Path to the Sonnet reference transcript
            (read for context; judge scores topology against embedded rubric)
        anthropic_client: Initialized Anthropic client

    Returns:
        dspy.Prediction with score (float [0.0, 1.0]) and feedback (str)
    """
    if not candidate_plan or len(candidate_plan.strip()) == 0:
        return dspy.Prediction(score=0.0, feedback="Empty plan")

    # Read reference transcript for context (best-effort)
    reference_context = ""
    try:
        reference_context = Path(reference_transcript_path).read_text(encoding="utf-8")
        # Truncate to avoid token limits — use first 3000 chars as reference context
        reference_context = reference_context[:3000]
    except Exception as e:
        logger.warning(f"Could not read reference transcript: {e}")
        reference_context = "(reference transcript unavailable)"

    user_message = (
        f"Reference planning transcript (high-quality example):\n\n"
        f"{reference_context}\n\n"
        f"---\n\n"
        f"Candidate plan to evaluate:\n\n"
        f"{candidate_plan}"
    )

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=PLANNING_JUDGE_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )
        response_text = response.content[0].text
        score, feedback = _parse_judge_response(response_text)
        return dspy.Prediction(score=score, feedback=feedback)
    except Exception as e:
        logger.error(f"Planning judge failed: {e}")
        return dspy.Prediction(score=0.0, feedback=f"Judge error: {str(e)}")
