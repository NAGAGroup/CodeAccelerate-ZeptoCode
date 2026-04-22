# Write Notes

**Phase:** {{PHASE_ID}}

**Hard Rules**
1. Each note must be self-contained — a future agent reading only that note must fully understand it without surrounding context.
2. One `qdrant_qdrant-store` call per distinct finding — never store as a monolithic block.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve findings from prior steps — what was accomplished, key decisions made, and the final state of the plan.

2. **Store Notes:** Document plan completion. For each distinct outcome, decision, or finding: call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}`. Capture: what was accomplished in this phase, key decisions or assumptions that were made, and what a future session would need to know to continue from this point. Write each note as self-contained prose.

3. **Self-Contained Check:** Review each stored note. If any note is shallow or would require surrounding context to understand, rewrite it before proceeding.

4. Call `next_step`.