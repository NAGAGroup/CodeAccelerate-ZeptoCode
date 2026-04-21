# AGENTS.md — ZeptoCode Project Guide

## What This Is
ZeptoCode is a DAG-driven planning and execution plugin for [OpenCode](https://opencode.ai). It runs locally on a 4B parameter model and orchestrates multi-agent workflows as typed execution graphs.

**Key repo fact**: This is a registry, plugins, and profiles repository—not an application. Code here is shipped to users via OCX (OpenCode Extension Manager).

---

## Build System

### Single Command (All Platforms)
```bash
npm run build
```

Does two things in order:
1. Builds `files/plugins/planning-enforcement.ts` → `planning-enforcement.js` (Bun-bundled, Node target)
2. Runs `ocx build . --out dist` to package all components

**Build output location**: `./dist/` — contains JSON registry and component files.

**Deploy** (Cloudflare Workers):
```bash
npm run deploy
```

**Dev mode** (local hotload):
```bash
npm run dev
```

---

## Project Structure

```
files/
├─ agents/                  # Agent role definitions (Markdown + YAML frontmatter)
│  ├─ headwrench.md        # Main orchestrator (primary agent)
│  ├─ junior-dev.md        # Code implementer
│  ├─ tailwrench.md        # Verification specialist
│  ├─ context-scout.md     # Broad codebase survey
│  ├─ context-insurgent.md # Deep analysis of specific code
│  ├─ external-scout.md    # Web research
│  └─ documentation-expert.md
├─ commands/               # Top-level user commands
│  ├─ plan-session.md      # `/plan-session` — initiate planning
│  └─ activate-plan.md     # `/activate-plan` — execute a plan
├─ skills/                 # Reusable skill definitions
│  ├─ following-plans/SKILL.md      # DAG-following protocol
│  └─ planning-schema/SKILL.md      # Plan schema validation
├─ planning/               # Execution DAGs and templates
│  └─ plan-session/        # The master planning DAG
│     ├─ plan.jsonl        # DAG definition (schema v4.0)
│     ├─ prompts/          # Phase-level system prompts
│     └─ node-library/     # Executable node specs (phases, stages, prompts)
├─ profiles/               # Model/agent configuration profiles
│  ├─ ollama/              # Fully local (gemma4 or custom Ollama model)
│  ├─ default/             # Claude Sonnet + Haiku (Anthropic)
│  ├─ copilot/             # GitHub Copilot
│  ├─ haiku/               # All-Haiku
│  ├─ haiku-copilot/       # Haiku + Copilot
│  └─ free/                # OpenCode free models
└─ plugins/               # Plugin source code
   ├─ planning-enforcement.ts  # Main plugin entry point
   ├─ dag-lifecycle.ts         # DAG copying & initialization
   ├─ phase-io.ts            # JSONL DAG read/write
   ├─ modules/               # Tool implementations & hooks
   └─ package.json           # Bun dependencies (@opencode-ai/plugin, beautiful-mermaid)

registry.jsonc             # OCX registry manifest (defines what gets shipped)
package.json               # Root build scripts (bun + wrangler)
wrangler.jsonc             # Cloudflare Workers config
netlify.toml / vercel.json # Alt deployment targets
```

---

## Critical Architecture Notes

### DAG Format: `plan.jsonl` (Schema v4.0)
- **JSONL format**: First line is metadata, subsequent lines are phase records.
- **Metadata**: `{ schema_version: "4.0", name, description, ... }`
- **Phase records**: `{ id, type, config, exits, ... }`
- **Validation**: Checked by `phase-io.ts:detectSchemaVersion()` and phase-io read/write functions.
- **Location in workflow**: Plans are copied from `files/planning/<plan-type>/plan.jsonl` → `.opencode/session-plans/<plan-type>-<sessionId>/plan.jsonl` at runtime.

### Execution Flow
1. User runs `/plan-session <goal>`
2. **headwrench** loads `plan.jsonl` and executes the DAG step by step
3. Each phase can spawn sub-agents (**context-scout**, **junior-dev**, **tailwrench**, etc.)
4. **Verification nodes** trigger triage & retry loops on failure
5. User runs `/activate-plan <name>` to execute a planned DAG

### Agent Model Assignment
Configured in `files/profiles/<profile>/opencode.jsonc`:
- **headwrench**: Sonnet (default) or local Ollama model — orchestrates the entire DAG
- **junior-dev**: Haiku or Ollama — writes code
- **tailwrench**: Sonnet or Ollama — verifies work
- **context-scout / context-insurgent**: Haiku/Sonnet or Ollama — analyze code
- **external-scout**: Haiku or Ollama — web research
- **documentation-expert**: Haiku or Ollama — writes docs

---

## Key Files to Touch (Selectively)

### To Add/Modify Agents
Edit: `files/agents/<agent-name>.md`
- YAML frontmatter + Markdown role definition
- Permission blocks determine tool access
- Changes require rebuild: `npm run build`

### To Add/Modify Commands
Edit: `files/commands/<command-name>.md`
- Defines user-facing `/command` behavior
- Requires rebuild

### To Modify the Planning DAG
Edit: `files/planning/plan-session/plan.jsonl`
- Schema v4.0 — do NOT hand-edit; use tooling to modify
- Changes propagate on next `npm run build`

### To Add New Plan Types
1. Create `files/planning/<new-plan-type>/plan.jsonl` (schema v4.0)
2. Add prompts to `files/planning/<new-plan-type>/prompts/`
3. Add node library to `files/planning/<new-plan-type>/node-library/`
4. Register in `registry.jsonc`
5. Run `npm run build && npm run deploy`

### To Tweak Model Assignment
Edit: `files/profiles/<profile>/opencode.jsonc`
- Change `agent.<agent-name>.model` to a different model
- Rebuild and redeploy to activate

---

## Known Issues & Quirks

### grepai Index Pollution
If search results degrade on a user's machine:
```bash
rm -rf .grepai/
```
ZeptoCode rebuilds the index automatically. Per-session isolation is in progress.

### Model Selection for Ollama Profile
- **Gemma 4 4B**: Reference model (slow but works)
- **Recommended: Qwen 3 14B Q4_K_M** (~9–10 GB VRAM): Best balance of speed and reliability
- **Minimum**: Qwen 2.5 14B (97.1% tool-calling F1)
- **Do NOT use 70B+** — zero VRAM for KV cache

See `files/profiles/ollama/opencode.jsonc` lines 24–40 for full model guide.

### KV Cache Optimization (Ollama)
```bash
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_FLASH_ATTENTION=1
ollama serve
```
Cuts context VRAM by ~50%.

### Temperature Settings for Ollama
- **--temp 0.2, --top-p 0.95, --top-k 64** ensure tool calls are reliable and DAG is followed exactly
- **--reasoning on** (gemma4 only) enables built-in chain-of-thought

---

## Deployment & Distribution

### Build for Distribution
```bash
npm run build
```
Generates `./dist/` with:
- Component files in `dist/components/`
- Registry manifest `dist/index.json`
- Static assets for `.well-known/`

### Deploy to Cloudflare Workers
```bash
npm run deploy
```
- Requires `wrangler` auth
- Publishes registry to OCX-compatible endpoint
- User can then `ocx profile add` profiles from this registry

### Profile Registration (Post-Deploy)
After `npm run deploy`, users run (approximately):
```bash
ocx profile add naga-ollama --global --source naga-group/ocx-ollama
```

To bulk-update all profiles on a machine, run the maintenance script:
```bash
bash scripts/update-profiles.sh
```
(Removes old profiles, re-adds from registry, clears cached plugin)

---

## Plugin Development Notes

### When to Rebuild
- **Always** after editing `files/agents/*.md` or `files/commands/*.md`
- **Always** after editing `files/planning/*/plan.jsonl`
- **Only if source code changes**: `files/plugins/*.ts`

### Plugin Entry Point
`files/plugins/planning-enforcement.ts`:
- Exports `PlanningEnforcementPlugin` async factory
- Registers tools (session, navigation, planning, grepai)
- Registers hooks (before, after, session-specific)
- Manages DAG lifecycle and turn-level state

### Tool Modules
Located in `files/plugins/modules/tools/`:
- Session tools: DAG activation, plan management
- Navigation tools: DAG traversal, step progression
- Planning tools: DAG creation, schema validation
- Grepai tools: Semantic search integration

### Hooks
Located in `files/plugins/modules/hooks/`:
- `session-hooks.ts`: Session state, chat params, compacting
- `tool-after-hooks/next-step.ts`: Post-tool DAG advancement
- `before-hook`, `after-hook`: Global tool lifecycle

---

## When to NOT Edit

- **Do not manually edit** `planning/plan-session/node-library/` unless you understand the schema — use tooling instead
- **Do not create new agent files** without adding them to both `registry.jsonc` **and** profiles
- **Do not hand-edit `dist/`** — always regenerate via `npm run build`
- **Do not change `schema_version` in plan.jsonl** without updating all DAG read/write code

---

## Testing & Validation

### Verify Build
```bash
npm run build
# Check dist/ is populated
ls -la dist/components/
```

### Verify Config Syntax
- OCX config files: validate against `$schema` URLs in `.jsonc` files
- Plan JSONL: runs through `phase-io.ts` parsers on load

### No Automated Test Suite
- Config and DAG validity are checked at **runtime** by OpenCode
- To test locally, you need a live OpenCode + Ollama/API setup
- See README.md Setup section for prerequisites

---

## Useful Commands Reference

| Command | Purpose |
|---------|---------|
| `npm run build` | Bundle plugin + build dist |
| `npm run deploy` | Deploy dist to Cloudflare Workers |
| `npm run dev` | Local dev (hotload, not production) |
| `bash scripts/update-profiles.sh` | Bulk refresh all installed profiles on user's machine |
| `rm -rf .grepai/` | Reset grepai index (run in target project, not this repo) |

---

## Links

- **OpenCode**: https://opencode.ai
- **OCX Registry Schema**: https://ocx.kdco.dev/schemas/v2/registry.json
- **Demo**: https://youtu.be/s7YQCgxsuO4
- **README**: Covers setup, profiles, usage, known issues in detail
