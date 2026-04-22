## Task Definition: Pre-Documentation Deep Analysis

**Authoring Goal:**
{{AUTHORING_INSTRUCTIONS}}

**Constraints:**
{{CONSTRAINTS}}

**Analysis Questions:**
{{PROJECT_ANALYSIS_INSTRUCTIONS}}

**Process Flow:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve prior survey findings and planning context relevant to the authoring goal and analysis questions above.

2. **Analysis Delegation:** Draft a detailed task prompt for the `context-insurgent` subagent. The prompt must:
   - Address context-insurgent directly
   - Scope the analysis to the authoring goal, constraints, and analysis questions above — treat all as pre-filled directives, not areas to generate or expand
   - Integrate prior findings as context (not for re-derivation)
   - Specify the return format (findings per question, file/symbol cross-references, call graph summary, unresolved gaps)
   - Remain strictly within project source files — no external web searching
   
   Verify all of the above before calling `task` with `subagent_type=context-insurgent`.

3. **Note Taking:** Structure findings into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: the identified mechanism with file/symbol cross-references, relevant call graph summary, and any unresolved gaps. Verify all notes meet this threshold before proceeding.

4. Call `next_step`.