## Task Definition: Pre-Implementation Deep Analysis

**Subagent:** context-insurgent
**Planning Context:**
{{PLANNING_CONTEXT}}

**Constraints:**
{{CONSTRAINTS}}

**Analysis Questions:**
{{PROJECT_ANALYSIS_INSTRUCTIONS}}

**Hard Rules**

1. Write your prompt as instructions *to* context-insurgent — treat it as a message to another agent, not commentary about it.
2. Call the `task` tool with `subagent_type=context-insurgent`.

**Execution Steps:**

1. **Context Retrieval (Preflight):** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve prior findings relevant to the analysis questions and implementation goal above.

2. **Analysis Delegation:** Draft a highly targeted prompt for the `context-insurgent` subagent that includes:
        - The analysis questions above — treat them as pre-filled directives, not areas to generate or expand
        - The retrieved prior findings as context (not for re-derivation)
        - A clearly specified return format (insights per question, file/symbol cross-references, call graph implications, unresolved gaps)

3. **Delegation Gate:** Before calling `task`, verify: prompt addresses context-insurgent directly, retrieved context is integrated, return format is specified. Revise if any check fails, then call `task` with `subagent_type=context-insurgent`.

4. **Note Taking:** Structure insights into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: the identified insight with file/symbol cross-references, relevant call graph implications, and any unresolved gaps. Verify all notes meet this threshold before proceeding.

5. Call `next_step`.