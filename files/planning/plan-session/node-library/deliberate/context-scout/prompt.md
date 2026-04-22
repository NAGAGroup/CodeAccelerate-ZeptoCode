## Task Definition: Pre-Deliberation Codebase Survey

**Deliberation Goal:**
{{DELIBERATION_INSTRUCTIONS}}

**Planning Context:**
{{PLANNING_CONTEXT}}

**Survey Topics:**
{{PROJECT_SURVEY_INSTRUCTIONS}}

**Process Flow:**

1. **Context Retrieval (Preflight):** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve prior findings relevant to the survey topics and deliberation goal above.

2. **Survey Delegation:** Draft a highly targeted prompt for the `context-scout` subagent. The prompt must:
   - Address context-scout directly
   - Scope the survey to the deliberation goal, planning context, and survey topics listed above — treat all as pre-filled directives, not areas to generate or expand
   - Integrate any relevant prior findings retrieved above
   - Specify the return format (findings by topic, gaps identified, follow-up questions)
   - Remain strictly within project source file analysis — no external knowledge or web searching
   
   Verify all of the above before calling `task` with `subagent_type=context-scout`.

3. **Note Taking:** Categorize findings into distinct notes. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: specific findings, identified gaps, and follow-up actions. Verify all notes are stored before proceeding.

4. Call `next_step`.