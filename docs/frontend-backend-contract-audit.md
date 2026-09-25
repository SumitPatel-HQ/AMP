# Frontend/Backend Contract Audit (Prompt 6)

Audit date: 2026-09-25. Scope: every mission-workspace surface built in Prompts 1–5, plus the Prompt 6 metrics panel.

Each row traces one UI requirement through the stack:

`UI requirement -> frontend source -> API endpoint/DTO -> domain object -> persistence/source -> status`

Status values:

- **supported**: the contract carries the data directly.
- **awkward**: the UI gets the data, but it has to reconstruct it or accept a limitation.
- **missing**: the UI cannot get the data.

The "Fix" column records what Prompt 6 changed. Every backend change links to a row that was **missing** before the change. The evidence section below gives the proof for each change.

## Matrix

### Mission header / state

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Mission name, id, satellite | `MissionBar` ← `useMissionSession.scenario` | `POST /scenarios`, `GET /scenarios/{id}` → `ScenarioSchema` | `Scenario` | scenarios repository | supported | — |
| Simulated clock, T+ elapsed/total, complete flag | `MissionBar.MissionClock`, `StatusChip` | `GET /scenarios/{id}/state` → `MissionStateSchema` | `MissionState` | states repository | supported | — |
| Battery / storage against capacity | `StatePanel.Resource` | `MissionStateSchema` + `ScenarioSchema.satellite` capacities | `MissionState`, `Satellite` | states, scenarios | supported | — |
| Active events | `StatePanel` | `MissionStateSchema.active_event_ids` + `GET /scenarios/{id}/events` | `MissionState`, `MissionEvent` | events repository | supported | — |
| Completed count over the request pool | `StatePanel` "Completed x / n" | Before: `n` = `scenario.requests.length` | `RequestPool` | scenario + event log | **missing** (emergency requests left out of `n`) | `n` = length of `GET /scenarios/{id}/requests` |
| Current plan version | `MissionBar`, `StatePanel` | `MissionPlanSchema.version` | `MissionPlan` | plans repository | supported | — |

### Requests / windows

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Every request in the pool, emergency arrivals included | `MissionNavPanel.RequestList` ← `scenario.requests` + `introducedRequests(events)` | `ScenarioSchema` + `MissionEventSchema` payloads | `RequestPool` | scenario + event log | awkward (the client rebuilds the pool from the event log) | Kept for membership and geometry: the rebuild is exact and tested, and it carries the introducing event id that the UI shows. Statuses and the pool size now come from `GET /scenarios/{id}/requests`. The two sources must agree on membership, and the backend route is the authority for status. |
| Status per request, with **expired** (Prompt 1: "statuses already available from the backend"; the decision "Simulation marks a request EXPIRED") | `requestStatus()` | Before: none. `ScenarioSchema.requests[].status` is always the immutable submitted `pending`. | `ObservationRequest.status` in the session's `RequestPool` | Rebuilt by `MissionSession.restore` from state + plans | **missing** | New `GET /scenarios/{id}/requests` → `ObservationRequestSchema[]` with live statuses. `requestStatus()` gains the `expired` state. |
| Planned / started / invalid / unscheduled per request | `requestStatus()` | `MissionPlanSchema.actions[].status`, `.unscheduled[]`, `ImpactSchema` | `MissionPlan`, `Impact` | plans, impacts | supported | — |
| Windows with validity and reason | `MissionNavPanel.WindowList` | `GET /scenarios/{id}/windows` → `ObservationWindowSchema[]` | `ObservationWindow` | windows repository | supported | — |

### Map

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| A target per pool request, with priority, deadline, plan status | `missionMapModel` ← `missionRequestPool(scenario, events)` + plan + state | `ScenarioSchema`, `MissionEventSchema`, `MissionPlanSchema`, `MissionStateSchema` | `ObservationRequest`, `MissionPlan` | as above | supported | — |
| Expired targets | `missionMapModel` `targetStatus` | Before: none (same gap as the request list) | `ObservationRequest.status` | session `RequestPool` | **missing** | `buildMissionMapModel` takes the expired ids from `GET /scenarios/{id}/requests`. The map now draws an `expired` status with its own legend entry. |
| Satellite position | `satellitePlacement()` places it over the current or last observed target | none | none. The domain holds no orbit or position. | — | awkward, by design. Windows are synthetic and there is no propagator. | None. Adding a position would be a new domain concept, which Prompt 6 forbids. |
| Shared selection | `selection.requestId` | — | — | — | supported (client state) | — |

### Timeline (`vis-timeline`)

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Window ranges, valid and invalid | `buildMissionTimelineModel` ← `windows` | `ObservationWindowSchema` | `ObservationWindow` | windows | supported | — |
| Scheduled actions with frozen/completed status | ← `plan.actions` | `ScheduledActionSchema.status` | `ScheduledAction` | plans | supported | — |
| Mission-time marker | ← `missionState.simulated_time` | `MissionStateSchema` | `MissionState` | states | supported | — |
| Event markers at their mission time | ← `events` | `MissionEventSchema.event_time` | `MissionEvent` | events | supported | — |
| Impacted and changed items | ← `impact`, `replanResult.diff` | `ImpactSchema`, `PlanDiffSchema` | `Impact`, `PlanDiff` | impacts; the diff is recomputed | supported | — |
| Expired request groups | `buildMissionTimelineModel` does not read expiry | `GET /scenarios/{id}/requests` now provides it | `ObservationRequest.status` | session `RequestPool` | awkward. An expired request has no action item, and its group reads as unscheduled. | None in Prompt 6. The contract gap is closed; the request list and the map show expiry. Timeline styling belongs to Prompt 7's cross-surface pass. |
| Previous plan's placement after a replan | ← `replanResult.initialPlan` | `MissionPlanSchema` (from before the replan) | `MissionPlan` | plans | supported | — |

### Events

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Inject CLOUD_BLOCK / BATTERY_DROP / EMERGENCY_TASK | `EventControl` → `injectEvent` | `POST /scenarios/{id}/events` ← `MissionEventRequest` | `MissionEvent` + payloads | events | supported | — |
| Event log with summaries | `EventList`, `eventSummary` | `GET /scenarios/{id}/events` | `MissionEvent` | events | supported | — |

### Persisted impact

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Latest event's impact on the plan it evaluated | `ImpactPanel` | `GET /scenarios/{id}/impact` → `ImpactSchema` | `Impact` | impacts | supported | — |
| "No impact yet" before any event | `fetchImpactIfAny` | 409 `SIMULATION_STATE_ERROR` | — | — | awkward (the client reads an error code as "empty") | None. The behaviour is documented and tested. No surface needs the impact of an earlier event, so an impact-history route would be speculative. |

### Replanning

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Replan against the displayed version | `useMissionSession.replan` | `POST /scenarios/{id}/replan` ← `ReplanRequest.expected_parent_plan_id` | `Replan` | plans (optimistic check) | supported | — |
| Stale-version conflict, then refresh to the current plan | `refreshAfterConflict`, `PlanConflictBanner` | 409 `PLAN_VERSION_CONFLICT` with `details.current_plan_id`; `GET /plans/{id}` | — | plans | supported | — |

### Plan comparison

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Diff entries with change type, reason, old/new start | `comparisonRows` | `GET /plans/{old}/compare/{new}` → `PlanDiffSchema.entries` | `PlanDiff` | recomputed from stored plans + impacts | supported | — |
| Old/new window per changed request | `comparisonRows` reads both plans' actions | `MissionPlanSchema` × 2 | `ScheduledAction` | plans | supported | — |
| List of every plan version (Plans tab) | `knownPlans()`: only the last replan's pair plus the current plan | none (`GET /plans/{id}` only) | `MissionPlan` | plans | awkward. After V3, V1 leaves the Plans tab. `planLabel` falls back to the id suffix, which still names the plan uniquely. | None in Prompt 6. No Prompt 1–6 surface compares versions that are not adjacent. Prompt 7 owns the cross-surface history. |

### Decision traces

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Trace per changed request, with event link and constraint | `comparisonRows` → `TraceLine` | `GET /plans/{id}/traces` → `DecisionTraceSchema[]` | `DecisionTrace` | traces | supported | — |
| Readable reason alongside the canonical code | `REASON_LABELS` | `ReasonCode` enum | `ReasonCode` | — | supported | — |

### Metrics

| UI requirement | Frontend source | API / DTO | Domain | Persistence | Status | Fix |
|---|---|---|---|---|---|---|
| Metrics for the current plan before any replan | Before: none. The panel waited for a replan. | `GET /plans/{id}/metrics` → `MetricsSchema` (the route existed, but no client used it) | `MetricsResult` | computed | awkward (the frontend did not use the route) | `fetchMetrics()`. The session refetches the current plan's metrics after every mutation. |
| Before/after for the replan's two plans | `metricsSubject`, `metricsView` | `PlanDiffSchema.metrics_before/after` | `MetricsResult` × 2 | computed | supported | — |
| Metrics tied to the exact plan version | `planLabel(metrics.plan_id)` | `MetricsSchema.plan_id` | — | — | supported | — |
| **When** the metrics were measured | Before: none | Before: none. Utilisation and completion read the *live* mission state. The same plan returned battery 0% at 10:00 and 8% at 10:05 with no field to show the difference. | `MissionState.simulated_time` | states | **missing** | `MetricsSchema.measured_at` / `MetricsResult.measured_at`. The panel header says "measured HH:MM UTC". |
| Battery/storage utilisation shown as per-plan values | Before: before/after columns | `battery_utilisation`, `storage_utilisation` | Read from `MissionState`, not from the plan | — | awkward. Both columns always held the same value, which suggested a per-plan difference that does not exist. | Shown once as "Mission state at HH:MM UTC". No backend change. |
| Churn / coverage N/A for empty denominators | `formatPercent(null)` → "N/A" | `plan_churn`, `explanation_coverage`: `float \| null` | locked decision | — | supported | — |
| Completion over an empty pool | `metricsView` shows "N/A" when `request_pool_size === 0` | `completion_rate` is `0.0` for an empty pool (locked backend behaviour) | — | — | awkward | Handled in the frontend. `request_pool_size` in the DTO proves the denominator is empty, so no backend change. |
| Request-pool mismatch flag, with the differing requests named | `PoolMismatch` | `PlanDiffSchema.request_pool_mismatch`, `request_pool_ids` | — | — | supported | The panel still shows the utility and completion deltas when the pools differ, but marks them "pools differ" and does not colour them as better or worse. |

## Evidence for the backend changes

### 1. `GET /scenarios/{scenario_id}/requests`

- Requirement: Prompt 1 says the request list shows "statuses already available from the backend". A locked decision says "Simulation marks a request EXPIRED when its deadline passes."
- Gap: the scenario is immutable (ADR-0002), so `GET /scenarios/{id}` always returns the submitted `pending` status. No route exposed the session's `RequestPool`. An expired request therefore showed as "unscheduled" or "planned" for the rest of the mission. The client could only fix that by copying the domain's expiry rule, which would move domain logic into the browser. The Completed count also divided by the scenario's request count and left out emergency arrivals.
- Change: one read route over the existing facade method `MissionSession.get_request_pool()`. It reuses `ObservationRequestSchema`. Planner, domain and persistence behaviour stay the same.
- Tests: `tests/test_rest_api.py::test_requests_route_lists_the_request_pool_with_live_statuses`, `requestStatus.test.ts` (expired), `App.test.tsx` ("marks a request the backend expired…").

### 2. `MetricsSchema.measured_at`

- Requirement: "Metrics correctly describe specific plans", and the locked decision "Metrics are self-describing".
- Gap: `compute_metrics` reads battery, storage, completion and completed-request utility from the mission state at the time of the query. Probe: the same plan gave `battery_utilisation` 0.0 after planning and 0.08 after a 300 s step, and both sides of a comparison always carried identical utilisation. The DTO did not say which instant a reading belonged to.
- Change: one field copied from `mission_state.simulated_time`. No metric formula changed.
- Tests: `tests/test_metrics.py::test_metrics_name_the_simulated_instant_they_were_measured_at`, `tests/test_replanning_metrics.py::test_both_sides_of_a_comparison_are_measured_at_the_same_instant`, `tests/test_rest_api.py::test_metrics_route_names_the_simulated_instant_it_measured`.

`frontend/src/api/schema.ts` was regenerated from the updated OpenAPI document. The diff contains only these two additions.

## Deliberately not changed

- Planner, replanner, metric formulas, and the `completion_rate = 0.0` result for an empty pool are locked. The frontend shows N/A in that case.
- Plan-history route, impact-history route, satellite position: rows marked awkward, with no Prompt 1–6 requirement that needs them.
- Recharts: not added. Every metric is one value, or two values and a delta, so a chart would add no information.
