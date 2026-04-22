# Write Notes

**Phase:** {{PHASE_ID}}

**Implementation Goal:**
{{IMPLEMENT_INSTRUCTIONS}}

**Verify Instructions:**
{{VERIFY_INSTRUCTIONS}}

**Hard Rules**
1. Each note must be self-contained — a future agent reading only that note must fully understand it without surrounding context.
2. One `qdrant_qdrant-store` call per distinct finding — never store as a monolithic block.

**Execution Steps:**

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve findings from prior steps — what was attempted across all triage cycles, the last error output, and the current state of the codebase.

2. **Store Notes:** Document the failure state for this phase. For each distinct finding: call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}`. Capture: what the implementation goal was, what was attempted across all triage cycles, the final error output, and what a future session would need to resolve this. Write each note as self-contained prose.

3. **Self-Contained Check:** Review each stored note. If any note is shallow or would require surrounding context to understand, rewrite it before proceeding.

4. Call `next_step`.