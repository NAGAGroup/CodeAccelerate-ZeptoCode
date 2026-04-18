# AGENTS.md — ZeptoCode Operational Guide

This file contains repo-specific guidance to help future OpenCode agent sessions avoid mistakes and ramp up quickly. Every section answers: "Would an agent miss this without help?"

---

## Repository Overview

**CodeAccelerate-ZeptoCode** is a multi-agent planning and execution framework for OpenCode. It decomposes goals into executable DAGs, delegates to specialized agents, and recovers from failures automatically.

- **Build system**: Bun + OCX (OpenCode extension manager)
- **Deployment**: Cloudflare Workers (Wrangler)
- **Testing**: OpenCode HTTP API via localhost:4096 (naga-ollama profile)
- **Project root directory**: `/home/jack/ZeptoCode/.worktrees/opencode-cfg`

---

## Build & Deployment

### Build (compiles TypeScript plugin, packages OCX components)
```bash
bun run build
# Produces: dist/
```

**What it does:**
1. Compiles `files/plugins/planning-enforcement.ts` → `files/plugins/planning-enforcement.js`
2. Runs `bunx ocx build . --out dist`
3. Output written to `dist/` (used by Vercel/Netlify and Wrangler)

**Critical:** Plugin TypeScript must compile to JavaScript before `ocx build` runs. If plugin changes fail the build, the entire registry becomes corrupted.

### Deploy
```bash
bun run deploy
# Builds, then runs: wrangler deploy
```

Deployment uses `wrangler.jsonc` and assets from `dist/`. After deploy, profiles must be refreshed locally:
```bash
bash scripts/update-profiles.sh
# Clears local plugin cache, removes/re-adds all profiles
```

---

## Testing Infrastructure

### Setup (starts OpenCode server on port 4096)
```bash
bun run test:setup
# Starts: ocx oc -p naga-ollama serve --port 4096 (detached)
# Polls http://localhost:4096/session until ready (max 20s)
# Logs: /tmp/opencode-serve.log, /tmp/opencode-serve-err.log
```

**Do this first before any test run.** If it fails:
- Check logs: `tail /tmp/opencode-serve.log`
- Kill stray process: `pkill -f "ocx oc"`
- Verify Qdrant and Ollama are running

### Run Subagent Tests (agents × 3 trials)
```bash
bun run test:runner
# Tests: context-scout, context-insurgent, junior-dev, documentation-expert, tailwrench, external-scout, autonomous-agent, headwrench, deep-researcher
# Stores results: Qdrant collection "prompt-engineering-test-harness"
```

**Test flow:**
1. Reads agent prompts from `test/agent-prompts.ts`
2. POSTs realistic single-dispatch prompt to `/session` with `agentID` routing
3. Captures full tool-call trajectory via SSE
4. Measures agent behavior against permission frontmatter (not expected tool lists)

**Output:** Agent behavior patterns in Qdrant. Use to validate system prompts before deployment.

### Run E2E Planning DAG Tests (full /plan-session flow)
```bash
bun run test:e2e
# Single planning session E2E (requires human monitoring)
# Sessions captured: Qdrant collection "e2e-test-harness"
```

**Test flow:**
1. Sends realistic goal to headwrench (via plan-session command expansion)
2. Monitors multi-turn execution across all DAG nodes (session-overview → plan-success)
3. Captures per-node tool sequences and verifies enforcement specs
4. Simulates user decisions when user-decision-gate nodes are encountered
5. Timeout: 5 min per turn, 60 min total session

**Key timeouts (from `test/e2e-runner.ts`):**
- `TURN_TIMEOUT_MS = 300_000` (5 min idle wait per turn)
- `SESSION_TIMEOUT_MS = 3_600_000` (60 min total)

**Known issue:** E2E tests require human interaction for decision gates. No CI automation currently.

---

## Architecture & Directories

```
files/
├── agents/                    # Agent system prompts (YAML frontmatter + Markdown)
│   ├── headwrench.md        # Orchestrator — delegates, never codes
│   ├── junior-dev.md         # Implementer — edits code, runs builds, searches web
│   ├── tailwrench.md         # Verification expert — no edits, just checks
│   ├── context-scout.md      # Broad codebase survey
│   ├── context-insurgent.md  # Deep, narrow code analysis
│   ├── external-scout.md     # Web research with confidence tags
│   ├── documentation-expert.md # Writes/updates docs
│   └── ...
│
├── commands/                  # User-facing commands
│   ├── plan-session.md        # /plan-session <goal> — decompose into DAG
│   └── activate-plan.md       # /activate-plan <name> — execute DAG
│
├── skills/                    # Reusable instruction modules
│   ├── planning-schema/      # Phase types, field schemas, naming conventions
│   └── following-plans/      # How to execute DAG nodes
│
├── planning/plan-session/
│   ├── plan.jsonl            # Planning DAG definition (phases as JSONL)
│   ├── prompts/              # Planning orchestration prompts
│   │   ├── session-overview.md
│   │   ├── orientation-scout.md
│   │   ├── draft-plan.md
│   │   └── ...
│   └── node-library/         # DAG node templates
│       ├── junior-dev-work-item/      (implement code)
│       ├── documentation-expert-work-item/  (write docs)
│       ├── verify-work-item/         (check work)
│       ├── verify-triage/            (diagnose failures)
│       ├── context-scout/            (survey codebase)
│       ├── context-insurgent/        (deep analysis)
│       ├── external-scout/           (web research)
│       ├── decision-gate/            (agentic branching)
│       ├── user-decision-gate/       (human branching)
│       ├── user-discussion/          (conversation)
│       ├── write-notes/              (checkpoint)
│       ├── project-setup/            (environment setup)
│       ├── commit/                   (git commit)
│       └── CATALOGUE.md              # Index of all nodes
│
├── plugins/
│   ├── planning-enforcement.ts  # Main plugin (TypeScript)
│   ├── planning-enforcement.js  # Compiled output
│   ├── modules/
│   │   ├── tools/               # DAG execution tools
│   │   └── hooks/               # Plugin lifecycle hooks
│   └── ...
│
└── profiles/                    # Model configurations per profile
    ├── ollama/                  # naga-ollama (gemma4:4be local)
    ├── default/                 # naga (Claude Sonnet)
    ├── haiku/                   # naga-haiku (Claude Haiku)
    ├── copilot/                 # naga-copilot (GitHub Copilot)
    ├── haiku-copilot/           # naga-haiku-copilot (hybrid)
    └── free/                    # naga-free (Free tier APIs)

scripts/
├── update-profiles.sh           # Refreshes profiles after deploy

test/
├── setup.ts                     # Starts OpenCode server (port 4096)
├── runner.ts                    # Subagent test runner
├── e2e-runner.ts                # E2E planning DAG test runner
├── agent-prompts.ts             # Per-agent test prompts & success criteria
├── e2e-prompts.ts               # Planning goal variations for E2E testing
├── manifest.ts                  # Artifact discovery
└── STRATEGY.md                  # Test harness iteration strategy
```

---

## Agent Permissions (YAML Frontmatter)

Every agent file (e.g., `files/agents/headwrench.md`) has a YAML permission block that constrains tool access. **This is the contract — agents must never exceed their declared permissions.** Violation causes execution failures.

### Example: headwrench
```yaml
permission:
    "*": deny
    next_step: allow
    activate_plan: allow
    plan_session: allow
    task: allow
    question: allow
    qdrant_qdrant-find: allow
    qdrant_qdrant-store: allow
    skill:
        "*": deny
        following-plans: allow
        planning-schema: allow
```

**headwrench** can:
- Call `task` (delegate to subagents)
- Call `question` (ask user)
- Call planning tools (`plan_session`, `activate_plan`, `next_step`)
- Load skills: `following-plans`, `planning-schema`
- Read/write Qdrant

**headwrench** cannot:
- Edit code (no `write`, `edit`)
- Run bash (no `bash`)
- Search codebase (no `grep`, `smart_grep_*`)
- Search web (no `searxng_*`)

### Example: junior-dev
```yaml
permission:
    "*": deny
    bash: allow
    grep: allow
    read: allow
    write: allow
    edit: allow
    glob: allow
    smart_grep_search: allow
    smart_grep_trace_callers: allow
    smart_grep_trace_callees: allow
    smart_grep_trace_graph: allow
    smart_grep_index_status: allow
    searxng_searxng_web_search: allow
    searxng_web_url_read: allow
    context7_resolve-library-id: allow
    context7_query-docs: allow
```

**junior-dev** can:
- Read/write/edit files
- Search code (smart_grep, grep, glob)
- Run builds/tests (bash)
- Search web (searxng)
- Trace callers/callees (smart_grep_trace_*)

**junior-dev** cannot:
- Call `task` (no delegation)
- Modify agent configs
- Load skills directly

---

## Planning Schema (Key Phase Types)

Plans are DAGs of typed phases. Defined in `files/skills/planning-schema/SKILL.md`.

### `implement-code`
**Researches, implements, verifies, and retries a code goal** — bundled into single node with auto-triage loops.

```toml
[[phases]]
id = "my-feature"
type = "implement-code"
next = ["next-phase"]
project-survey-topics = ["survey areas before work"]
web-search-questions = ["research questions for pre-work"]
deep-search-questions = ["codebase analysis before work"]
pre-work-project-setup-instructions = ["setup commands to run"]
work-instructions = "detailed implementation steps"
verification-instructions = "success criteria: compilation, tests, etc."
commit = false
```

**Critical:** `work-instructions` and `verification-instructions` must include references to pre-work steps and external dependencies. Don't assume the orchestrator will relay this context — junior-dev won't know about it otherwise.

### `author-documentation`
**Single-dispatch doc goal** — no retry loop, no pre-work survey.

```toml
[[phases]]
id = "update-readme"
type = "author-documentation"
next = ["next-phase"]
goal = "update README with new deployment instructions"
commit = false
```

### `user-decision-gate`
**User chooses between branches** — linear, no auto-routing.

```toml
[[phases]]
id = "pick-approach"
type = "user-decision-gate"
next = ["approach-a", "approach-b"]
question = "Should we use approach A or B?"
```

### `agentic-decision-gate`
**Agent routes based on evidence** — no user input needed.

```toml
[[phases]]
id = "check-deps"
type = "agentic-decision-gate"
next = ["has-deps", "no-deps"]
question = "Does the project have external dependencies?"
```

### Other phases
- `web-search` — External research (informs decisions, does NOT satisfy pre-work web search)
- `user-discussion` — Open conversation with user (linear)
- `write-notes` — Checkpoint — documents findings
- `project-setup` — Environment setup
- `verify-work-item` — Check completed work
- `verify-triage` — Diagnose and fix verification failures

---

## Smart-Grep Index Lifecycle

### Initial Index Build
When `grepai` first runs on a project, it builds an embeddings index in `.grepai/`:
- **Takes time:** First `smart_grep_search` is slow (indexing)
- **Happens once:** Subsequent sessions reuse the index
- **Per-project:** Each project dir has its own `.grepai/`

### Index Staleness
Over time, stale entries accumulate in the index (deleted files, renamed symbols):
- **Symptom:** `smart_grep_search` results degrade or return irrelevant files
- **Fix:** Delete the index
  ```bash
  rm -rf .grepai/
  ```
- **Result:** Index rebuilds on next session (takes time, but fixes search quality)

### Mandatory Smart-Grep Protocol (junior-dev)
Per agent prompt `files/agents/junior-dev.md`:

1. **Call `smart_grep_index_status` first** — determine if index is empty or populated
2. **If populated:** Execute varied `smart_grep_search` queries, trace callers/callees with `smart_grep_trace_*`
3. **If empty:** Skip semantic search, fall back to grep/glob
4. **Before modifying code:** Always call `smart_grep_trace_callers` on the symbol being changed

---

## Commands: /plan-session and /activate-plan

### /plan-session
Starts a planning session. Decomposes a goal into an executable DAG.

```
/plan-session build a C++ ASCII art library that prints to stdout
```

**Hard rules (from `files/commands/plan-session.md`):**
1. Load `following-plans` skill immediately before anything else
2. Do NOT attempt to solve the request — only decompose it into a plan
3. Call `plan_session` tool (managed by headwrench)
4. Planning DAG guides all subsequent steps

### /activate-plan
Executes a previously-planned DAG.

```
/activate-plan my-feature
```

**Hard rules (from `files/commands/activate-plan.md`):**
1. Load `following-plans` skill immediately
2. Execute the plan exactly as designed — no modifications, no skipping steps
3. Call `activate_plan` tool with plan name
4. Execution DAG guides all subsequent steps

---

## Grepai Index Quirk

**Issue:** Grepai's incremental tracking accumulates stale entries over time. After significant codebase changes, search quality degrades.

**Symptom:** `smart_grep_search` returns outdated file paths or irrelevant results.

**Fix:** Delete and rebuild
```bash
cd your-project
rm -rf .grepai/
```

Next session will rebuild the index automatically. Per-session index isolation is being investigated.

---

## Test Commands Quick Reference

```bash
# 1. Start OpenCode server (required for all tests)
bun run test:setup

# 2. Run subagent tests (agents × 3 trials)
bun run test:runner

# 3. Run E2E planning DAG test
bun run test:e2e

# Combined: setup + e2e
bun run test:e2e:full

# Combined: setup + subagent runner
bun run test:full
```

**Before running tests:** Ensure Qdrant and Ollama are running.
```bash
# Check Qdrant
curl http://localhost:6333/health

# Check Ollama
curl http://localhost:11434/api/tags
```

---

## Profiles & Model Selection

Six profiles define different model combinations:

| Profile | Orchestrator | Subagents | Use Case |
|---------|---|---|---|
| **naga-ollama** | gemma4:4be | gemma4:4be | Local, private, fully self-hosted |
| **naga** | Claude Sonnet | Claude Haiku | Maximum reasoning + cost savings |
| **naga-haiku** | Claude Haiku | Claude Haiku | Budget option, no API key for headwrench |
| **naga-copilot** | GitHub Copilot | GitHub Copilot | Enterprise GitHub integration |
| **naga-haiku-copilot** | Claude Haiku | GitHub Copilot | Hybrid cost/capability |
| **naga-free** | Free tier API | Free tier API | Minimal cost, rate-limited |

### Running with Ollama
```bash
ollama pull gemma4:4be
export OPENCODE_OLLAMA_PORT=11434
ocx oc -p naga-ollama
```

### Running with llama.cpp (recommended for local inference)
```bash
llama-server \
  -hf unsloth/gemma-4-E4B-it-GGUF:Q8_0 \
  --temp 0.8 --top-p 0.95 --top-k 64 \
  --alias opencode-model \
  --port 8000 \
  --reasoning on
```

Then:
```bash
export OPENCODE_OLLAMA_PORT=8000
ocx oc -p naga-ollama
```

---

## Plugin Build Pitfalls

### TypeScript Compilation Required
`planning-enforcement.js` is **auto-generated** from `files/plugins/planning-enforcement.ts`. Never edit the `.js` file directly.

**Build process:**
1. TypeScript checks: `bun build planning-enforcement.ts --outfile planning-enforcement.js`
2. If compilation fails, the entire build fails — no partial output
3. OCX build consumes the `.js` file

### After Plugin Changes
1. Fix the `.ts` source
2. Run `bun run build` to regenerate `.js`
3. Run `bun run deploy`
4. Run `bash scripts/update-profiles.sh` to refresh profiles locally

If profiles become corrupt after deploy:
```bash
rm -rf ~/.config/opencode/plugins/planning-enforcement.js ~/.config/opencode/planning ~/.config/opencode/.ocx/
npx ocx profile rm naga naga-copilot naga-free naga-haiku naga-haiku-copilot naga-ollama --global
npx ocx profile add ... (re-add all profiles)
```

---

## DAG Node Library Organization

All DAG nodes live in `files/planning/plan-session/node-library/*/`:

- **node-spec.json** — Execution metadata: skill requirements, enforcement array, next phase
- **prompt.md** — Instruction template for the node (what the executor reads)

### Enforcement Array (node-spec.json)
```json
{
  "enforcement": ["task", "sequential-thinking_sequentialthinking"]
}
```

Declares which tools **must** be called in order. Used by E2E tests to verify node behavior.

### Node Prompt Structure
Each prompt is freestanding — includes all context the executor needs (references to prior nodes, external dependencies, success criteria, etc.).

**Common patterns:**
- `junior-dev-work-item`: "Implement X based on the earlier research from context-scout"
- `verify-work-item`: "Verify the changes from junior-dev-work-item by running tests"
- `verify-triage`: "Diagnosis why verify-work-item failed and what to retry"

---

## Registry & Component Publishing

All components are declared in `registry.jsonc`:

- **ocx-planning-plugin** (plugin) — DAG execution plugin
- **ocx-bundle** (bundle) — Agents, commands, skills
- **ocx-default**, **ocx-ollama**, etc. (profiles) — Model + plugin+bundle combos

**Publishing flow:**
1. Update `registry.jsonc` (if adding new components)
2. Run `bun run build` (compiles plugin + packages via OCX)
3. Run `bun run deploy` (pushes to Cloudflare Workers)
4. Users run `npx ocx profile add <profile-name>` to pull updates

---

## Key Reminders

1. **Grepai staleness**: If search quality degrades, `rm -rf .grepai/`
2. **Plugin is TypeScript**: Changes to `planning-enforcement.ts` must compile
3. **Test infrastructure is HTTP-based**: Runs via localhost:4096, not CLI
4. **Permissions are contracts**: Agents cannot exceed YAML frontmatter declarations
5. **Plans are portable**: Design with one model, execute with another
6. **Skills must load first**: Both `/plan-session` and `/activate-plan` require `following-plans` skill
7. **Enforcement specs matter**: E2E tests validate that nodes call expected tools in order

---

## References

- **README.md** — High-level overview, setup instructions, profiles
- **test/STRATEGY.md** — Test harness philosophy and current iteration status
- **files/skills/planning-schema/SKILL.md** — Complete phase type definitions
- **files/skills/following-plans/SKILL.md** — How to execute DAG nodes
- **files/planning/plan-session/node-library/CATALOGUE.md** — Index of all node types
