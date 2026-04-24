---
description: "Start a planning session — explore, design, decompose, and write a project DAG"
---
Objective: Initiate a structured project planning and decomposition session to generate a definitive Project Directed Acyclic Graph (DAG) for the specified request.

Input:
- User Request Details: `$ARGUMENTS` (The complete request requiring planning).

Process Flow and Execution Directives:

1.  **Prerequisite Skill Loading:** Immediately load and ensure the operational status of the `following-plans` skill. Failure to load this skill constitutes an immediate task failure.
2.  **Preflight Analysis (Input Deconstruction):** Analyze the `$ARGUMENTS` to generate the following four structured data points:
    a. `user_request`: A complete, lossless semantic summary of the user's request, retaining all constraints and intent.
    b. `user_involvement`: A boolean (`true`/`false`) indicating whether the user requires involvement during planning or execution.
    c. `user_involvement_nature`: If `user_involvement` is true, provide a detailed description of the required collaboration type.
    d. `constraints`: A comprehensive list of all explicit limitations, scope boundaries, or exclusions defined within `$ARGUMENTS`.
3.  **Execution Gate Validation:** Before proceeding to the planning phase, verify the following conditions:
    a. The `following-plans` skill is successfully loaded and active.
    b. All four Preflight Analysis fields (`user_request`, `user_involvement`, `user_involvement_nature`, `constraints`) are fully populated.
    If either condition fails, resolve the dependency before proceeding.
4.  **Planning Execution:** Invoke the `plan_session` function, utilizing the validated preflight data and the loaded skill to generate the comprehensive planning DAG.

Constraints and Quality Thresholds:
- **Scope Boundary:** This session is strictly for decomposition and planning; it must not attempt to execute or solve the original request.
- **Dependency:** The resulting Project DAG must be the guiding artifact for all subsequent steps.
- **Data Integrity:** The `user_request` summary must maintain 100% semantic fidelity to the original input.

Output:
- A structured Project DAG detailing the planned steps, dependencies, and scope derived from the planning session.
