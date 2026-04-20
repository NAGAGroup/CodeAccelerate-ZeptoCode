# Creating the Plan

Craft a plan as an executable DAG. The plan will be locked in by calling `create_plan`.

Do not activate the plan — this step only produces and locks in the plan.

## Hard Rules

1. Every plan has exactly one entry point — the phase not referenced in any other phase's `next` field.
2. Every phase must define `next`. Use `next = []` for leaf/exit phases.
3. **Branching:** Only phases explicitly marked with `is-branch = true` may have multiple entries in their `next` field. **Note: Branching defines separate, sequential execution pathways based on key decisions, not parallel work.**
4. If the plan involves external dependencies or resources at any point, then every work phase in the plan must include web search. Not just the phases that directly touch the dependency — every single one. Make sure to include web searches for both project setup (e.g. dependency integration, build system configuration, etc.) and source code implementation work (user guides, API docs, header/module import paths, etc.).
5. Work through all steps completely before calling `create_plan`. Do not skip steps.

## Step 1: Retrieve Context

1. Use `qdrant_qdrant-find` with `collection_name={{PLAN_NAME}}` to retrieve the user's goal and all relevant findings from prior exploratory steps. Determine what to query to fully understand the goal, constraints, and prior research.
2. Establish:
   - The user's core goal in one sentence.
   - multiple, varied queries to resolve critical findings/info from prior steps.
   - Collaboration signal: "autonomous" | "collaborative" | "unclear".
   - Whether external dependencies or resources are involved anywhere in the plan.
3. If collaboration signal is unclear, use the `question` tool now to resolve it.

## Step 2: Identify Work Permutations and Decisions

**Meta-Instruction: Prioritize mapping all identified work permutations into the decision/branch structure before proceeding to Step 3.**

Start with the work, not the decisions. Decisions exist to route between concrete work permutations.

1. **Work permutations.** Based on the goal and findings, what are all the concrete ways this could be implemented? For each permutation, specify:
   - What gets set up (dependencies, build config, scaffolding, and any research needed — API docs, integration guides, etc.)
   - What code or documentation gets written
   - How to verify it worked — build commands, test commands, visual checks, etc. The executing agent uses exactly what you write here.
   - Constraints that must be maintained even during triage and retries
   - Planning context — why this permutation exists, what prior findings informed it

2. **Decisions and Discussion.** Identify phases where input is required. These can be general discussion/research phases (`collaborate`/`deliberate`) or explicit decision points.
   - Who decides: user (`collaborate`) or agent (`deliberate`).
   - **If the phase is an explicit decision point (i.e., it routes to separate, distinct work permutations), it must define a branch point.**
   - **Crucially, a single decision phase can capture multiple topics or decisions in its `purpose` list.** If it defines a branch point, it must lead to separate, explicitly named pathways. Each named branch must represent a distinct, concrete work permutation.

## Step 3: Map to Plan Structure

The following examples show common plan shapes. Find the patterns that match your work permutations and decisions, then combine and adapt them.

### Example: Simple implementation (no unknowns, no user involvement)
implement-code(goal="add email validation to user registration endpoint")
  → finish

### Example: User collaboration with concrete branching
collaborate(
  purpose=["discuss project requirements", "choose web framework", "research Flask vs Express feature comparison and deployment considerations"],
  is-branch=true
)
  → [flask-app] implement-code(
      setup=["install Flask via pip", "create app directory structure", "research Flask blueprint project structure and error handling patterns"],
      goal="build REST API using Flask routes and blueprints"
    ) → finish
  → [express-app] implement-code(
      setup=["install Express via npm", "initialize package.json", "research Express router, middleware, and error handling patterns"],
      goal="build REST API using Express router and middleware"
    ) → finish
  → [no-viable-option] finish(reason="requirements incompatible with available options")

### Example: Agent resolves unknowns, then branches to concrete work
deliberate(
  purpose=["evaluate threading strategy for packet processor", "research C++20 std::jthread vs coroutines performance tradeoffs", "research io_uring async patterns in C++"],
  is-branch=true
)
  → [threadpool-approach] implement-code(
      setup=["configure CMakeLists.txt with std.jthread and <latch> support", "enable C++20"],
      goal="implement thread pool dispatcher using std.jthread and lock-free queue"
    ) → finish
  → [coroutine-approach] implement-code(
      setup=["configure CMakeLists.txt with coroutine support flags", "enable C++20", "research C++20 coroutine task patterns and io_uring integration"],
      goal="implement async packet dispatcher using C++20 coroutines and io_uring"
    ) → finish

### Example: Multi-phase with documentation
implement-code(goal="implement BVH acceleration structure for ray-scene intersection")
  → implement-code(
      setup=["research Fresnel equations for physically based rendering", "research Cook-Torrance BRDF implementation"],
      goal="add material shading system with reflection and refraction support"
    )
  → author-documentation(
      setup=["research technical documentation conventions for graphics APIs"],
      goal="write rendering pipeline reference with configuration examples"
    )
  → finish

### Example: Collaboration with feature prioritization branching
collaborate(
  purpose=["review existing codebase", "prioritize which features to add"],
  is-branch=true
)
  → [auth-and-roles] implement-code(
      goal="add user authentication with bcrypt password hashing"
    ) → implement-code(
      goal="add role-based access control middleware"
    ) → finish
  → [auth-and-audit] implement-code(
      goal="add user authentication with bcrypt password hashing"
    ) → implement-code(
      goal="add audit logging for all API operations"
    ) → finish
  → [full-security] implement-code(
      goal="add user authentication with bcrypt password hashing"
    ) → implement-code(
      goal="add role-based access control middleware"
    ) → implement-code(
      goal="add audit logging for all API operations"
    ) → finish
  → [auth-only] implement-code(
      goal="add user authentication with bcrypt password hashing"
    ) → finish

### Additional structural patterns (allowed but not shown above)
- Nested branching (a branch leads to another decision) is allowed.
- Any phase type can be a merge point (multiple branches converge).
- `finish` should appear at every leaf. Use it to document completion context.

## Step 4: Write the TOML

1. Load the `planning-schema` skill.
2. Map your plan structure from Step 3 to actual phase types and fields using the schema as the definitive reference.
3. Write the full plan in TOML. Don't re-derive — transcribe from Steps 2 and 3.
4. Before calling `create_plan`, verify:
   - Exactly one entry point.
   - Every phase has `next`.
   - Only phases with `is-branch = true` have multiple `next` entries.
   - Collaboration or deliberation that does not define decisions, which *must* branch into separate named branches, may have `is-branch=false`.
   - If external dependencies are involved anywhere, every work phase has web search in its setup list.
   - Every work phase has verification instructions with concrete commands.
   - Every decision from Step 2 appears as a branching phase with named concrete branches.
5. Call `create_plan` with `plan_name={{PLAN_NAME}}`. On errors, read them and retry.
6. Once `create_plan` succeeds, call `next_step` immediately.
