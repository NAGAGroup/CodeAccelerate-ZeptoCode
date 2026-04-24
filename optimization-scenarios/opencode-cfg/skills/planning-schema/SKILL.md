---
name: planning-schema
description: Phase types, field schemas, and naming conventions for writing executable plans in TOML format.
---

## collaborate

Engages the user in discussion, research, and decision-making. Can branch if the outcome determines different execution paths.

```toml
[[phases]]
id = <phase-id>
type = "collaborate"
next = [<child-id>]
is-branch = false
discussion-topics = ["...", ...]
planning-context = ["...", ...]
project-survey-instructions = ["...", ...]
web-search-instructions = ["...", ...]
project-analysis-instructions = ["...", ...]
```

### Core fields

- **discussion-topics** — what to discuss with the user: requirements, preferences, tradeoffs, decisions. When `is-branch = true`, branch names must be concrete named options.
- **planning-context** — why this phase exists and what prior findings informed it. Gives executing agents the "why" behind the work.

### Pre-discussion fields

These compile into pre-phase steps that run before the discussion begins in the following order.

- **project-survey-instructions** — codebase areas to survey for broad orientation relevant to the discussion.
- **web-search-instructions** — external research to inform the discussion: landscape surveys, feature comparisons, ecosystem overviews.
- **project-analysis-instructions** — specific codebase mechanisms to deeply analyze before the discussion.

---

## deliberate

Agent independently reasons, researches, and makes decisions. Same role as `collaborate` but without user involvement.

```toml
[[phases]]
id = <phase-id>
type = "deliberate"
next = [<child-id>]
is-branch = false
deliberation-instructions = ["...", ...]
planning-context = ["...", ...]
project-survey-instructions = ["...", ...]
web-search-instructions = ["...", ...]
project-analysis-instructions = ["...", ...]
```

### Core fields

- **deliberation-instructions** — what to reason through: evaluations, tradeoffs, decisions. When `is-branch = true`, branch names must be concrete named options.
- **planning-context** — why this phase exists and what prior findings informed it.

### Pre-deliberation fields

These compile into pre-phase steps that run before the deliberation begins in the following order.

- **project-survey-instructions** — codebase areas to survey for broad orientation relevant to the deliberation.
- **web-search-instructions** — external research to inform the deliberation: technical comparisons, best practices, ecosystem options.
- **project-analysis-instructions** — specific codebase mechanisms to deeply analyze before deliberating.

---

## implement-code

Researches, sets up, implements, and verifies code. Includes automatic triage retries on failure.

```toml
[[phases]]
id = <phase-id>
type = "implement-code"
next = [<child-id>]
planning-context = ["...", ...]
project-survey-instructions = ["...", ...]
web-search-instructions = ["...", ...]
project-analysis-instructions = ["...", ...]
setup-instructions = ["...", ...]
implement-instructions = ["...", ...]
verify-instructions = ["...", ...]
constraints = ["...", ...]
```

### Core fields

- **planning-context** — why this phase exists and what prior findings informed it.
- **setup-instructions** — project setup only: dependency installation, build system configuration, config file changes, scaffolding directory structures. No code implementation belongs here.
- **implement-instructions** — code implementation only: writing source code, modifying existing source files, adding tests. No project setup belongs here.
- **verify-instructions** — concrete success criteria: build commands, test commands, visual checks, expected outputs. The executing agent uses exactly what you write here.
- **constraints** — invariants that must hold even during triage and retries. The executing agent checks these alongside verification.

**Project Setup Mandate:** `setup-instructions` *must* be used if there are any project setup steps that need to take place before implementation. The `implement-instructions` field is strictly for code implementation steps. This separation allows the executing agent to perform all necessary setup before any code changes, which is crucial for ensuring a smooth implementation process and avoiding issues that can arise from interleaving setup and implementation steps.

### Pre-work fields

These compile into pre-phase steps that run before any implementation begins in the following order.

- **project-survey-instructions** — codebase areas to survey for broad orientation relevant to the implementation.
- **web-search-instructions** — external research needed for the work: API docs, integration guides, user guides, best practices.
- **project-analysis-instructions** — specific codebase mechanisms to deeply analyze before implementation.

---

## author-documentation

Researches, plans, and writes documentation.

```toml
[[phases]]
id = <phase-id>
type = "author-documentation"
next = [<child-id>]
planning-context = ["...", ...]
project-survey-instructions = ["...", ...]
web-search-instructions = ["...", ...]
project-analysis-instructions = ["...", ...]
authoring-instructions = ["...", ...]
constraints = ["...", ...]
```

### Core fields

- **planning-context** — why this phase exists and what prior findings informed it.
- **authoring-instructions** — what to write, covering scope, structure, and content expectations.
- **constraints** — style, scope, or content constraints.

### Pre-work fields

These compile into pre-phase steps that run before any authoring begins in the following order.

- **project-survey-instructions** — codebase areas to survey for broad orientation relevant to the documentation.
- **web-search-instructions** — external research: documentation conventions, reference material, style guides.
- **project-analysis-instructions** — specific codebase mechanisms to deeply analyze for accurate documentation.

---

## finish

Planned completion or exit point. Documents what was accomplished or why execution stopped. Generic, all pre-exit phases can use the same finish phase instance.

```toml
[[phases]]
id = <phase-id>
type = "finish"
next = []
```

