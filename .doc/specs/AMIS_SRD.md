# AMIS --- Software Requirements Document (SRD)

**Project:** Adaptive Mission Planning for Earth Observation Satellites\
**Document Type:** Software Requirements / Technical Specification\
**MVP Target:** 2--3 day implementation sprint

## 1. System Purpose

AMIS is a modular local software system that simulates Earth-observation
mission state, schedules observation requests under constraints, applies
controlled disruptions, detects plan infeasibility, replans affected
mission work, records decision traces, and exposes results through a
lightweight web interface.

The technical design shall keep the planner independent from the UI,
HTTP layer, and persistence layer.

## 2. Architectural Principles

1.  **Simulation first.** Mission state and deterministic scenario
    execution are the foundation.
2.  **Planner independence.** Planning algorithms consume domain objects
    and return plans without depending on FastAPI, React, or PostgreSQL.
3.  **Pure constraint logic where possible.** Validation functions
    should be independently testable.
4.  **Immutable plan versions.** Replanning creates a new plan version
    rather than mutating history.
5.  **Structured explanations.** Decision traces use reason codes and
    structured data; natural-language text is a presentation layer.
6.  **Reproducibility.** Scenario configuration and random seed must be
    stored.
7.  **Local operation.** No live API shall be required for the MVP.
8.  **Replaceable algorithms.** Baseline and future advanced planners
    shall share one interface.

## 3. Logical Architecture

``` text
┌──────────────────────────────────────────────────────────────┐
│                    React / TypeScript UI                     │
│ Scenario | Map | State | Timeline | Events | Trace | Metrics│
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP/JSON
┌──────────────────────────────▼───────────────────────────────┐
│                         FastAPI API                          │
│ Scenario / Planning / Simulation / Events / Metrics         │
└──────────────┬───────────────────┬───────────────────────────┘
               │                   │
     ┌─────────▼─────────┐   ┌─────▼────────────────────┐
     │ Mission State     │   │ Planning Core           │
     │ Simulation Engine │   │ Planner + Constraints   │
     └─────────┬─────────┘   └──────────┬───────────────┘
               │                        │
     ┌─────────▼─────────┐   ┌──────────▼───────────────┐
     │ Scenario / Event  │   │ Adaptive Replanner      │
     │ Engine            │   │ Impact + Plan Diff      │
     └─────────┬─────────┘   └──────────┬───────────────┘
               └──────────────┬─────────┘
                              ▼
                 Decision Trace / Metrics
                              │
                              ▼
                        PostgreSQL
```

## 4. Backend Module Structure

``` text
backend/
├── app/
│   ├── api/
│   │   ├── scenarios.py
│   │   ├── planning.py
│   │   ├── simulation.py
│   │   ├── events.py
│   │   └── metrics.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── enums.py
│   │   └── schemas.py
│   ├── simulation/
│   │   ├── state.py
│   │   ├── engine.py
│   │   └── windows.py
│   ├── constraints/
│   │   ├── validator.py
│   │   └── rules.py
│   ├── planning/
│   │   ├── base.py
│   │   ├── greedy.py
│   │   └── cpsat.py
│   ├── replanning/
│   │   ├── impact.py
│   │   ├── replanner.py
│   │   └── diff.py
│   ├── explainability/
│   │   ├── reason_codes.py
│   │   └── traces.py
│   ├── benchmarking/
│   │   └── metrics.py
│   ├── persistence/
│   │   ├── models.py
│   │   └── repository.py
│   └── main.py
└── tests/
```

## 5. Core Domain Models

### 5.1 ObservationRequest

``` text
id: string
target_lat: float
target_lon: float
priority: int             # 1..5
duration_seconds: int
deadline: datetime
status: enum
storage_required_mb: float
energy_required_wh: float
```

### 5.2 Satellite

``` text
id: string
battery_capacity_wh: float
battery_current_wh: float
storage_capacity_mb: float
storage_used_mb: float
available: bool
```

### 5.3 ObservationWindow

``` text
id: string
request_id: string
satellite_id: string
start_time: datetime
end_time: datetime
valid: bool
invalid_reason: optional string
```

### 5.4 MissionState

``` text
scenario_id: string
simulation_time: datetime
satellite_id: string
battery_wh: float
storage_used_mb: float
satellite_available: bool
active_event_ids: list[string]
completed_task_ids: list[string]
```

### 5.5 ScheduledAction

``` text
id: string
request_id: string
satellite_id: string
window_id: string
start_time: datetime
end_time: datetime
status: enum
expected_energy_wh: float
expected_storage_mb: float
```

### 5.6 MissionPlan

``` text
id: string
scenario_id: string
version: int
parent_plan_id: optional string
created_at: datetime
actions: list[ScheduledAction]
utility: float
constraint_violations: int
planning_time_ms: float
```

Plan versions shall be immutable after creation.

### 5.7 MissionEvent

``` text
id: string
scenario_id: string
event_type: enum
event_time: datetime
payload: object
```

Required event types:

``` text
CLOUD_BLOCK
BATTERY_DROP
EMERGENCY_TASK
```

Optional event types:

``` text
COMMUNICATION_OUTAGE
SATELLITE_UNAVAILABLE
```

### 5.8 DecisionTrace

``` text
id: string
plan_id: string
event_id: optional string
request_id: optional string
reason_code: string
previous_action: optional object
new_action: optional object
constraint: optional string
message: string
metadata: object
```

## 6. Reason Codes

Minimum supported codes:

``` text
WINDOW_INVALIDATED
INSUFFICIENT_BATTERY
INSUFFICIENT_STORAGE
DEADLINE_VIOLATION
TIME_OVERLAP
SATELLITE_UNAVAILABLE
HIGHER_PRIORITY_TASK_INSERTED
ALTERNATIVE_WINDOW_AVAILABLE
NO_ALTERNATIVE_WINDOW
TASK_UNCHANGED
```

Reason codes are authoritative. Human-readable explanation strings are
generated from them.

## 7. Planner Interface Contract

All planning algorithms shall implement a common contract equivalent to:

``` python
class Planner(Protocol):
    def plan(
        self,
        scenario: Scenario,
        state: MissionState,
        tasks: list[ObservationRequest],
        windows: list[ObservationWindow],
    ) -> MissionPlan:
        ...
```

The planner shall not:

-   read UI state;
-   perform HTTP requests;
-   query live APIs;
-   write directly to React-facing structures;
-   mutate previous mission plans.

## 8. Baseline Planning Behavior

The required baseline is deterministic greedy scheduling.

Recommended ordering:

``` text
priority descending
→ deadline ascending
→ duration ascending
→ request ID ascending
```

For each task:

1.  obtain valid windows;
2.  sort windows by earliest start;
3.  evaluate candidate start time;
4.  check deadline;
5.  check action overlap;
6.  check battery;
7.  check storage;
8.  check satellite availability;
9.  schedule into the earliest feasible candidate;
10. otherwise record the task as unscheduled with a reason.

Suggested baseline mission utility:

``` text
utility = Σ priority(task) for each successfully scheduled/completed task
```

The exact utility formulation can later be replaced without changing the
planner interface.

## 9. Constraint Engine

The constraint engine shall expose independently testable validation
operations.

Minimum checks:

``` text
is_inside_observation_window(action, window)
meets_deadline(action, request)
has_no_overlap(action, existing_actions)
has_sufficient_battery(action, state)
has_sufficient_storage(action, state)
is_satellite_available(action, state)
validate_plan(plan, scenario, state)
```

Validation output should be structured:

``` json
{
  "valid": false,
  "violations": [
    {
      "code": "INSUFFICIENT_BATTERY",
      "request_id": "OBS-004",
      "details": {}
    }
  ]
}
```

## 10. Observation Window Generation

### Sprint Mode

Use deterministic synthetic observation windows generated from scenario
configuration. This avoids making orbital mechanics a blocker for the
planning/replanning demonstration.

### Extension Mode

A replaceable window provider may later use:

-   Skyfield;
-   SGP4;
-   static TLE/ephemeris inputs.

No live TLE API is required.

Recommended interface:

``` python
class WindowProvider(Protocol):
    def generate(
        self,
        scenario: Scenario,
        requests: list[ObservationRequest],
    ) -> list[ObservationWindow]:
        ...
```

## 11. Simulation Engine

The simulation engine shall:

-   hold current mission time;
-   advance time by a deterministic step;
-   mark actions started/completed;
-   update battery;
-   update storage;
-   apply active events;
-   expose the current `MissionState`.

Minimum API:

``` text
initialize(scenario)
get_state()
step(seconds)
apply_event(event)
reset()
```

The same scenario and seed shall produce the same state progression.

## 12. Event Engine

### CLOUD_BLOCK

Payload example:

``` json
{
  "request_id": "OBS-B",
  "window_id": "WIN-B-1"
}
```

Behavior: mark the selected observation window invalid.

### BATTERY_DROP

Payload example:

``` json
{
  "satellite_id": "SAT-001",
  "new_battery_wh": 35.0
}
```

Behavior: update mission state and invalidate future actions that no
longer satisfy battery constraints.

### EMERGENCY_TASK

Payload example:

``` json
{
  "request": {
    "id": "OBS-EMG-1",
    "priority": 5,
    "duration_seconds": 120,
    "deadline": "..."
  }
}
```

Behavior: add the new request and its window(s) to the remaining
planning problem.

## 13. Impact Analysis

After an event, the impact analyzer shall classify future actions as:

``` text
UNCHANGED
AFFECTED
INVALID
```

Completed actions and actions wholly in the past are frozen.

The analyzer shall return:

``` json
{
  "event_id": "EVT-001",
  "affected_action_ids": ["ACT-002"],
  "invalid_action_ids": ["ACT-002"],
  "unaffected_action_ids": ["ACT-003", "ACT-004"],
  "reason_codes": ["WINDOW_INVALIDATED"]
}
```

## 14. Adaptive Replanning Behavior

Replanning algorithm:

``` text
1. Load Plan vN.
2. Freeze completed/past actions.
3. Apply event to mission state/window/task data.
4. Validate all remaining scheduled actions.
5. Identify affected/invalid actions.
6. Build remaining planning problem.
7. Preserve feasible future actions where possible.
8. Reschedule affected/unscheduled/new tasks.
9. Validate resulting plan.
10. Create immutable Plan vN+1.
11. Compute plan diff.
12. Generate decision traces.
13. Calculate revised metrics.
```

A full rebuild of all remaining future tasks is acceptable for the MVP
if the system still freezes mission history and reports plan churn
correctly.

## 15. Plan Diff Contract

Plan comparison shall classify each request as:

``` text
UNCHANGED
MOVED
INSERTED
DROPPED
COMPLETED
```

Example:

``` json
{
  "request_id": "OBS-B",
  "change": "MOVED",
  "old_start": "2026-09-21T10:20:00",
  "new_start": "2026-09-21T11:15:00",
  "reason_code": "WINDOW_INVALIDATED"
}
```

## 16. Explainability Requirements

Explanation generation shall be deterministic and grounded in planning
data.

Template example:

``` text
{request_id} moved from {old_time} to {new_time} because
{constraint_description}. The new slot was selected because
{alternative_description}.
```

An LLM is optional after the MVP and shall not be required to derive the
planning reason.

## 17. Metrics

Required calculations:

### Mission Utility

``` text
Σ priority of successfully scheduled/completed tasks
```

### Task Completion Rate

``` text
completed_tasks / total_tasks
```

### Constraint Violations

Number of validation violations in the resulting plan.

### Planning/Replanning Time

Wall-clock execution time of the planning operation in milliseconds.

### Resource Utilization

Battery and storage consumed relative to configured capacity.

### Plan Churn

Recommended MVP definition:

``` text
changed_future_actions / future_actions_in_previous_plan
```

### Explanation Coverage

``` text
changed_actions_with_trace / total_changed_actions
```

## 18. REST Interface

Minimum endpoints:

  ------------------------------------------------------------------------------------
  Method                  Endpoint                             Purpose
  ----------------------- ------------------------------------ -----------------------
  POST                    `/scenarios`                         Create scenario

  GET                     `/scenarios/{id}`                    Get scenario

  POST                    `/scenarios/{id}/windows/generate`   Generate observation
                                                               windows

  POST                    `/scenarios/{id}/plan`               Generate initial plan

  GET                     `/scenarios/{id}/state`              Current mission state

  POST                    `/scenarios/{id}/simulation/step`    Advance simulation

  POST                    `/scenarios/{id}/events`             Inject event

  POST                    `/scenarios/{id}/replan`             Generate next plan
                                                               version

  GET                     `/plans/{id}`                        Retrieve plan

  GET                     `/plans/{old}/compare/{new}`         Plan diff

  GET                     `/plans/{id}/traces`                 Decision traces

  GET                     `/scenarios/{id}/metrics`            Mission metrics
  ------------------------------------------------------------------------------------

## 19. Persistence Model

Recommended PostgreSQL tables:

``` text
scenarios
satellites
observation_requests
observation_windows
mission_states
mission_plans
scheduled_actions
mission_events
decision_traces
experiment_results
```

For the first backend checkpoint, repositories may be implemented in
memory as long as the domain/service interfaces do not depend on storage
implementation. PostgreSQL integration should follow once the complete
planning loop works.

## 20. Frontend Interface Requirements

Frontend stack:

``` text
React + TypeScript + Vite
```

Required components:

``` text
ScenarioControls
MissionMap
MissionStatePanel
EventPanel
PlanTimeline
PlanComparison
DecisionTracePanel
MetricsPanel
```

Use a lightweight 2D map for the sprint. CesiumJS is a later
replacement/extension.

## 21. Error Behavior

API errors shall return machine-readable codes.

Example:

``` json
{
  "error": {
    "code": "PLAN_INFEASIBLE",
    "message": "No feasible schedule exists for the remaining requests.",
    "details": {}
  }
}
```

Expected error categories:

``` text
INVALID_SCENARIO
INVALID_EVENT
PLAN_INFEASIBLE
CONSTRAINT_VIOLATION
RESOURCE_NOT_FOUND
SIMULATION_STATE_ERROR
```

## 22. Non-Functional Requirements

### Determinism

Repeated execution of a seeded scenario shall produce identical
scheduling results.

### Modularity

Planner, simulator, constraints, replanner, and explanation modules
shall be independently testable.

### Performance

For an MVP scenario of one satellite and approximately 5--10 tasks,
planning and replanning should feel interactive. Record execution time
rather than imposing an artificial research claim.

### Offline Capability

The complete core workflow shall operate without internet access.

### Auditability

Every plan version, event, and decision trace shall be recoverable for
experiment replay.

### Maintainability

Algorithms shall depend on domain contracts rather than
framework-specific objects.

## 23. Required Test Cases

1.  Greedy planner schedules a feasible task.
2.  Planner rejects overlapping tasks.
3.  Planner rejects tasks exceeding a deadline.
4.  Planner rejects insufficient battery.
5.  Planner rejects insufficient storage.
6.  Cloud event invalidates the correct window/action.
7.  Battery drop invalidates resource-infeasible future actions.
8.  Emergency task enters the remaining planning problem.
9.  Replanner does not modify completed actions.
10. Replanner creates a new plan version.
11. Plan diff correctly identifies moved/inserted/dropped actions.
12. Every changed action receives a decision trace.
13. Same scenario seed produces identical results.
14. Resulting Plan v2 passes full constraint validation.

## 24. Technical Definition of Done

The SRD is satisfied for the sprint when the backend can execute this
integration test without the frontend:

``` text
load scenario
→ generate windows
→ plan v1
→ validate v1
→ advance simulation
→ inject event
→ analyze impact
→ replan
→ validate v2
→ compare v1/v2
→ generate traces
→ calculate metrics
```

The React dashboard is then a client of this already-working system.
