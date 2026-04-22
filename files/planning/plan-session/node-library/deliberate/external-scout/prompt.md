# Web Search: Pre-Deliberation Research

**Deliberation Goal:**
{{DELIBERATION_INSTRUCTIONS}}

**Research Questions:**
{{WEB_SEARCH_INSTRUCTIONS}}

**Hard Rules**
1. Write your prompt as instructions *to* external-scout — treat it as a message to another agent, not commentary about it.
2. Call the `task` tool with `subagent_type=external-scout`.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve known project constraints (language versions, dependencies, exclusions) and prior findings related to the research questions.

2. **Prompt Drafting:** Draft a direct, actionable instruction set for external-scout. Include: the deliberation goal and research questions above — treat both as pre-filled directives, not areas to generate or expand, a summary of prior context (to prevent redundant research), all project constraints, and reporting requirements — confidence tags (High/Medium/Low) for every finding, sources consulted, and unresolved unknowns.

3. **Delegation Gate:** Before calling `task`, verify:
   - Prompt addresses external-scout directly
   - Deliberation goal and research questions are included
   - Retrieved context is integrated
   - Return format is specified with confidence tags
   - Project constraints are stated
   
   Revise if any check fails, then call `task` with `subagent_type=external-scout`.

4. **Note Taking:** Categorize the report into distinct notes — one per question or finding area. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: the finding, confidence tag, unresolved unknowns, and sources consulted.

5. Call `next_step`.