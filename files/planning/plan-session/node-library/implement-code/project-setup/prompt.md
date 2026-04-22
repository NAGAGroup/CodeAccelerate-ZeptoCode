# Project Setup

**Subagent:** junior-dev
**Setup Instructions:**
{{SETUP_INSTRUCTIONS}}

**Hard Rules**
1. Output must be framed as instructions *to* junior-dev — not meta-commentary about the process.
2. Call the `task` tool with `subagent_type=junior-dev`.
3. Modifying source code is forbidden in this step — junior-dev should only be setting up the environment, dependencies, and tools needed for implementation. Any necessary code changes for setup should be limited to configuration files (e.g., package.json, .env) and must be explicitly approved in the prompt instructions.
4. Decisions made throughout the plan *must* be adhered to. Ensure decisions that constrain the project setup instructions are clearly stated in the prompt to junior-dev to ensure it can set up the environment accordingly.

**Execution Steps:**

0. **Pre-Work Queries:** Call `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve any previous context that could be helpful. You *must* include one query for `"[DECISION]"`, which will inform any additional constraints that need to be included in your prompt.

1. **Context Retrieval:** Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve environment constraints, known dependency versions, and any prior failed attempts that affect how these steps should run.

2. **Prompt Drafting:** Draft the prompt for junior-dev that includes:
        - The setup instructions above — treat them as pre-filled directives, not areas to generate or expand.
        - The retrieved context and environment constraints.
        - Provide web search instructions, if any, so junior-dev knows where to look to help with setup and troubleshooting.
        - A clearly specified return format (what was set up, any issues encountered, and how they were resolved).

3. **Delegation Gate:** Before calling `task`, verify: prompt addresses junior-dev directly, retrieved context is integrated, web search instructions included if web search instructions are present, return format is specified. Revise if any check fails, then call `task` with `subagent_type=junior-dev`.

4. **Note Taking:** Call `qdrant_qdrant-store` with `collection_name={{PLAN_NAME}}`. At minimum capture: each setup step with success/failure status, and any output relevant to subsequent steps. Add missing notes if needed.

5. Call `next_step`.