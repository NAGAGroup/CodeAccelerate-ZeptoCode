# Prompt Optimization System Specification

## (1) Overview and Goals

**Goal:** Deliver a fully autonomous, generic end-to-end (E2E) prompt optimization system for ZeptoCode, targeting **gemma4:4b** as the minimum viable local model. The system optimizes the text of DAG node prompts and agent system prompt behavioral sections, enabling a 4B-parameter local model to reliably execute complex multi-step agentic workflows.

**Optimization Scope:**
- Node-level prompts: `files/planning/plan-session/node-library/*/prompt.md` (execution optimization only)
- Agent behavioral sections: `files/agents/*.md` Markdown body text (execution optimization only; planning optimization keeps these fixed)
- Planning workflow prompts: `files/planning/plan-session/prompts/*.md` (planning optimization only; agent prompts are fixed)

**Scenario-Driven Approach:** The system runs standardized optimization scenarios—pairs of (dummy project, DAG plan)—through OpenCode headlessly, scores session transcripts via LLM judge, and iteratively refines prompts via genetic-Pareto optimization.

**Generic by Design:** No lock-in to any specific project type, DAG structure, or programming language. All scenarios are declared via manifest files; adding a new scenario requires zero harness code changes.

---

## (2) System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        GEPA Optimizer                            │
│  (Genetic-Pareto Reflective Evolution / Frontier LLM Feedback)   │
└──────────────────────────┬───────────────────────────────────────┘
                           │ proposes mutated prompts
                           ▼
        ┌──────────────────────────────────────┐
        │   Write Mutations to Repository      │
        │  - Overwrite *.md prompt files      │
        │  - Overwrite agent behavioral text  │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │   Sync to OpenCode Config (~/.config)│
        │  - cp files/planning/* ~/ ...        │
        │  - cp files/agents/* ~/ ...          │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  OpenCode Server Launch              │
        │  $ ocx opencode -p naga-ollama ...   │
        │  Port: 4096 (configurable)           │
        │  LM: gemma4:4b via Ollama            │
        └──────────────┬───────────────────────┘
                       │
          ┌────────────┴────────────┐
          │ HTTP API                 │
          │ POST /session            │
          │ POST /session/:id/message│
          │ GET /session/:id/message │
          │ DELETE /session/:id      │
          ▼                          ▼
    ┌─────────────────────────────────────────┐
    │   ZeptoCode Plugin (Inside OpenCode)    │
    │  ┌────────────────────────────────────┐ │
    │  │ Executes DAG Phases Sequentially   │ │
    │  │ - entry-phase (execution-kickoff) │ │
    │  │ - deliberate (non-branching)       │ │
    │  │ - implement-code (work + verify)   │ │
    │  │ - author-documentation             │ │
    │  │ - finish (context storage)         │ │
    │  │                                    │ │
    │  │ Reads/Writes:                      │ │
    │  │ - Qdrant (session memory)          │ │
    │  │ - Project files (codebase)         │ │
    │  └────────────────────────────────────┘ │
    └─────────────────────────────────────────┘
                       │
                       │ Session Transcript
                       ▼
        ┌──────────────────────────────────────┐
        │  LLM Judge (Frontier Model)          │
        │  Reads: Full session transcript      │
        │  Outputs: {score, feedback}          │
        │  Score: [0.0, 1.0] (0 = hung)        │
        │  Feedback: Natural language diagnosis│
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  Score + Feedback to GEPA            │
        │  (Closes loop; informs next mutation)│
        └──────────────┬───────────────────────┘
                       │
                       │ git reset --hard
                       │ (restore repo + Qdrant)
                       ▼
        ┌──────────────────────────────────────┐
        │  Baseline Reset                      │
        │  - Restore files/planning/* to git   │
        │  - Restore files/agents/* to git     │
        │  - Restore Qdrant data dir to commit │
        │  → Eliminates cross-run contamination│
        └──────────────────────────────────────┘
                       │
                       │ next GEPA generation
                       ▼
                   [LOOP BACK]
```

---

## (3) Scenario Structure

A **scenario** is a (project, DAG) pair. A single project can host multiple scenarios, each with a distinct purpose and execution model.

### Scenario Types

1. **`execution`** — Linear DAGs only; no branching; `deliberate` phases allowed with `is-branch=false`; directly runnable by the optimization loop; produces clean, comparable signal.
2. **`planning`** — Complex DAGs with collaborate, deliberate, and branching; **NOT run** by the optimization loop; used as plan quality evaluation targets only (frontier model generates candidate plans against this reference).

### Physical Layout

```
optimization-scenarios/
└── <project-name>/
    ├── manifest.yaml                    ← scenario registry for this project
    ├── AGENTS.md                        ← project-specific agent constraints
    ├── <project source files>           ← actual codebase
    └── .opencode/
        └── session-plans/
            └── <scenario-name>/
                └── phase-plan.toml      ← git-tracked DAG source (TOML)
```

**Example:**
```
optimization-scenarios/cpp-greenfield-project/
├── manifest.yaml
├── AGENTS.md
├── CMakeLists.txt
├── pixi.toml
├── app/
│   └── main.cpp
└── .opencode/
    └── session-plans/
        └── cpp-fmt-argparse/
            └── phase-plan.toml
```

### manifest.yaml Schema

A YAML file listing all scenarios for a project, each with exactly two fields:

```yaml
scenarios:
  - name: cpp-fmt-argparse
    type: execution
  - name: cpp-tui-widget-library
    type: planning
```

- `name` (string) — scenario name; implicitly defines path `.opencode/session-plans/<name>/phase-plan.toml`
- `type` (`execution` | `planning`) — scenario classification

### Scenario Discovery and TOML as Source of Truth

- **TOML is the source of truth** for DAG structure. `plan.jsonl` is compiled at runtime from TOML and is **not** tracked in git.
- The optimization harness discovers scenarios by scanning for `manifest.yaml` files across all project directories under `optimization-scenarios/`.
- **Adding a new scenario** requires only:
  1. Creating the project directory (or adding to an existing project)
  2. Adding an entry to `manifest.yaml`
  3. Generating the TOML via `/plan-session` with a frontier model
  4. Committing to git (including Qdrant snapshot for execution scenarios — see §8)

---

## (4) OpenCode Headless API Integration

ZeptoCode runs as a plugin inside OpenCode. The optimization harness interacts with OpenCode **externally** via its HTTP API; ZeptoCode itself is not directly instrumented.

### Server Launch

```bash
ocx opencode -p naga-ollama --dangerously-skip-permissions [--port N]
```

- `ocx` — OpenCode CLI launcher
- `-p naga-ollama` — selects the naga-ollama profile (gemma4:4b via Ollama)
- `--dangerously-skip-permissions` — prevents runtime permission prompts from blocking headless runs
- `[--port N]` — optional port configuration (default: 4096)

**Profile source:**
- Repo: `files/profiles/ollama/opencode.jsonc`
- Installation path: `~/.config/opencode/profiles/naga-ollama/` (via OCX; profile name chosen to prevent clashes)

### Session Lifecycle

1. **Create session:** `POST /session` → returns `{id: string, ...}`
2. **Send kickoff message:** `POST /session/:id/message` with body `{parts: [{type: "text", text: string}]}`
   - Blocking call; waits for initial response
   - Kicks off the scenario's DAG execution
3. **Poll for completion:** `GET /session/:id/message` → returns array of new messages (if any)
   - Poll periodically (e.g., every 2–5 seconds)
   - **Completion detection:** If no new messages appear for **60 seconds**, treat run as complete (or hung)
4. **Cleanup:** `DELETE /session/:id` → closes session; `kill` server process

### Permission Handling

- **Primary mechanism:** `--dangerously-skip-permissions` at server launch prevents permission prompts from blocking execution
- **Fallback:** `POST /session/:id/permissions/:permissionID` with body `{response: bool, remember?: bool}` (used if a runtime permission is still encountered; not recommended for fully autonomous runs)

### Authentication

- **HTTP Basic Auth:** Configured via environment variables:
  - `OPENCODE_SERVER_USERNAME` (optional; defaults to "user")
  - `OPENCODE_SERVER_PASSWORD` (required if auth is enabled)

### Default Configuration

- **Port:** 4096 (configurable via `--port`)
- **Idle timeout:** 60 seconds with no new messages → run declared complete
- **Hung runs:** Receive a score of **0.0**

### Additional Features (Available but Not Primary)

- **SSE stream:** `GET /event` provides real-time async event stream (available but not used as primary completion detection)
- **Plugin/MCP tools:** Fully available in headless mode; no limitations documented

---

## (5) DSPy Module Design

ZeptoCode DAG execution is wrapped as a `dspy.Module` subclass that drives OpenCode sessions externally via HTTP.

### Module Interface (Conceptual)

```python
class ZeptocodeModule(dspy.Module):
    def forward(
        self,
        scenario: dict,           # {project_path: str, dag_name: str}
        prompt_set: dict[str, str] # {filename: mutated_content}
    ) -> dspy.Prediction:
        """
        Returns: Prediction with 'score' [0.0, 1.0] and 'feedback' (str)
        """
```

### Behavior

- **Black box to GEPA:** GEPA only observes inputs and outputs (`{score, feedback}`); cannot inspect internal OpenCode execution details
- **Atomicity:** Each forward pass:
  1. Writes mutated prompts to disk
  2. Syncs to OpenCode config
  3. Launches OpenCode server (headless)
  4. Creates session, sends kickoff message, polls for completion
  5. Captures full session transcript
  6. Submits transcript to LLM judge for scoring
  7. Cleans up (session, server, git reset)
  8. Returns `{score, feedback}`

### DSPy LM Configuration for gemma4:4b

```python
dspy.LM(
    'ollama_chat/gemma4:4b',
    api_base='http://localhost:<OPENCODE_OLLAMA_PORT>/v1',
    api_key=''
)
```

- **Port:** Controlled by `OPENCODE_OLLAMA_PORT` environment variable
- **Provider:** LiteLLM (underlying DSPy LM implementation) supports Ollama and OpenAI-compatible endpoints natively

---

## (6) GEPA Integration

**Optimizer:** `dspy.GEPA` (ICLR 2026 Oral — Genetic-Pareto Reflective Evolution)

### Why GEPA

- Outperforms MIPROv2 by 10%+ in multi-step agentic compound AI systems
- Requires 35× fewer rollouts than reinforcement learning
- Native Pareto frontier convergence (no external budget or plateau threshold required)
- Built specifically for mutating system prompts of agentic workflows

### Reflection and Mutation

- **Reflection LLM:** Claude Sonnet (frontier model) serves as GEPA's internal mutation proposer
  - Reads: GEPA's current generation score history + DSPy Module's feedback string
  - Proposes: Targeted textual mutations to candidate prompts
  - Cost: Per generation (not per rollout; much cheaper than RL alternatives)
- **Termination:** GEPA native Pareto frontier convergence (automatic, no external thresholds)

---

## (7) Mutable Prompt Surface

### Execution Optimization

Runs first; agent behavioral sections and node prompts are both mutable.

**Tier 1 — Node Prompts (Primary):**
- All prompt files across all phase types in `files/planning/plan-session/node-library/*/prompt.md`
- Phase types: `entry-phase`, `implement-code`, `deliberate`, `collaborate`, `author-documentation`, `finish`
- **Approximately 22 prompt files** (exact count depends on node distribution across phases)

**Tier 2 — Agent Behavioral Sections (Secondary):**
- Markdown body text in all agent role definition files: `files/agents/*.md`
- **8 agent files:** `headwrench.md`, `junior-dev.md`, `tailwrench.md`, `context-scout.md`, `context-insurgent.md`, `external-scout.md`, `documentation-expert.md`, `deep-researcher.md`
- **Fixed:** YAML frontmatter and permission blocks (never mutated)

**Never Mutated (Execution Optimization):**
- `files/planning/plan-session/node-library/*/node-spec.json` (enforcement arrays)
- `files/planning/plan-session/node-library/*/phase-schema.toml` and `phase-spec.jsonl`
- Plan-level template variables (`{{IMPLEMENT_INSTRUCTIONS}}`, `{{VERIFY_INSTRUCTIONS}}`, etc.) — these are scenario-specific inputs, not system behavior

### Planning Optimization

Runs after execution optimization converges; only planning workflow prompts are mutable.

**Mutable Surface:**
- All 6 files in `files/planning/plan-session/prompts/*.md`:
  - `session-overview.md`
  - `orientation-scout.md`
  - `external-research.md`
  - `draft-plan.md`
  - `store-notes.md`
  - `plan-success.md`

**Fixed (Planning Optimization):**
- All `files/agents/*.md` system prompts (frozen to their optimized state from execution optimization)
- All `files/planning/plan-session/node-library/*/prompt.md` (unchanged from execution optimization result)

### Highest-Leverage Execution Targets (Priority Order)

1. `implement-code/verify-work-item/prompt.md` — drives PASS/FAIL gate signal quality
2. `implement-code/junior-dev-triage/prompt.md` — drives recovery efficiency; root-cause autonomy
3. `implement-code/junior-dev-work-item/prompt.md` — drives implementation quality; context integration
4. `entry-phase/execution-kickoff/prompt.md` — orients agent to plan context; Qdrant query structure
5. `headwrench.md` (behavioral body) — gatekeeping rigor, prescriptiveness, recovery behavior
6. `junior-dev.md` (behavioral body) — search depth, change scope, validation strictness, retry limits

---

## (8) Evaluation Metric Design

### Metric Type: LLM-as-Judge (Generic Agentic Quality)

- **Rationale:** The framework must be generic across all project types. Project-specific cost functions (build pass/fail, test success, format checks) would optimize for the specific scenario, not for generic agentic capability. The C++ scenario is a vehicle for exercising agents, not the optimization target itself.
- **Judge:** Frontier model (Claude Sonnet or equivalent) reads the full session transcript
- **No project-specific checks:** No build commands, format verification, test runners, or domain-specific artifacts

### Evaluation Criteria (Generic Agentic Quality)

Applied uniformly to any project type:

| Criterion | Description |
|-----------|-------------|
| **Reasoning Quality** | Are decisions coherent? Do steps follow logically? Is the agent's thinking transparent? |
| **Tool Call Discipline** | Correct sequencing of tool invocations? No hallucinated calls? Tool parameters sound? |
| **Scope Adherence** | Does the agent stay within the stated task? No feature creep or scope reduction without justification? |
| **Step Completion Signal** | Does each DAG node produce clear evidence of completion before proceeding? |
| **Recovery Behavior** | Does triage/recovery happen autonomously without being pre-specified? Is root-cause discovery genuine? |
| **Context Threading** | Do early-phase decisions correctly propagate to later phases? Is Qdrant context correctly retrieved and applied? |

### Philosophy

**Conservative correctness over completion rate:** A clean early exit (e.g., Phase N fails after retries and terminates gracefully with a clear error summary) scores higher than a dirty completion (scope creep, hallucinated success, constraint violations, false confidence).

### Score Format

```json
{
  "score": 0.75,
  "feedback": "Strong context threading; deliberation decisions correctly applied in implementation. Triage autonomy present. Verify node signal clean. Minor: over-prescriptive in recovery phase 3 triage — agent asked for too much guidance before attempting root-cause discovery."
}
```

- **score** — float in [0.0, 1.0]
- **feedback** — natural language diagnosis, fed directly into GEPA's reflective mutation input
- **Hung runs** (idle timeout exceeded) — score = 0.0

---

## (9) Optimization Loop (End-to-End Flow)

### Per-Candidate Run Sequence

1. **GEPA proposes** a mutated prompt set (candidate)

2. **Write mutations to repo:**
   - Overwrite affected `files/planning/plan-session/node-library/*/prompt.md` files
   - Overwrite affected `files/agents/*.md` behavioral sections (Markdown body only; keep frontmatter/permissions intact)

3. **Sync to OpenCode config:**
   ```bash
   cp -r files/planning/* ~/.config/opencode/planning
   cp -r files/agents/* ~/.config/opencode/profiles/naga-ollama/agents
   ```
   *(Steps 2 and 3 are synchronous — `cp` completes before server launch)*

4. **Launch server:** `ocx opencode -p naga-ollama --dangerously-skip-permissions --port <N>`

5. **Create session:** `POST /session`

6. **Send kickoff message:** `POST /session/:id/message` with body:
   ```json
   {
     "parts": [
       {
         "type": "text",
         "text": "<scenario's activation prompt>"
       }
     ]
   }
   ```

7. **Poll for completion:** `GET /session/:id/message` — check for new messages every N seconds
   - If no new messages for **60 seconds**, run is complete (or hung)

8. **Score:** Frontier LLM judge reads full session transcript → `{score, feedback}`

9. **Cleanup:**
   - `DELETE /session/:id`
   - Kill server process

10. **Reset baseline:**
    ```bash
    git reset --hard
    ```
    - Restores all `files/planning/*` to committed state
    - Restores all `files/agents/*` to committed state
    - Restores Qdrant data directory to committed snapshot
    - Eliminates all cross-run contamination

11. **Repeat** from step 1 with next GEPA candidate

### Qdrant State Management

- Each scenario's Qdrant collection (planning context from the frontier-model planning run) is **committed to git** alongside the TOML
- `git reset --hard` after each run restores both the prompt files **and** the Qdrant data directory to the committed baseline
- This is the **sole isolation mechanism** — no separate snapshot/restore tooling required

### Loop Termination

GEPA native Pareto frontier convergence (automatic; no external budget or plateau condition)

---

## (10) Execution vs Planning Optimization Ordering

### Execution Optimization Runs First

**Ordering constraint:** Planning optimization cannot begin until execution optimization has converged.

**Rationale:** Planning prompt quality depends on agent behavior correctness. If agent prompts (`files/agents/*.md`) are still being mutated during planning optimization, the signal is confounded — it becomes impossible to distinguish planning prompt quality from agent behavior quality.

**Handoff Mechanism:**
1. Execution optimization runs until GEPA frontier converges
2. All optimized agent prompts are committed to git
3. Agent prompts are **frozen** for planning optimization
4. Planning optimization begins with `files/planning/plan-session/prompts/*.md` as the sole mutable surface
5. Agent prompts remain at their execution-optimization-optimized state (fixed input to planning optimizer)

### Mutable Surfaces by Phase

| Phase | Mutable Surface | Fixed | Rationale |
|-------|---|---|---|
| **Execution Optimization** | Node prompts (Tier 1) + Agent behavioral sections (Tier 2) | Node specs, YAML frontmatter, template variables | Both surface types affect execution quality |
| **Planning Optimization** | Planning workflow prompts only | Agent prompts, node prompts, node specs | Agent behavior must be stable to isolate planning quality |

---

## (11) Branching Phase Inference Strategy

### Why Branching Phases Are Not Directly Optimized

- `collaborate` and `deliberate` phases with branching (`is-branch=true`) are **NOT directly optimized** by the GEPA loop
- **Reason:** Branching DAG execution is non-deterministic; running branching scenarios through the optimization loop produces noisy, non-comparable signal across GEPA generations
- **Solution:** Branching phases are optimized via post-hoc inference after execution optimization converges

### Execution Scenarios Design Constraint

- Execution scenarios **exclude branching entirely**
- `deliberate` phases allowed only with `is-branch=false` (linear decision gates)
- Only `collaborate` phases are allowed with `is-branch=true`, but they are NOT primary optimization targets

### Inference Mechanism (Post-Hoc, After Execution Optimization Converges)

1. A frontier LLM (Claude Sonnet) reads:
   - The optimized prompt diffs (before vs after GEPA)
   - The full GEPA feedback history across all generations
2. It produces targeted **proposed changes** to `collaborate` and `deliberate` phase node prompts
3. A human reviews and approves the proposed changes
4. Changes are committed to git (and integrated into the frozen agent/node prompts for subsequent planning optimization)

**This is the bridge** between linear execution optimization and the branching phase prompts that cannot be directly optimized via the headless loop.

---

## (12) Genericity Requirements

The system must not be locked to any specific DAG structure, project type, or programming language.

### Scenario Discovery

- **Manifest-based:** The harness scans `optimization-scenarios/*/manifest.yaml` and enumerates all declared scenarios
- **Zero hardcoding:** Scenarios are defined via `manifest.yaml` entries; adding a scenario requires zero harness code changes

### Adding a New Scenario

1. Create project directory under `optimization-scenarios/<project-name>/`
2. Add entry to `manifest.yaml` with `name` and `type` (`execution` or `planning`)
3. Generate initial TOML via `/plan-session` with frontier model
4. Commit to git (including Qdrant snapshot for execution scenarios)
5. **No harness code changes required**

### Metric Function Genericity

- The metric function evaluates **generic agentic quality criteria** (reasoning, tool discipline, scope adherence, recovery autonomy, context threading)
- These criteria apply uniformly to any scenario (C++, Python, Rust, documentation tasks, etc.)
- No project-specific outcome checks are needed

### DAG Structure Genericity

- DAG structure is not hardcoded in the harness
- Harness reads whatever TOML is declared in the manifest
- TOML is compiled to JSONL at runtime via ZeptoCode's existing schema validators

### Branching Type Declaration

- `execution` vs `planning` branching type is explicitly declared in `manifest.yaml`
- Not inferred from DAG structure; prevents ambiguity

---

## (13) Out of Scope

The following are explicitly excluded from the prompt optimization system:

- **Direct instrumentation of ZeptoCode plugin internals** — all optimization is external via HTTP API
- **Optimization of branching phases via the GEPA loop** — collaborate/deliberate phases with branching are handled by post-hoc inference only
- **Planning optimization before execution optimization converges** — strict ordering constraint
- **Models larger than ~14B parameters** — 70B+ excluded due to VRAM constraints; gemma4:4b is the sole target
- **Non-Ollama proxy models as optimization target** — gemma4:4b is the target; Haiku and other non-local models not supported
- **In-session prompt injection via the `system` field** — write-to-disk is the sole injection mechanism
- **Automated modification of `node-spec.json` enforcement arrays or `phase-schema.toml` / `phase-spec.jsonl`** — these remain immutable

---

**End of optimization-system-spec.md**
