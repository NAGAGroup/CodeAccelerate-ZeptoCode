# Triage

**Subagent:** junior-dev
**Constraints:**
{{CONSTRAINTS}}

Verification failed. Junior-dev will investigate the root cause and apply a fix.

> [!NOTE]
> You are entering or already in a verify, triage and fix cycle. You have a limited number of tries to correct mistakes, so make each triage and fix attempt count. You will see this message after each failed verification step.

**Hard Rules**
1. Address the prompt as direct instructions *to* junior-dev — not commentary about the process.
2. Call the `task` tool with `subagent_type=junior-dev`.
3. The failed commands and error output must be included in the prompt for reproduction.
4. Decisions made throughout the plan should be integrated into the prompt for verification.
5. Always let the subagent discover the fix and the root cause on its own. Remember, you are merely a project orchestrator. Never specify the fix, the root cause, or the specific aspect of the project that is broken. By limiting the scope, you restrict the search space and limit the subagent's ability to find the optimal solution. Instead, your job is to provide context and guidance, and then let the subagent do its work.

**Execution Steps:**

0. **Pre-Work Queries:** Call `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve any previous context that could be helpful. You *must* include one query for `"[DECISION]"`, which will inform any additional constraints that need to be included in your prompt.

1. **Prompt Generation:** Draft a cohesive message *to* junior-dev that includes:
   - Instructions to triage and fix the issue. Do not specify the root cause, the fix, or the broken component; provide all necessary context for the subagent to discover the solution.
   - Guidance on initial steps, such as re-running failed commands.
   - The verbatim failed commands and exact error output, presented as the raw, observable event for reproduction.
   - All prior triage attempts to prevent redundant investigation.
   - A directive to investigate the issue, apply a suitable fix, and document the findings.
   - Provide web search instructions, if any, so junior-dev knows where to look to help with its triaging and identification of a fix.

2. **Delegation Gate:** Before calling `task`, verify: prompt addresses junior-dev directly, instructions are clear, web search instructions included, any necessary context from previous steps is integrated, return format is specified, verbatim failure output is in the prompt (not summarized). Revise if any check fails, then call `task` with `subagent_type=junior-dev`.

3. **Note Taking:** Categorize the report into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. At minimum capture: root cause, fix applied, files changed. Add missing notes if needed.

4. Call `next_step`.
