# Verify

**Subagent:** tailwrench
**Verify Instructions:**
{{VERIFY_INSTRUCTIONS}}

**Constraints:**
{{CONSTRAINTS}}

Tailwrench is restricted to command execution and output reading — it cannot edit any files.

> [!NOTE]
> You are entering or already in a verify, triage and fix cycle. You have a limited number of tries to correct mistakes, so make each triage and fix attempt count. You will see this message after each triage step.

**Hard Rules**

1. Address the prompt as direct instructions *to* tailwrench — not commentary about the process.
2. Call the `task` tool with `subagent_type=tailwrench`.
3. The exact commands to run and verbatim output must be in the prompt — tailwrench needs them to execute and verify.
4. Decisions made throughout the plan *must* be adhered to. These are in addition to the constraints above. Both should be clearly stated in the prompt to tailwrench to ensure it can verify against them.

**Execution Steps:**

0. **Pre-Work Queries:** Call `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve any previous context that could be helpful. You *must* include one query for `"[DECISION]"`, which will inform any additional constraints that need to be included in your prompt.

1. **Prompt Drafting:** Construct a prompt *to* tailwrench that includes: what was implemented, the verify instructions and constraints above — treat both as pre-filled directives, and the required return format: commands run, full output, pass/fail verdict, and on failure — exact error output and which criteria failed.

2. **Delegation Gate:** Before calling `task`, verify: prompt addresses tailwrench directly, any necessary context from previous steps is included, success criteria and constraints (if present) are stated, return format is specified. Revise if any check fails, then call `task` with `subagent_type=tailwrench`.

3. **Note Taking:** Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}`. At minimum capture: verdict (pass/fail), commands run, and on failure — exact error output and which criteria failed. Store missing details if needed.

4. **Branch:** Call `get_branch_options` to retrieve available branch node IDs.
   - **PASS:** Call `next_step` with the success branch node ID.
   - **FAIL:** Call `next_step` with the triage branch node ID.

   Both outcomes require a branch argument — `next_step` cannot be called without one.
