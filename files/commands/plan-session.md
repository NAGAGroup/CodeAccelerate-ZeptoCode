---
description: "Start a planning session — explore, design, decompose, and write a project DAG"
---

# Plan Session

You are starting a planning session for the following request: `$ARGUMENTS`

**Hard Rules**
1. Load the `following-plans` skill immediately — before any other operation.
2. Do not attempt to solve the request. This session decomposes it into a plan — it does not execute it.

**Execution Steps:**

1. **Load skill:** Load the `following-plans` skill. Failure to load constitutes immediate task failure.

2. **Preflight:** Evaluate the user's request (`$ARGUMENTS`) and establish:
   - `user_request`: A complete, lossless summary in your own words — retain all semantic details and constraints.
   - `user_involvement`: true/false — does the user want to be involved during planning or execution?
   - `user_involvement_nature`: If true, describe the specific nature of the collaboration required.
   - `constraints`: All explicit limitations, exclusions, or scope boundaries in `$ARGUMENTS`.

3. **Gate:** Before calling `plan_session`, verify:
   - `following-plans` skill is loaded.
   - All preflight fields are populated.
   If either check fails, resolve it first.

4. Call `plan_session`. The planning DAG will guide every subsequent step.
