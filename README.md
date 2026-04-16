# CodeAccelerate-PicoCode
[![Demo](https://img.shields.io/badge/Watch_Demo-YouTube-red?style=flat-square&logo=youtube)](https://youtu.be/s7YQCgxsuO4)

> Autonomous multi-agent planning and execution for [OpenCode](https://opencode.ai) — running entirely on a 4-billion parameter model.

You describe a goal. PicoCode plans it, executes it, and ships it — locally, privately, with no cloud APIs required.

---

## What makes PicoCode different

**Agents build their own execution plans as structured DAGs — not flat task lists, not free-form reasoning chains.**

PicoCode uses a two-level planning system. A small, modular set of plan "phase types" (research, implement, decide, verify, exit) serves as the authoring vocabulary. A planning agent composes these phases into a typed execution DAG — with branches for decision-making, early exits for dead ends, merge points where paths converge, and user interaction gates where human judgment is needed. That DAG then compiles down to individual node prompts that specialist agents execute step by step.

This matters because:

- **Failure is a feature, not a bug.** Work phases include automatic verification and triage loops — but retries are bounded. When a phase exhausts its retry budget, it exits cleanly and documents exactly what failed and why. You come back from lunch and find the system stopped at a well-defined point, not a trail of hallucinated changes across your codebase. Even when things go wrong, the blast radius is scoped to a single phase — the plan as a whole can define a large feature, but no single failure corrupts more than the task that failed.
- **Everything is auditable.** The DAG is a concrete artifact — you can inspect the plan before execution starts, trace exactly which path was taken during execution, and pinpoint where things went wrong after the fact. No black-box chains of thought that silently change your codebase.
- **Plans are portable.** The DAG is model-agnostic. Plan with one model, execute with another. Plan with Sonnet for maximum reasoning quality, execute with gemma4 locally for zero cost. Or plan and execute both on gemma4 — it handles both.

The whole system runs on [gemma4:4be](https://ollama.com/library/gemma4) via Ollama or llama.cpp. Four billion parameters. One consumer GPU.

---

## What it does

```
/plan-session build a C++ ASCII art library that prints to stdout
```

PicoCode will:

1. **Survey** your codebase to understand structure and conventions
2. **Research** external dependencies, frameworks, and integration approaches
3. **Plan** an execution DAG with work items, decision gates, and exit points
4. **Execute** each phase — delegating to specialist agents that edit code, run builds, search the web, and verify results
5. **Recover** from failures automatically — verification failures trigger triage, which diagnoses and fixes before retrying

---

## The agent team

| Agent | Role | Tools |
|---|---|---|
| **headwrench** | Orchestrator — follows the DAG, delegates to specialists, never touches code | `qdrant`, `task`, `question`, `next_step` |
| **junior-dev** | Implements code changes via targeted file edits | `grepai`, `filesystem`, `web search` |
| **tailwrench** | Verification expert, no edits, just checks work | `bash`, `read` |
| **context-scout** | Broad codebase survey for orientation | `grepai`, `filesystem` |
| **context-insurgent** | Deep, narrow analysis of specific code mechanisms | `grepai`, `filesystem` |
| **external-scout** | Web research with confidence-tagged findings | `web search` |
| **documentation-expert** | Writes and updates documentation | `grepai`, `filesystem` |

---

## Plan phases

Plans are DAGs composed of typed phases:

| Phase | Purpose |
|---|---|
| `implement-code` | Research, implement, verify, and retry — bundles pre-work survey, web search, deep analysis, setup, implementation, and verification into a single phase with automatic triage loops |
| `author-documentation` | Self-explanatory |
| `web-search` | External research to inform decisions — does not satisfy pre-work research within `work` phases |
| `user-discussion` | Open-ended discussion with the user (linear, no branching) |
| `user-decision-gate` | User chooses between execution branches |
| `agentic-decision-gate` | Agent routes between branches based on evidence |
| `write-notes` | Checkpoint — documents findings, decisions, context |
| `early-exit` | Planned stopping point with handoff context |

---

## Prerequisites

- [OpenCode](https://opencode.ai) — `npm install -g opencode-ai`
- [OCX](https://ocx.sh) — `npm install -g ocx` (OpenCode extension manager)
- [grepai](https://yoanbernabeu.github.io/grepai/installation/) — semantic codebase search
- [Ollama](https://ollama.com) — for grepai embeddings and the local profile
- [Docker](https://docker.com) — for Qdrant (session memory) and SearXNG (web search)
- Node.js 18+ with `npx`
- Python with `uvx` (for the Qdrant MCP server)

---

## Setup

### 1. Start background services

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
docker run -d --name searxng -p 8080:8080 searxng/searxng
ollama pull gemma4:4be
```

### 2. Install PicoCode

```bash
npx ocx init --global
npx ocx registry add https://ocx-registry.nagagroup.workers.dev --name naga-group --global
npx ocx profile add naga-ollama --global --source naga-group/ocx-ollama
npx ocx add --global naga-group/ocx-planning-plugin
```

### 3. Verify grepai

```bash
grepai version
```

PicoCode manages grepai automatically per project — no manual init or watch commands needed. The first session on a new project takes slightly longer while the index builds.

---

## Profiles

| Profile | Source | Headwrench | Subagents |
|---|---|---|---|
| **`naga-ollama`** | `naga-group/ocx-ollama` | gemma4:4be (local) | gemma4:4be (local) |
| `naga` | `naga-group/ocx-default` | Claude Sonnet | Claude Haiku |
| `naga-haiku` | `naga-group/ocx-haiku` | Claude Haiku | Claude Haiku |
| `naga-copilot` | `naga-group/ocx-copilot` | GitHub Copilot | GitHub Copilot |
| `naga-haiku-copilot` | `naga-group/ocx-haiku-copilot` | Claude Haiku | GitHub Copilot |
| `naga-free` | `naga-group/ocx-free` | Free tier | Free tier |

`naga-ollama` is the flagship — fully local, fully private, no API keys.

### Running with Ollama

```bash
ollama pull gemma4:4be
export OPENCODE_OLLAMA_PORT=11434
ocx oc -p naga-ollama
```

### Running with llama.cpp (recommended)

```bash
llama-server \
  -hf unsloth/gemma-4-E4B-it-GGUF:Q8_0 \
  --temp 0.8 --top-p 0.95 --top-k 64 \
  --alias opencode-model \
  --port 8000 \
  --reasoning on
```

```bash
export OPENCODE_OLLAMA_PORT=8000
ocx oc -p naga-ollama
```

The `--alias opencode-model` flag matches the profile's expected model name. The `--reasoning on` flag enables gemma4's built-in reasoning.

---

## Usage

### Plan

```
/plan-session <describe what you want to build or fix>
```

The planner will survey your codebase, research external dependencies, and produce an execution DAG. When planning completes, you'll see the plan diagram and an activation command.

### Execute

```
/activate-plan <plan-name>
```

Execution runs through the DAG automatically. Each phase dispatches the appropriate subagent. Verification failures trigger triage and retry.

---

## Known issues

**grepai index pollution** — grepai's incremental tracking accumulates stale entries over time. If search results degrade, reset the index:

```bash
cd your-project && rm -rf .grepai/
```

PicoCode rebuilds the index automatically on the next session. Per-session index isolation is being investigated.

---

## Demo

[![Watch the demo](https://img.shields.io/badge/Watch_Demo-YouTube-red?style=flat-square&logo=youtube)](https://youtu.be/s7YQCgxsuO4)

Full E2E planning and execution on gemma4:4be — planning, delegation, verification, triage, and recovery, all running locally.

---

## Part of CodeAccelerate

PicoCode is part of the [CodeAccelerate](https://github.com/nagagroup) collection — tools, libraries, and configurations published by NagaGroup.
