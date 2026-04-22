## Task Definition: Pre-Implementation Codebase Survey

**Subagent:** context-scout
**Planning Context:**
{{PLANNING_CONTEXT}}

**Constraints:**
{{CONSTRAINTS}}

**Survey Topics:**
{{PROJECT_SURVEY_INSTRUCTIONS}}

**Hard Rules**
1. Write your prompt as instructions *to* context-scout — treat it as a message to another agent, not commentary about it.
2. Call the `task` tool with `subagent_type=context-scout`.

**Execution Steps:**

1. **Context Retrieval (Preflight):** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve prior findings relevant to the survey topics and implementation goal above.

2. **Survey Delegation:** Draft a highly targeted prompt for the `context-scout` subagent that includes:
        - The survey topics above — treat them as pre-filled directives, not areas to generate or expand
        - The retrieved prior findings as context (not for re-derivation)
        - A clearly specified return format (findings per topic, file/symbol cross-references, call graph summary, unresolved gaps)

3. **Delegation Gate:** Before calling `task`, verify: prompt addresses context-scout directly, retrieved context is integrated, return format is specified. Revise if any check fails, then call `task` with `subagent_type=context-scout`.

4. **Note Taking:** Structure findings into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: the identified mechanism with file/symbol cross-references, relevant call graph summary, and any unresolved gaps. Verify all notes meet this threshold before proceeding.

5. Call `next_step`.