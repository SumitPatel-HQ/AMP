# Prompt 4 — Event → Impact → Replan Operational Workflow

Extracted from `AMIS_REDESIGN_CONTEXT.md`. This file is authoritative for Prompt 4 implementation.

Implement only this redesign stage.

The AMIS backend/domain remains authoritative. Preserve all working functionality from Prompts 1–3, especially the shared selection model, mission-control shell, map behavior, and the `vis-timeline` mission timeline implemented in Prompt 3.

Do not redesign the backend or substantially restructure the map/timeline in this stage.

## References

- **AMIS backend/domain:** authoritative for event lifecycle, impact, replanning, plan versions and errors.
- **NASA Open MCT:** reference only for operational workflow, contextual inspection and state transitions.
- **World Monitor:** reference only for compact operational controls/dialog/panel presentation.

Do not copy unrelated architecture or domain behavior from the references.

## Before editing

Inspect the current implementation before making changes. Specifically inspect:

- existing event controls and event API mutations;
- CLOUD_BLOCK, BATTERY_DROP and EMERGENCY_TASK payload contracts;
- scenario, mission-state, requests/windows and plan query/data flow;
- persisted Impact endpoint/DTO and how it links event → evaluated plan → affected/invalid actions;
- replanning endpoint and `expected_parent_plan_id`;
- plan version/current-plan handling;
- lifecycle/error handling including `SIMULATION_STATE_ERROR` and `PLAN_VERSION_CONFLICT`;
- shared request/window/event/plan selection state created by previous prompts;
- map selection/highlighting behavior from Prompt 2;
- the completed `vis-timeline` implementation and event/current-plan mapping from Prompt 3.

Reuse existing components/hooks/query infrastructure where practical instead of creating parallel state or duplicate API layers.

## Goal

Make the complete adaptive operational workflow understandable and executable as one sequence:

```text
Current Plan
→ Configure Event
→ Inject Event
→ See Event in Mission Context
→ Inspect Persisted Impact
→ Replan
→ New Immutable Plan Version
```

The user should understand what disruption occurred and what became invalid **before** analyzing what changed in the resulting plan.

Full Plan Vn ↔ Plan Vn+1 comparison and DecisionTrace analysis remain Prompt 5.

## Event control

Replace any oversized permanent event section with a compact contextual dialog, drawer or popover launched from the existing mission controls. Support the existing backend event types only:

**CLOUD_BLOCK:** use Request → Observation Window selection rather than requiring the user to manually type a window ID. Only show real requests/windows supplied by the backend. After injection, make the blocked request/window/action identifiable in the mission workspace.

**BATTERY_DROP:** provide the real battery-drop input required by the API. After injection: refresh mission resource state; show the new battery value; expose backend-computed impact on future actions. Do not fabricate a spatial association when none exists.

**EMERGENCY_TASK:** use the existing event API contract. Preserve the locked domain behavior: Scenario remains immutable; the emergency request is introduced through the event log; use the explicit observation-window payload expected by the backend; after injection, expose the emergency request in the existing Requests/Windows mission context. Do not mutate scenario data client-side to simulate the emergency request.

## Event lifecycle

Represent the operational state clearly:

```text
Plan Vn active
→ Event configured
→ Event injected
→ Impact available
→ Awaiting replan
→ Replanning
→ Plan Vn+1 available
```

Do not create a second mission state machine in the frontend. Derive UI availability from existing backend/query state and lifecycle responses. Disable or prevent invalid actions when the current lifecycle does not permit them. Preserve backend lifecycle errors and show them intelligibly rather than swallowing them.

## After event injection

Explicitly refetch/invalidate the relevant existing queries. No polling. Update the mission workspace using real backend state. Where applicable: select or focus the injected event; show the event at its actual mission time on the Prompt 3 timeline; highlight the affected request/window/action; highlight the associated target on the map when a real spatial relationship exists; expose the persisted Impact associated with the event. Do not calculate event impact in React.

## Persisted Impact

Treat backend Impact data as authoritative. Clearly show: event identity/type; evaluated plan/version; affected/invalid scheduled actions; request/action/window identity where available; violation/reason codes supplied by the backend. Keep the conceptual distinction explicit:

```text
Impact = what became invalid because of the disruption

Plan Diff = what changed after replanning
```

Do not implement the full Plan Diff UI in this prompt. Do not infer causality or invent human explanations beyond backend-supported reason information.

## Replanning

Enable Replan only when valid for the current mission lifecycle. Use the current immutable plan as the parent and send `expected_parent_plan_id` using the real API contract. Handle optimistic concurrency correctly. If the backend returns `PLAN_VERSION_CONFLICT`, show a visible stale-plan/conflict state and refresh the relevant plan context instead of silently retrying against an unknown version. Do not mutate Plan Vn. A successful replan must produce and expose a new immutable Plan Vn+1.

## After successful replan

Preserve both plan identities: previous plan = Plan Vn, current operational plan = Plan Vn+1. Update the mission workspace and timeline to the new operational plan while retaining Plan Vn context for Prompt 5. Expose any newly unscheduled requests separately using backend data, including their canonical reason codes when available. Do not implement the complete Vn ↔ Vn+1 diff or DecisionTrace analysis yet.

## Shared mission context

Use the shared selection model established in previous prompts. Event selection should be capable of identifying the corresponding: Event → Request → Window / ScheduledAction → Timeline location → Map target where applicable → Impact. Do not build a second independent event-selection state if the shared mission selection model can represent it. Deep final cross-surface polish remains Prompt 7.

## Do not

- redesign or rewrite the backend;
- reimplement event or impact logic in React;
- mutate Scenario to represent emergency requests;
- calculate plan diff client-side;
- invent API/domain data;
- add mock behavior where real endpoints exist;
- use polling;
- replace or substantially rewrite the Prompt 3 timeline;
- rewrite the Prompt 2 map;
- create a generic raw-JSON event form as the primary UX;
- hide backend reason/error codes behind invented explanations;
- discard Plan Vn when Plan Vn+1 is created;
- start Prompt 5 work.

## Acceptance criteria

A reviewer can complete each supported flow from the UI:

```text
Current Plan
→ Inject Event
→ Understand what became affected/invalid
→ Replan
→ See the new Plan version
```

Specifically:

- CLOUD_BLOCK works using Request → Window selection;
- BATTERY_DROP visibly updates mission resource state and backend-computed impact;
- EMERGENCY_TASK enters the mission through the real event contract without mutating Scenario;
- injected events appear at the correct mission time on the existing timeline;
- affected mission objects are highlighted using real relationships where available;
- persisted Impact is displayed separately from future plan-diff analysis;
- Replan sends `expected_parent_plan_id`;
- `PLAN_VERSION_CONFLICT` and lifecycle errors are visible and understandable;
- Plan Vn remains available after Plan Vn+1 is created;
- newly unscheduled requests remain visible with backend reason information;
- no polling is introduced;
- frontend build/typecheck passes;
- relevant frontend tests pass;
- existing Prompt 1–3 functionality is preserved.

After implementation, report: changed files; existing components/hooks reused; reference patterns adapted; event/impact/replan data flow; assumptions or API limitations found; build/typecheck/test results. Stop after Prompt 4. Do not proceed into Plan Comparison or Decision Trace work.
