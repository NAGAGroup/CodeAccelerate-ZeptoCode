# Execution DAG Specification: `cpp-fmt-argparse`

## (1) Purpose and Scope

This DAG is the **first execution optimization scenario** for the ZeptoCode prompt optimization system. It is run end-to-end by the optimization harness against the `cpp-greenfield-project` scenario and produces clean, comparable signal across GEPA generations.

**Why this DAG:**
- Fully linear, non-branching execution (no topological variance across runs)
- Exercises core agent behaviors most critical for gemma4:4b: context threading across phases, deliberation→implementation→documentation coherence, build error recovery, and external dependency integration
- Genuine failure surfaces: CMake/build errors, CPM dependency resolution, include path errors, CLI argument mapping
- Stress-tests triage autonomy (root-cause discovery without pre-specification) in a realistic C++ development scenario

---

## (2) Target Scenario

### Scenario Identification

- **Scenario name:** `cpp-fmt-argparse`
- **Project:** `optimization-scenarios/cpp-greenfield-project/`
- **Project name (display):** cpp-demo-project v0.1.0

### Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Language** | C++ | C++23 (GNU extensions allowed; GCC 14.3.0) |
| **Build System** | CMake | ≥ 3.25 |
| **Package Manager** | Pixi | conda-forge (Quetz) |
| **Package Manager** | CPM | CMake Package Manager (already scaffolded) |
| **Compiler** | GCC | 14.3.0 |
| **Build Tool** | Ninja | (default via Pixi) |
| **Formatters/Linters** | clang-format, clang-tidy | (already in pixi.toml) |
| **Format Verification** | pixi run format | (checks formatting) |

### Current Project State

**main.cpp (10 lines):**
```cpp
#include <iostream>
#include <format>

int main() {
    auto msg = std::format("Hello, World!");
    std::print("{}\n", msg);
    return 0;
}
```

**Key facts:**
- Uses `std::format` and `std::print` from `<format>` and `<iostream>`
- No external dependencies
- CMakeLists.txt exists, build system is fully configured
- `cmake/CPM.cmake` is already present (line 8); `CPMAddPackage` calls can be added directly
- pixi.toml exists; all conda-forge dependencies managed via `pixi add`

### Project Constraints (from AGENTS.md)

All constraints are **non-negotiable and must be enforced at every phase:**

| Constraint | Details | Enforcement |
|---|---|---|
| **Pixi for all commands** | All builds, tests, formatting, runs via `pixi run` — never raw cmake or system calls | Every implementation phase must verify each command uses `pixi run` |
| **Pixi task arguments** | Positional only; never flags | No `--release`, `--debug` flags in pixi run statements |
| **Code quality order** | clang-format → build (non-negotiable) | Must run `pixi run format` before every build attempt |
| **Conda priority over CPM** | Use conda-forge (pixi) for packages available there | `fmt` must use pixi, not CPM |
| **GitHub dependencies via CPM** | Packages not on conda-forge must use CPM | `p-ranav/argparse` must use CPMAddPackage |
| **GitHub version pinning** | Always pin GitHub dependencies to specific commit/tag | CPMAddPackage must include version specification |

---

## (3) DAG Phase Composition

The DAG is **fully linear**. All `deliberate` phases use `is-branch=false`. No `collaborate` phases.

### Phase Sequence and Goals

| # | Phase Type | Node(s) Used | Goal | Context |
|---|---|---|---|---|
| 1 | `entry-phase` | `execution-kickoff` | Orient headwrench to the plan; retrieve full planning context from Qdrant; store execution context note for all downstream phases | Entry point; gates all subsequent work |
| 2 | `deliberate` (is-branch=false) | `deliberate` | **Decide:** fmt integration approach (conda-forge pixi vs cpp-fmt/fmt GitHub), module naming conventions, formatter API design (simple utility function vs class-based wrapper), file structure (single `.hpp`/`.cpp` pair vs separate files). Record all decisions in Qdrant for downstream reference. | Pre-implementation alignment; decisions inform Phase 3 |
| 3 | `implement-code` | `project-setup` → `junior-dev-work-item` → `verify-work-item` ↔ `junior-dev-triage` (retry loop as needed) | **Add fmt library:** Add `fmt` to `pixi.toml` via `pixi add fmt`, update `CMakeLists.txt` with `find_package(fmt CONFIG REQUIRED)` + `target_link_libraries(... fmt::fmt)`. **Implement formatter module:** New `.hpp`/`.cpp` files per Phase 2 design, exposing a clean API. **Replace std::format:** Update `main.cpp` to use the new formatter module instead of `std::format`. **Verify:** Build successfully (no CMake errors, no linker errors); clang-format passes; clang-tidy passes. | Core work; Phase 2 decisions drive all implementation choices |
| 4 | `author-documentation` | `author-documentation` | **Document fmt API:** Function signatures, input/output types, usage examples, error handling. **Design rationale:** Explain why this particular API shape was chosen (based on Phase 2 deliberation decisions). Document module file structure. | Captures design intent; depends on Phase 2 and Phase 3 artifacts |
| 5 | `deliberate` (is-branch=false) | `deliberate` | **Decide:** argparse integration approach (CPM with `p-ranav/argparse`, specific version/commit), which CLI arguments to expose (`--name`, `--count`, `--verbose`, etc.), how each argument maps to the Phase 3 formatter API, error handling strategy. Record decisions in Qdrant for Phase 6. | Pre-implementation alignment; Phase 6 depends on these decisions |
| 6 | `implement-code` | `junior-dev-work-item` → `verify-work-item` ↔ `junior-dev-triage` (retry loop as needed) | **Add argparse:** Add `CPMAddPackage("gh:p-ranav/argparse#<version>")` to `CMakeLists.txt` with proper version pinning. **Implement CLI layer:** Modify `main.cpp` to parse command-line arguments using argparse, map arguments to Phase 3 formatter module, handle user input validation. **Verify:** Build successfully; argparse correctly integrated; CLI works (test with `--help` and sample arguments); clang-format and clang-tidy pass. | Implementation driven by Phase 5 decisions; builds on Phase 3 formatter module |
| 7 | `author-documentation` | `author-documentation` | **Document CLI interface:** Available arguments, defaults, examples, error cases. Explain design decisions from Phase 5. **Cross-reference:** Mention how CLI arguments map to the formatter module API from Phase 4. | May not be reached if Phase 6 implementation fails and retries exhaust |
| 8 | `finish` | `write-notes` | Store final completion notes in Qdrant: summary of all deliberation decisions, implementation status (success/partial/failure), any blockers encountered, suggestions for follow-up work. | End of DAG; captures final state |

---

## (4) Optimization Targets

The following node prompts are exercised by this DAG and are **mutable during execution optimization:**

### Primary Optimization Targets (Ranked by Criticality)

| Node Prompt | Phase(s) | Why It Matters | Failure Modes It Stresses |
|---|---|---|---|
| **`implement-code/verify-work-item/prompt.md`** | 3, 6 | PASS/FAIL verdict clarity; branch routing correctness; signal quality. Verify node determines if Phase continues or enters retry loop. | Weak PASS/FAIL logic; ambiguous verdict; premature exit; incorrect branching to triage |
| **`implement-code/junior-dev-triage/prompt.md`** | 3, 6 | Recovery autonomy; root-cause discovery without pre-specification; verbatim error inclusion; prescriptiveness calibration. Triage decides if retry is viable or failure terminal. | Over-prescribed fixes ("fix CMake" when error is in source code); insufficient autonomy; missed root cause; circular retry loops |
| **`implement-code/junior-dev-work-item/prompt.md`** | 3, 6 | Implementation prompt quality; IMPLEMENT_INSTRUCTIONS delegation; context integration. Primary driver of work quality. | Poor context threading (Phase 2 decisions lost); weak instruction clarity; scope creep; constraint violations (missing `pixi run` calls) |
| **`implement-code/project-setup/prompt.md`** | 3 | Dependency setup instructions to junior-dev; pixi add correctness; CMakeLists.txt modification guidance. Gates Phase 3 success. | Missed pixi add step; incomplete CMakeLists.txt edits; linker flag errors |
| **`entry-phase/execution-kickoff/prompt.md`** | 1 | Qdrant query structure; planning context retrieval; execution context note format. Sets stage for all downstream phases. | Planning context not retrieved; Qdrant queries too narrow; execution context note missing or malformed |
| **`author-documentation/author-documentation/prompt.md`** | 4, 7 | Documentation delegation quality; how Phase 2/5 deliberation decisions are surfaced to doc writer; artifact integration. | Decisions not mentioned in docs; API examples incorrect; missing cross-references |
| **`deliberate/deliberate/prompt.md`** | 2, 5 | Quality of non-branching decision recording; how decisions are stored in Qdrant for downstream use. | Decisions not stored; insufficient detail for downstream phases; ambiguous decision wording |
| **`finish/write-notes/prompt.md`** | 8 | Completion note quality; self-containment of stored artifacts; summary of key decisions and outcomes. | Incomplete final summary; decisions not carried forward; no record of blockers |
| **`headwrench.md` (behavioral body)** | All | Gatekeeping rigor; prescriptiveness level; recovery behavior; failure escalation threshold. Orchestrates all phases; controls delegation quality. | Over-prescriptive instructions to junior-dev; weak failure detection; premature escalation |
| **`junior-dev.md` (behavioral body)** | 3, 6 | Search depth; change scope; validation strictness; retry cycle behavior; autonomy vs safety tradeoff. Drives implementation quality; handles retries. | Insufficient context search before implementation; scope creep; weak validation; infinite retry loops |

### Secondary Optimization Targets

- `context-scout.md` and `context-insurgent.md` (behavioral bodies) — code survey quality during Phase 3/6
- `external-scout.md` (behavioral body) — research capability if dependencies require external lookup (fmt and argparse APIs)

---

## (5) Key Failure Modes (Designed for Stress-Testing)

### Failure Mode 1: Triage Over-Prescription

**Scenario:** Phase 3 build fails with a linker error. Headwrench's triage node says: "The CMakeLists.txt is broken. Fix the target_link_libraries() call to include fmt::fmt."

**Bad outcome:** Junior-dev immediately tweaks CMakeLists.txt without investigating the actual error. The error was actually in the source code — a missing include statement for `fmt/core.h`. Triage wasted junior-dev's effort and did not discover the root cause.

**Good outcome:** Triage node says: "The build failed. Review the full error output, identify the component that is broken (CMake, compiler, linker, or source code), and propose a fix with justification." Junior-dev reads the error, discovers it's a linker error originating from a missing include in the source, fixes it independently, and retries.

**Optimization target:** `implement-code/junior-dev-triage/prompt.md` — must enable root-cause autonomy without pre-specifying the broken component.

### Failure Mode 2: Context Threading Loss

**Scenario:** Phase 2 deliberation decides: "Use a simple utility function approach: `std::string format_message(const std::string& msg)`. Store as `formatter.hpp` and `formatter.cpp`."

**Bad outcome:** Phase 3 implementation creates a class-based design instead (`class Formatter { ... }`). Phase 4 documentation describes the class design. Phase 6 implementation assumes the utility function API and passes wrong argument types to Phase 3 formatter.

**Good outcome:** Phase 3 implementation reads Phase 2 decisions from Qdrant, follows the utility function design exactly, implements `formatter.hpp`/`formatter.cpp` correctly. Phase 4 documentation references Phase 2 decisions and documents the utility function. Phase 6 implementation correctly calls the Phase 3 API with right argument types.

**Optimization target:** `entry-phase/execution-kickoff/prompt.md`, `deliberate/deliberate/prompt.md` — context storage and retrieval must be precise and complete.

### Failure Mode 3: CPM Integration Error (Phase 6)

**Scenario:** Phase 6 attempts to add argparse via CPMAddPackage. The initial version string is incorrect (e.g., missing `#` before commit hash). CMake fails to resolve the dependency. Triage node misidentifies the error as a build system issue when it's actually a CPM configuration error.

**Bad outcome:** Triage tells junior-dev to "update CMake version" instead of "fix CPMAddPackage version string." Junior-dev spins wheels in the wrong direction.

**Good outcome:** Triage reads the full CMake error, identifies it as a CPM resolution failure, and tells junior-dev: "Review the CPMAddPackage call; the version specifier may be malformed. Check the syntax and retry."

**Optimization target:** `implement-code/junior-dev-triage/prompt.md` — must include full error output in analysis; verbatim errors are critical.

### Failure Mode 4: Cross-Phase Artifact Handoff

**Scenario:** Phase 3 creates `formatter.hpp` with the API decided in Phase 2. Phase 6 needs to know the exact function signature to map CLI arguments correctly. If Phase 6 context retrieval (from Qdrant) doesn't include Phase 3 artifacts, Phase 6 implementation will guess at the API.

**Bad outcome:** Phase 6 guesses the formatter API incorrectly, writes code that compiles but has wrong type conversions.

**Good outcome:** Phase 6 context retrieval includes Phase 3 implementation details (the actual `formatter.hpp` signature), Phase 6 correctly maps CLI arguments to the actual API.

**Optimization target:** `entry-phase/execution-kickoff/prompt.md` — Qdrant context retrieval must surface all prior-phase artifacts, not just decisions.

---

## (6) Success Metric Definition

### Metric Type: LLM-as-Judge Only

- **No project-specific checks:** No build pass/fail gates, no format verification, no test runners
- **Rationale:** This DAG is a vehicle for exercising agent behaviors; the optimization target is generic agentic quality, not C++ build success
- **Judge:** Frontier model (Claude Sonnet or equivalent) reads the full session transcript

### Scoring Criteria (Generic Agentic Quality)

| Criterion | Description | Good Signal | Bad Signal |
|---|---|---|---|
| **Context Threading** | Did deliberation decisions (Phase 2, 5) get correctly retrieved and applied in downstream phases (3, 4, 6, 7)? | Phase 3/6 implementations cite Phase 2/5 decisions; docs reference deliberation rationale | Decisions ignored or misapplied; implementation diverges from deliberation |
| **Implementation Coherence** | Did Phase 3 and Phase 6 implementations align with their respective deliberation outputs? Are artifacts (API, module structure) consistent with design decisions? | Code matches deliberation decisions; Phase 4/7 docs accurately describe implementation | Code does not match decisions; design was changed ad-hoc during implementation |
| **Triage Autonomy** | Did triage nodes investigate root causes independently, or were they over-prescribed? | "Review error output and identify root cause" followed by genuine root-cause discovery | "Fix X" without investigation; triage pre-specifies the broken component |
| **Verify Signal Quality** | Did verify nodes produce clean PASS/FAIL decisions that correctly route to retry or continuation? | Clear PASS allows progression; clear FAIL routes to triage; ambiguous failures resolved | Weak verdicts; incorrect routing; false PASSes |
| **Tool Call Discipline** | Were tool calls sequenced correctly? No hallucinated calls? Correct parameters? | `pixi run` calls present; correct Qdrant queries; proper CMakeLists.txt edits | Raw cmake calls without pixi; wrong tool invocations; malformed parameters |
| **Scope Adherence** | Did implementation stay within the stated scope? Were constraints (pixi, clang-format, CPM) respected? | All constraints enforced; no extra features added; no scope creep | Constraint violations (missing pixi, skipped formatting, wrong tool); feature creep |
| **Error Recovery** | When errors occurred, did the agent recover gracefully or give up prematurely? | Retries attempted; root causes investigated; escalation only when necessary | Immediate escalation without investigation; circular retry loops; premature exit |
| **Cross-Phase Artifact Handoff** | Did Phase 6 correctly retrieve Phase 3 artifacts (formatter API)? Did documentation (Phase 4/7) correctly reference prior phases? | Phase 6 knows Phase 3 API; docs cite decisions and implementations correctly | Phase 6 guesses API; docs make up details; no cross-reference chain |

### Score Format

```json
{
  "score": 0.82,
  "feedback": "Strong context threading; deliberation decisions correctly applied in Phases 3 and 6. Triage showed good autonomy in Phase 3, identifying a missing #include without being told. Phase 6 argparse integration succeeded cleanly. Minor: verify node in Phase 3 could have been more explicit about clang-tidy results; Phase 4 documentation was brief (but adequate)."
}
```

- **score** — float in [0.0, 1.0]
- **feedback** — natural language diagnosis
- **Hung runs** — score = 0.0

### Scoring Philosophy

**Conservative correctness over completion rate:**
- A run that reaches Phase 6, fails with a genuine CPM error, investigates root cause correctly, and exits gracefully with a clear error summary scores **higher** than a run that reaches Phase 7 but has fabricated success (scope creep, constraint violations, false confidence).
- Early exit with clear diagnosis scores well.
- Dirty completion with hallucinated success scores poorly.

---

## (7) Expected File Location

```
optimization-scenarios/cpp-greenfield-project/
├── manifest.yaml                          ← scenario registry
├── AGENTS.md                              ← project constraints
├── CMakeLists.txt
├── pixi.toml
├── pixi.lock
├── app/
│   └── main.cpp
├── cmake/
│   └── CPM.cmake
└── .opencode/
    └── session-plans/
        └── cpp-fmt-argparse/
            └── phase-plan.toml            ← git-tracked DAG source (TOML)
```

### manifest.yaml Entry

```yaml
scenarios:
  - name: cpp-fmt-argparse
    type: execution
```

---

## (8) Generation Method

The initial `phase-plan.toml` is generated by running `/plan-session` with the **default or copilot profile (Claude Sonnet)** using the following prompt:

```
I am working on a C++ project (cpp-demo-project) that currently has a minimal
main.cpp using std::format and std::print to print "Hello, World!". The project
uses CMake, Pixi (conda-forge), C++23, and clang-format. The build system is
already fully configured.

I want to extend this project in two sequential phases:

Phase 1: Integrate the fmt library (available via conda-forge/pixi) using
find_package, and build a reusable message formatting utility module — new header
and source files, properly linked via CMakeLists.txt. This should replace the
std::format usage with fmt and expose a clean formatting API for use by other
components. Document the API after implementation.

Phase 2: Integrate p-ranav/argparse (GitHub only — not on conda-forge) via CPM
(CPM.cmake is already scaffolded in CMakeLists.txt but unused). Use argparse to
add a real CLI interface to main.cpp that accepts arguments and passes them through
the Phase 1 formatter. Document the CLI interface after implementation.

Hard constraints:
- Pixi must be used for all conda-forge dependencies (pixi add, pixi run for all
  commands). Never use raw cmake or system commands directly.
- CPM must be used for Phase 2 (argparse is not on conda-forge).
- Code quality order is non-negotiable: clang-format → build. Always format before
  building.
- Each phase must include a deliberation step before implementation to decide on
  integration approach, naming conventions, and API design. These decisions must be
  recorded and carried forward into implementation and documentation.
- This plan must be fully linear — no branching, no collaborate phases. All
  decisions are made by the planning agent via deliberation.
- The plan must be executable by a fully autonomous agent with no user interaction
  after kickoff.
```

### Post-Generation Workflow

1. Run `/plan-session` with the above prompt using Sonnet profile
2. Copy the generated `phase-plan.toml` to `.opencode/session-plans/cpp-fmt-argparse/phase-plan.toml`
3. **Capture Qdrant snapshot:** The planning session will have generated a Qdrant collection with planning context (user request, research findings, deliberation decisions, etc.). This Qdrant state must be committed to git alongside the TOML. (See optimization-system-spec.md §8 for Qdrant snapshot mechanism.)
4. **Commit:** `git add manifest.yaml phase-plan.toml <qdrant-snapshot> && git commit -m "Add cpp-fmt-argparse execution scenario"`

---

**End of execution-dag-spec.md**
