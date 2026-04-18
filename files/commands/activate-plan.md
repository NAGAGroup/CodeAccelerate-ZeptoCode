---
description: "Activate an execution plan produced by a planning session"
---

# Activate Plan

You are starting the execution of plan `$ARGUMENTS`. Your sole function is to initiate it following a strict validation sequence. Deviation from these rules constitutes task failure.

**Hard Rules**
1. Load the `following-plans` skill immediately — before any other operation.
2. Execute the plan exactly as designed. Modifications, scope reduction, step skipping, or working ahead are strictly forbidden.

**Execution Steps:**

1. **Load skill:** Load the `following-plans` skill.

2. **Preflight:** Confirm `plan_name` is `$ARGUMENTS` verbatim and that you have what you need to begin.

3. **Gate:** Before calling `activate_plan`, verify:
   - `following-plans` skill is loaded.
   - Preflight is complete.
   If either check fails, resolve it first.

4. Call `activate_plan` with `$ARGUMENTS`. The execution DAG will guide every subsequent step.
