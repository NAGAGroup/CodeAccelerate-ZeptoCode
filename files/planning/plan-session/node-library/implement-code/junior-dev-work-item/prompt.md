# Code Implementation

**Subagent:** junior-dev
**Planning Context:**
{{PLANNING_CONTEXT}}

**Implementation Instructions:**
{{IMPLEMENT_INSTRUCTIONS}}

**Constraints:**
{{CONSTRAINTS}}

**Hard Rules**
1. All instructions must be directed *to* junior-dev — actionable tasks, not commentary about the process.
2. Call the `task` tool with `subagent_type=junior-dev`.
3. Implementation must adhere to the provided instructions and constraints. Any necessary code changes should be limited to the scope defined in the implementation instructions and must be explicitly approved in the prompt instructions.
4. Decisions made throughout the plan *must* be adhered to. These are in addition to the constraints above. Both should be clearly stated in the prompt to tailwrench to ensure it can verify against them.

**Execution Steps:**

0. **Pre-Work Queries:** Call `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve any previous context that could be helpful. You *must* include one query for `"[DECISION]"`, which will inform any additional constraints that need to be included in your prompt.

1. **Prompt Drafting:** Draft a clear, actionable prompt for junior-dev that includes:
        - The implementation instructions above — treat them as pre-filled directives, not areas to generate or expand.
        - The constraints and planning context as relevant to the implementation steps.
        - Provide web search instructions, if any, so junior-dev knows where to look to help with implementation and troubleshooting.
        - A clearly specified return format (what was implemented, any issues encountered, and how they were resolved).

2. **Delegation Gate:** Before calling `task`, verify: prompt addresses junior-dev directly, retrieved context is integrated, web search instructions included if web search instructions are present, return format is specified. Revise if any check fails, then call `task` with `subagent_type=junior-dev`.

3. **Note Taking:** Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}`. At minimum capture: each implementation step with success/failure status, and any output relevant to subsequent steps. Add missing notes if needed.