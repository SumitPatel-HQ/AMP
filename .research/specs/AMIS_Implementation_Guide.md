# AMIS --- MVP Implementation Guide

**Project:** Adaptive Mission Planning for Earth Observation Satellites\
**Sprint:** 2--3 days\
**Objective:** Build the smallest complete adaptive mission-planning
demonstration before adding advanced algorithms or visual polish.

## 1. Sprint Rule

Do not build the project screen-first.

The implementation order is:

``` text
DOMAIN
  ↓
SIMULATION STATE
  ↓
OBSERVATION WINDOWS
  ↓
CONSTRAINTS
  ↓
BASELINE PLANNER
  ↓
EVENTS
  ↓
IMPACT ANALYSIS
  ↓
REPLANNER
  ↓
PLAN DIFF + DECISION TRACE
  ↓
METRICS
  ↓
API
  ↓
UI
```

The core workflow must work from Python tests/CLI before frontend
integration.

## 2. Target Architecture

``` text
┌──────────────────────────────────────────────────────────────┐
│                    React + TypeScript                        │
│                                                              │
│ Scenario Controls        Mission State        Event Controls │
│ 2D Target Map            Plan Timeline        Metrics        │
│ Plan Comparison          Decision Trace                       │
└──────────────────────────────┬───────────────────────────────┘
                               │ REST / JSON
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         FastAPI                              │
│                                                              │
│ /scenarios /plan /state /step /events /replan /metrics      │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
                ▼                              ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│ Mission State Engine    │      │ Planning Engine             │
│ - simulated time        │      │ - planner interface         │
│ - battery               │      │ - greedy baseline           │
│ - storage               │      │ - optional CP-SAT           │
│ - completed actions     │      └──────────────┬──────────────┘
└─────────────┬───────────┘                     │
              │                                 ▼
              │                  ┌─────────────────────────────┐
              ├─────────────────►│ Constraint Engine           │
              │                  │ time/resource/availability  │
              │                  └─────────────────────────────┘
              ▼
┌─────────────────────────┐
│ Scenario / Event Engine │
│ cloud/battery/emergency │
└─────────────┬───────────┘
              ▼
┌──────────────────────────────────────────────────────────────┐
│ Adaptive Replanning                                           │
│ Impact Analysis → Repair/Rebuild → Plan Diff → Decision Trace │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
                    Metrics / Experiment Data
                               │
                               ▼
                         PostgreSQL
```

## 3. Recommended Stack

### Backend

  -------------------------------------------------------------------------
  Tool                    Use                     Reason
  ----------------------- ----------------------- -------------------------
  Python 3.12             Core implementation     Strong
                                                  scientific/optimization
                                                  ecosystem

  FastAPI                 HTTP API                Fast implementation,
                                                  typed contracts,
                                                  automatic OpenAPI

  Pydantic                Domain/API validation   Explicit schemas and
                                                  validation

  OR-Tools                Advanced/second planner CP-SAT support; useful
                                                  for research comparison

  Skyfield + SGP4         Orbit/window extension  Suitable for later
                                                  TLE-based visibility

  SQLAlchemy              Persistence             Keeps database access
                                                  separate from domain
                                                  logic

  PostgreSQL 16           Persistent experiment   Reliable relational model
                          data                    for plans/events/traces

  pytest                  Tests                   Fast unit/integration
                                                  testing
  -------------------------------------------------------------------------

### Frontend

  Tool                      Use
  ------------------------- --------------------------
  React                     Dashboard
  TypeScript                Typed frontend contracts
  Vite                      Build/dev server
  React-Leaflet + Leaflet   2D mission/target map
  Recharts                  Metrics visualization
  date-fns                  Timeline/date formatting
  Axios or Fetch            REST communication

### Infrastructure

Use Docker Compose for:

``` text
frontend
backend
postgres
```

Do not introduce Kubernetes or microservices.

## 4. Dependency Setup

### Backend `requirements.txt`

``` text
fastapi
uvicorn[standard]
pydantic
sqlalchemy
psycopg[binary]
alembic
ortools
skyfield
sgp4
numpy
pandas
pytest
pytest-asyncio
httpx
python-dotenv
```

`ortools`, `skyfield`, and `sgp4` can be installed from the start but
should not block the first working loop.

### Frontend

``` bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install axios leaflet react-leaflet recharts date-fns
npm install -D @types/leaflet
```

### Suggested Environment

``` text
DATABASE_URL=postgresql+psycopg://amis:amis@postgres:5432/amis
AMIS_RANDOM_SEED=42
AMIS_ENV=development
```

No live API keys are required for the MVP.

## 5. Repository Structure

``` text
amis/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── simulation/
│   │   ├── constraints/
│   │   ├── planning/
│   │   ├── replanning/
│   │   ├── explainability/
│   │   ├── benchmarking/
│   │   ├── persistence/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── types/
│   │   └── App.tsx
│   └── package.json
├── scenarios/
│   ├── demo.json
│   └── tle/
├── docker-compose.yml
├── .env.example
└── README.md
```

## 6. Phase 1 --- Domain Models

Build these first:

``` text
Scenario
Satellite
ObservationRequest
ObservationWindow
MissionState
ScheduledAction
MissionPlan
MissionEvent
DecisionTrace
```

Add enums for:

``` text
TaskStatus
ActionStatus
EventType
PlanChangeType
ReasonCode
```

### Checkpoint

A test must successfully construct a complete scenario, serialize it to
JSON, deserialize it, and preserve all values.

Do not proceed until domain models are stable enough for planner tests.

## 7. Phase 2 --- Deterministic Mission State

Implement:

``` text
initialize(scenario)
get_state()
step(seconds)
reset()
```

For the MVP, battery/storage behavior can be simple and explicit:

``` text
observation consumes configured energy
observation adds configured storage
idle behavior may consume a fixed small amount or zero
```

Do not attempt realistic power-system simulation.

### Checkpoint

Given the same scenario and step sequence, the final mission state must
be identical across repeated runs.

## 8. Phase 3 --- Observation Windows

Start with synthetic windows.

Example `demo.json`:

``` json
{
  "request_id": "OBS-B",
  "windows": [
    {
      "id": "WIN-B-1",
      "start": "2026-09-21T10:20:00",
      "end": "2026-09-21T10:30:00"
    },
    {
      "id": "WIN-B-2",
      "start": "2026-09-21T11:15:00",
      "end": "2026-09-21T11:25:00"
    }
  ]
}
```

Create a `WindowProvider` interface immediately so synthetic generation
can later be replaced by Skyfield/SGP4.

### Checkpoint

Every demo observation request has at least one known window, and at
least one task has two windows so replanning can visibly move it.

## 9. Phase 4 --- Constraint Engine

Implement pure functions for:

``` text
window containment
deadline
time overlap
battery
storage
satellite availability
```

Return structured violations, not booleans alone.

Example:

``` json
{
  "valid": false,
  "violations": [
    {
      "code": "TIME_OVERLAP",
      "request_id": "OBS-C"
    }
  ]
}
```

### Checkpoint

Write one passing and one failing unit test for every constraint before
implementing the planner.

## 10. Phase 5 --- Greedy Baseline Planner

Implement the baseline before OR-Tools.

Pseudo-code:

``` python
tasks = sorted(
    tasks,
    key=lambda t: (-t.priority, t.deadline, t.duration_seconds, t.id)
)

scheduled = []

for task in tasks:
    candidate_windows = sorted(valid_windows(task), key=lambda w: w.start_time)

    for window in candidate_windows:
        candidate = earliest_feasible_action(task, window, scheduled)

        if validator.is_valid(candidate):
            scheduled.append(candidate)
            break
```

The planner output must include unscheduled tasks and reasons.

### Checkpoint

Run:

``` text
5–10 tasks
1 satellite
multiple windows
battery/storage limits
```

Expected result:

-   no overlapping scheduled actions;
-   all actions inside valid windows;
-   no deadline violations;
-   resource constraints satisfied;
-   deterministic output.

At this point print the plan in CLI. If this does not work, do not start
the UI.

## 11. Phase 6 --- Metrics v1

Implement immediately after the baseline planner:

``` text
mission utility
scheduled/completion rate
constraint violations
planning time
battery utilization
storage utilization
```

This gives a baseline for later replanning comparison.

### Checkpoint

`metrics(plan_v1)` returns a serializable result with no UI dependency.

## 12. Phase 7 --- Event Engine

Implement events one at a time.

### Event 1: Cloud Block

``` text
Input:
request/window + event time

Effect:
selected observation window becomes invalid
```

This is the best first replanning demonstration because the cause/effect
is easy to verify.

### Event 2: Battery Drop

``` text
Input:
new battery value

Effect:
mission state battery changes
future plan is revalidated
```

### Event 3: Emergency Task

``` text
Input:
new high-priority observation request

Effect:
request and its windows are added
remaining plan must be reconsidered
```

### Checkpoint

Each event changes domain state correctly without invoking the replanner
automatically.

Keep event application and replanning as separate operations.

## 13. Phase 8 --- Impact Analyzer

Input:

``` text
current mission state
Plan v1
event
current tasks/windows
```

Output:

``` text
completed/frozen actions
unaffected future actions
affected actions
invalid actions
reason codes
```

### Checkpoint

For the cloud demo, only the action using the blocked window should
become invalid unless secondary resource/timing effects exist.

## 14. Phase 9 --- Adaptive Replanner

For a 2--3 day sprint, do not over-engineer incremental optimization.

Use this strategy:

``` text
freeze completed/past actions
      ↓
retain feasible future actions when practical
      ↓
collect affected + unscheduled + newly arrived tasks
      ↓
run baseline planner on remaining problem
      ↓
merge with frozen history
      ↓
validate entire future plan
      ↓
create Plan v2
```

If preserving feasible future actions makes implementation unstable,
regenerate all future actions while freezing completed history. Record
resulting plan churn.

### Checkpoint

Cloud demo must produce:

``` text
Plan v1:
OBS-B @ 10:20

Event:
WIN-B-1 blocked

Plan v2:
OBS-B @ 11:15
```

If no alternative exists, `OBS-B` must be dropped with
`NO_ALTERNATIVE_WINDOW`.

## 15. Phase 10 --- Plan Diff

Implement:

``` text
UNCHANGED
MOVED
INSERTED
DROPPED
COMPLETED
```

Diff by request ID rather than array position.

### Checkpoint

The cloud example returns `MOVED` for `OBS-B` with both timestamps.

## 16. Phase 11 --- Decision Trace

Do not use an LLM.

Store structured records:

``` json
{
  "request_id": "OBS-B",
  "reason_code": "WINDOW_INVALIDATED",
  "previous_action": {
    "start": "10:20"
  },
  "new_action": {
    "start": "11:15"
  },
  "message": "OBS-B moved because its original observation window was invalidated. A later feasible window was selected."
}
```

### Checkpoint

Every `MOVED`, `INSERTED`, or `DROPPED` result has a trace.

`explanation_coverage` should equal `1.0` in the demo.

## 17. Phase 12 --- Replanning Metrics

Add:

``` text
replanning time
utility before/after
completion before/after
violations before/after
plan churn
explanation coverage
```

### Checkpoint

A single comparison object can be serialized and returned to the
frontend.

## 18. Phase 13 --- FastAPI

Only now expose the working core.

Implement:

``` text
POST /scenarios
POST /scenarios/{id}/windows/generate
POST /scenarios/{id}/plan
GET  /scenarios/{id}/state
POST /scenarios/{id}/simulation/step
POST /scenarios/{id}/events
POST /scenarios/{id}/replan
GET  /plans/{old}/compare/{new}
GET  /plans/{id}/traces
GET  /scenarios/{id}/metrics
```

Keep endpoint functions thin:

``` text
validate request
→ call application/domain service
→ return schema
```

Do not put scheduling logic inside route handlers.

### Checkpoint

Run the entire mission flow through API integration tests using `httpx`.

## 19. Phase 14 --- PostgreSQL

Persist:

``` text
scenario
requests
windows
plan versions
scheduled actions
events
decision traces
experiment metrics
```

Use SQLAlchemy repositories.

Do not let SQLAlchemy ORM objects become planner inputs. Convert
persistence records into domain models.

### Checkpoint

Restart backend and confirm Plan v1, event, Plan v2, and traces remain
retrievable.

## 20. Phase 15 --- Frontend

Build one dashboard.

### Components

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

### UI Priority

1.  scenario/load button;
2.  generate initial plan;
3.  initial timeline;
4.  mission state;
5.  inject event;
6.  replan;
7.  revised timeline;
8.  plan changes;
9.  explanations;
10. metrics;
11. map.

The map is useful but must not block the adaptive-planning loop.

### Checkpoint

A reviewer can run the complete demo without opening terminal or API
documentation.

## 21. Optional Phase --- OR-Tools CP-SAT

Only start this after the full greedy loop works.

Model one optional interval/decision per feasible task/window
assignment.

Conceptual objective:

``` text
maximize Σ(priority × scheduled)
```

Constraints include:

``` text
at most one assignment per request
no overlap
valid windows
deadline
battery/storage approximation
```

Both planners must use the same interface:

``` text
GreedyPlanner
CPSATPlanner
```

This allows later experimental comparison without changing simulation or
UI code.

## 22. Optional Phase --- Skyfield/SGP4

Do not start here.

Once synthetic windows work, implement:

``` text
SyntheticWindowProvider
OrbitalWindowProvider
```

Use static TLE files stored in the repository.

No live orbit API should be required.

## 23. Day-by-Day Sprint

## Day 1 --- Make Planning Work

### Morning

Build:

``` text
domain models
scenario loader
mission state
synthetic window provider
constraint engine
```

### Afternoon

Build:

``` text
greedy planner
plan validator
baseline metrics
unit tests
demo scenario
```

### Day 1 Exit Requirement

This command-level flow works:

``` text
load scenario
→ generate windows
→ generate Plan v1
→ validate Plan v1
→ print schedule + metrics
```

If Day 1 ends without a valid schedule, do not work on frontend polish.

## Day 2 --- Make Adaptation Work

### Morning

Build:

``` text
cloud event
battery event
emergency-task event
impact analyzer
```

### Afternoon

Build:

``` text
adaptive replanner
plan versioning
plan diff
decision trace
replanning metrics
integration tests
```

### Day 2 Exit Requirement

This flow works entirely in backend tests:

``` text
Plan v1
→ inject cloud event
→ detect OBS-B invalid
→ replan
→ Plan v2
→ compare
→ explain
→ metrics
```

This is the core research demonstration.

## Day 3 --- Make It Demonstrable

### Morning

Build:

``` text
FastAPI endpoints
PostgreSQL repositories
Docker Compose
```

### Afternoon

Build:

``` text
React dashboard
timeline
event controls
before/after comparison
decision trace panel
metrics
basic 2D map
```

### Day 3 Exit Requirement

One local command starts the system and the complete demo is executable
from the browser.

## 24. Four-Person Parallel Split

If four members are available:

  Member     Primary Ownership
  ---------- -------------------------------------------------
  Member 1   Domain models, simulator, windows, event engine
  Member 2   Constraints, greedy planner, replanner, metrics
  Member 3   React dashboard, timeline, map, comparison UI
  Member 4   FastAPI, PostgreSQL, Docker, integration tests

Before parallel work begins, agree on the domain schemas and API
contracts. Otherwise integration will consume the sprint.

## 25. Test Checkpoints

### Unit

``` text
domain serialization
each constraint rule
greedy ordering
window selection
event state mutation
plan diff classification
metric calculations
```

### Integration

``` text
scenario → plan
plan → cloud event → replan
plan → battery drop → replan
plan → emergency task → replan
replan → validate
replan → traces
```

### Determinism

Run the same scenario twice and assert:

``` text
same scheduled requests
same start times
same plan utility
same reason codes
```

Planning-time milliseconds may differ and should not be part of
deterministic equality.

## 26. Demo Scenario Design

Use a scenario deliberately designed to prove replanning.

Example:

``` text
SAT-001

OBS-A priority 5
OBS-B priority 4, windows at 10:20 and 11:15
OBS-C priority 3
OBS-D priority 2
OBS-E priority 1
```

Plan v1 schedules `OBS-B` at `10:20`.

Inject:

``` text
CLOUD_BLOCK(WIN-B-1)
```

Expected:

``` text
OBS-B old: 10:20
OBS-B new: 11:15
reason: WINDOW_INVALIDATED
```

A second demo can reduce battery enough that a lower-priority task is
dropped.

A third demo can insert a priority-5 emergency task and show resulting
schedule changes.

## 27. What to Cut First

If behind schedule, cut in this order:

``` text
1. Cesium / advanced 3D
2. OR-Tools second planner
3. Skyfield/SGP4 window calculation
4. experiment browser
5. full replay controls
6. extra event types
7. sophisticated charts
8. animations
9. LLM explanations
10. advanced planning algorithms
```

Use synthetic windows and the greedy planner instead.

## 28. What Must Never Be Cut

The project loses its core research value if any of these disappear:

``` text
mission scenario
mission state
observation windows
constraints
initial planner
controlled event
impact detection
adaptive replanning
plan comparison
decision trace
metrics
repeatability
```

## 29. Engineering Rules

-   Do not couple planning logic to React.
-   Do not put scheduling logic in FastAPI routes.
-   Do not make PostgreSQL ORM models the core domain model.
-   Do not mutate Plan v1 during replanning.
-   Do not generate explanations without structured reason codes.
-   Do not use an LLM to decide the schedule.
-   Do not depend on live APIs for the demo.
-   Do not build advanced visualization before the backend loop works.
-   Do not add algorithms until the baseline can be measured.
-   Keep all scenarios reproducible.

## 30. Final Sprint Verification

Before declaring the MVP complete, execute:

``` text
[ ] Load deterministic demo scenario
[ ] Generate observation windows
[ ] Produce Plan v1
[ ] Validate Plan v1
[ ] Display baseline metrics
[ ] Advance simulation
[ ] Inject CLOUD_BLOCK
[ ] Detect affected action
[ ] Produce Plan v2
[ ] Validate Plan v2
[ ] Compare Plan v1 and Plan v2
[ ] Generate decision trace
[ ] Display replanning metrics
[ ] Repeat scenario and verify deterministic result
[ ] Run complete workflow locally without live APIs
```

If these checks pass, the project has a defensible MVP of adaptive
Earth-observation mission planning. Advanced orbital fidelity,
optimization methods, visualization, and AI-assisted interfaces can then
be added without changing the core architecture.
