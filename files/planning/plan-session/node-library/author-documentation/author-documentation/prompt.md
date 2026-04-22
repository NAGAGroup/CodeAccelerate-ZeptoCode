# Documentation

**Subagent:** documentation-expert
**Authoring Instructions:**
{{AUTHORING_INSTRUCTIONS}}

**Constraints:**
{{CONSTRAINTS}}

**Planning Context:**
{{PLANNING_CONTEXT}}

**Hard Rules**
1. Draft and delegate a direct, actionable instruction set *to* documentation-expert — not meta-commentary.
2. Call the `task` tool with `subagent_type=documentation-expert`.
3. Documentation-expert is limited to documentation files only — never instruct it to make code changes.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve: verified code facts, API shapes, behavioral findings, and documentation conventions from prior steps.

2. **Prompt Drafting:** Draft the prompt for documentation-expert. Include: the authoring instructions, constraints, and planning context above — treat all as pre-filled directives, not areas to generate or expand, all verified technical facts as the mandatory source-of-truth, documentation conventions to follow, and return format requirements.

3. **Delegation Gate:** Before calling `task`, verify: prompt addresses documentation-expert directly, retrieved context is integrated, return format is specified, no code changes are requested. Revise if any check fails, then call `task` with `subagent_type=documentation-expert`.

4. **Note Taking:** Categorize the report into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. At minimum capture: what was written, files changed, any decisions or assumptions downstream steps should know about. Add missing notes before proceeding.

5. Call `next_step`.