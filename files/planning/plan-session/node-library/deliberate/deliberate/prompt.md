**Deliberation Instructions:**
{{DELIBERATION_INSTRUCTIONS}}

**Planning Context:**
{{PLANNING_CONTEXT}}

**Hard Rules**
1. Do not call `next_step` until you have worked through all deliberation instructions.
2. Always deliberate on your own, this is not a user-involved task.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve any relevant context. Call it as many times as needed.

2. **Deliberate:** Work through all deliberation instructions, make any decisions mentioned. Think through each fully, this deliberation directly affects the quality of your work in future steps.

3. **Store Essential Context:** If you identify any essential context that should be preserved for future steps, call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}` to save it. This could include decisions made, insights gained, or any other information you think is crucial to remember. Decisions made *must* be captured and must be prefixed with `"[DECISION]"`.

4. Only after you have deliberated on all instructions, call `next_step` to proceed to the next node in the plan. If the tool fails and provides branch names in the error message, choose the appropriate branch based on your deliberation by passing it to your `next_step` call.

