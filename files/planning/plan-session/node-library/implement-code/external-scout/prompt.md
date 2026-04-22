# Web Search: Pre-Implementation Research

**Subagent:** external-scout
**Planning Context:**
{{PLANNING_CONTEXT}}

**Constraints:**
{{CONSTRAINTS}}

**Research Questions:**
{{WEB_SEARCH_INSTRUCTIONS}}

**Hard Rules**
1. Write your prompt as instructions *to* external-scout — treat it as a message to another agent, not commentary about it.
2. Call the `task` tool with `subagent_type=external-scout`.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve known project constraints (language versions, dependencies, exclusions) and prior findings related to the research questions.

2. **Prompt Drafting:** Draft a direct, actionable instruction set for external-scout that includes:
        - The research questions above — treat them as pre-filled directives, not areas to generate or expand.
        - The retrieved project constraints and prior findings as context (not for re-derivation).
        - A clearly specified return format (findings per question, confidence level, sources consulted).

3. **Delegation Gate:** Before calling `task`, verify: prompt addresses external-scout directly, retrieved context is integrated, return format is specified. Revise if any check fails, then call `task` with `subagent_type=external-scout`.

4. **Note Taking:** Categorize the report into distinct notes — one per question or finding area. Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` once per note. Each note must capture: the finding, confidence tag, unresolved unknowns, and sources consulted.

5. Call `next_step`.