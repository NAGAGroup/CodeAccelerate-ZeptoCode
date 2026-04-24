#!/usr/bin/env python3
"""
GEPA prompt optimization harness.

Optimizes the body of `--optimized-prompt` against a static scenario
(`--static-prompt`, `--agent`) using an LM-as-a-judge rubric
(`--eval-criteria`). The file's frontmatter is preserved across all writes.

Black box: `run_opencode(static_path, optimized_path, agent) -> str` — the
user implements this. Every forward pass:
  1. reads the current (GEPA-mutated) body from the Predict signature
  2. writes `frontmatter + body` to the optimized prompt file
  3. calls run_opencode
  4. returns the resulting string as a dspy.Prediction

Both the judge and the reflection LM run via ollama (default localhost:11434).

Dependencies:  dspy  ollama
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import dspy
import ollama


# ======================================================================
# STUB — user implements this
# ======================================================================


def run_command_live(cmd: list[str]) -> tuple[str, int]:
    captured = []
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr in; drop this to keep separate
        text=True,
        bufsize=1,  # line-buffered
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured.append(line)
    returncode = proc.wait()
    return "".join(captured), returncode


def run_opencode(
    workdir: Path,
    static_prompt_path: Path,
    optimized_prompt_path: Path,
    agent: str,
) -> str:
    with open(static_prompt_path, "r") as file:
        prompt = file.read()
    cwd = os.getcwd()
    os.chdir(workdir)
    subprocess.call("git checkout .".split(" "))
    subprocess.call("git clean -Xdf .".split(" "))
    command_str = f"npx opencode run --thinking --agent {agent} '{prompt}'"
    output, retval = run_command_live(command_str.split(" "))

    os.chdir(cwd)
    return output


# ======================================================================
# Frontmatter-preserving file IO
# ======================================================================


def split_frontmatter(text: str) -> tuple[str, str]:
    """
    Split leading YAML frontmatter (delimited by `---` lines) from body.
    Returns (frontmatter_block_including_delimiters_and_trailing_newline, body).
    If no frontmatter is found, returns ("", text).
    """
    if not text.startswith("---"):
        return "", text
    lines = text.split("\n")
    if lines[0] != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i] == "---":
            frontmatter = "\n".join(lines[: i + 1]) + "\n"
            body = "\n".join(lines[i + 1 :]).lstrip("\n")
            return frontmatter, body
    return "", text


def write_with_frontmatter(path: Path, frontmatter: str, body: str) -> None:
    path.write_text(frontmatter + body, encoding="utf-8")


# ======================================================================
# DSPy student module — the Predict signature's .instructions IS the
# optimized prompt body. GEPA mutates that; we forward the mutation to
# the filesystem and call the black box.
# ======================================================================


class _OpencodeSignature(dspy.Signature):
    """Placeholder — overwritten via with_instructions at construction."""

    static_prompt_path: str = dspy.InputField()
    agent: str = dspy.InputField()
    output: str = dspy.OutputField()


class OpencodeModule(dspy.Module):
    def __init__(
        self, workdir: Path, initial_body: str, optimized_path: Path, frontmatter: str
    ):
        super().__init__()
        sig = _OpencodeSignature.with_instructions(initial_body)
        self.predict = dspy.Predict(sig)
        self._workdir = workdir
        self._optimized_path = optimized_path
        self._frontmatter = frontmatter

    def forward(self, static_prompt_path: str, agent: str) -> dspy.Prediction:
        # Whatever body GEPA currently has installed on the predictor:
        current_body = self.predict.signature.instructions
        # Persist it to the optimized prompt file, preserving frontmatter.
        write_with_frontmatter(self._optimized_path, self._frontmatter, current_body)
        # Black box call.
        output = run_opencode(
            workdir=self._workdir,
            static_prompt_path=Path(static_prompt_path),
            optimized_prompt_path=self._optimized_path,
            agent=agent,
        )
        return dspy.Prediction(output=output)


# ======================================================================
# Ollama judge — returns dspy.Prediction(score=..., feedback=...)
# ======================================================================

_JUDGE_SYSTEM_PROMPT = """You are evaluating the output of an AI agent against a rubric.

Respond with a JSON object and nothing else:
{
  "score": <float between 0.0 and 1.0>,
  "feedback": "<detailed textual rationale citing concrete aspects of the output against specific rubric criteria>"
}

Your feedback will be used as reflective guidance to improve the prompt that produced this output. Cite concrete evidence from the output; vague commentary wastes the optimizer's budget.
"""


def make_metric(eval_criteria: str, judge_model: str, ollama_host: str):
    client = ollama.Client(host=ollama_host)

    def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        user_msg = (
            f"## Rubric\n\n{eval_criteria}\n\n"
            f"## Agent Output\n\n{pred.output}\n\n"
            "Evaluate the agent output against the rubric. Respond with JSON only."
        )
        try:
            response = client.chat(
                model=judge_model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                format="json",
            )
            parsed = json.loads(response["message"]["content"])
            return dspy.Prediction(
                score=float(parsed["score"]),
                feedback=str(parsed.get("feedback", "")),
            )
        except Exception as e:
            return dspy.Prediction(
                score=0.0,
                feedback=f"Judge error: {type(e).__name__}: {e}",
            )

    return metric


# ======================================================================
# Main
# ======================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workdir",
        type=Path,
        required=True,
        help="Directory in which to launch opencode",
    )
    parser.add_argument(
        "--static-prompt",
        type=Path,
        required=True,
        help="Path to the fixed scenario prompt file",
    )
    parser.add_argument(
        "--optimized-prompt",
        type=Path,
        required=True,
        help="Path to the prompt file being optimized (rewritten in place)",
    )
    parser.add_argument(
        "--eval-criteria",
        type=Path,
        required=True,
        help="Path to the rubric file used by the judge",
    )
    parser.add_argument(
        "--agent",
        type=str,
        required=True,
        help="Agent name passed through to the opencode stub",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="eval-model",
        help="Ollama model name for the judge",
    )
    parser.add_argument(
        "--reflection-model",
        type=str,
        default="eval-model",
        help="Ollama model name for GEPA's reflection LM",
    )
    parser.add_argument(
        "--ollama-host",
        type=str,
        default="http://localhost:11434",
        help="Ollama host URL",
    )
    parser.add_argument(
        "--auto",
        type=str,
        default="light",
        choices=["light", "medium", "heavy"],
        help="GEPA budget preset",
    )
    args = parser.parse_args()

    # --- Load files ---
    eval_criteria = args.eval_criteria.read_text(encoding="utf-8")
    optimized_text = args.optimized_prompt.read_text(encoding="utf-8")
    frontmatter, initial_body = split_frontmatter(optimized_text)

    # --- Configure DSPy ---
    # The task LM is never actually invoked by OpencodeModule.forward (we
    # only read signature.instructions and call the black box), but dspy
    # requires a default LM to be configured.
    task_lm = dspy.LM(
        f"ollama_chat/{args.reflection_model}",
        api_base=args.ollama_host,
        max_tokens=32000,
    )
    dspy.configure(lm=task_lm)

    reflection_lm = dspy.LM(
        f"ollama_chat/{args.reflection_model}",
        api_base=args.ollama_host,
        temperature=1.0,
        max_tokens=32000,
    )

    # --- Student, trainset, metric ---
    student = OpencodeModule(
        workdir=args.workdir,
        initial_body=initial_body,
        optimized_path=args.optimized_prompt,
        frontmatter=frontmatter,
    )

    trainset = [
        dspy.Example(
            static_prompt_path=str(args.static_prompt),
            agent=args.agent,
        ).with_inputs("static_prompt_path", "agent")
    ]

    metric = make_metric(
        eval_criteria=eval_criteria,
        judge_model=args.judge_model,
        ollama_host=args.ollama_host,
    )

    # --- GEPA ---
    optimizer = dspy.GEPA(
        metric=metric,
        auto=args.auto,
        reflection_lm=reflection_lm,
        reflection_minibatch_size=1,
        track_stats=True,
    )

    print("[harness] Running GEPA optimization...", file=sys.stderr)
    optimized = optimizer.compile(student, trainset=trainset)

    # --- Persist final best body ---
    final_body = optimized.predict.signature.instructions
    write_with_frontmatter(args.optimized_prompt, frontmatter, final_body)
    print(
        f"[harness] Final optimized prompt written to {args.optimized_prompt}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
