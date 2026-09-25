# AMIS project report

Date: 2026-09-25
Source: code read of `amis`, `frontend/src`, `tests`, plus `.doc/specs`, `.doc/adr`, and `CONTEXT.md`

This file follows the table of contents from the provided image. Headings use sentence case.

## Abstract

AMIS is a local simulator for Earth observation mission planning. It builds an initial observation plan under timing and resource limits, advances simulated time, injects a controlled disruption, marks affected work, rebuilds the remaining plan, and explains each change.

The system models one satellite called `SAT-001` and five requests called `OBS-A` through `OBS-E`. It generates observation windows, runs a deterministic greedy planner, validates against six constraints, and records immutable plan versions. A cloud block moves `OBS-B` from 10:20 to 11:15. Decision traces carry fixed reason codes. Metrics compare plan v1 and plan v2 side by side.

Backend tests report 136 passed. Frontend tests report 139 passed across 12 files. The demo reports churn 0.25 and explanation coverage 1.0. The full stack runs offline with FastAPI, PostgreSQL, and a React dashboard through Docker Compose. No language model takes part in planning or explanation.

## Introduction

Mission planning tools and operator dashboards often grow apart. Planning research tests algorithms in private rigs. Dashboards display data without a measurable planner underneath. A student or researcher who wants to watch a plan survive cloud cover, a battery drop, or an urgent request has no single place to run that experiment and repeat it.

AMIS closes that gap with one visible loop. The loop runs in this order: create scenario, generate windows, create plan v1, simulate, inject event, read impact, replan into v2, explain changes, compare and measure.

The build keeps fixed language from `CONTEXT.md`. Scenario, satellite, observation request, request pool, observation window, scheduled action, mission plan, planner, violation, mission state, mission event, frozen action, replan, impact, reason code, decision trace, plan diff, mission utility, plan churn, and explanation coverage each have one meaning. The report uses those terms throughout.

The single test seam is `MissionSession` in `amis/session.py`. Integration tests drive this object. Routes rebuild it from repositories per request, act, and write back. This keeps days 1 and 2 testable before any API exists.

## Literature survey

Published ISRO mission operations material describes practice for real Earth observation missions. NASA and JPL work on increasingly autonomous spacecraft informs the research framing. AMIS is not an ISRO product and claims no operational readiness. It addresses the integration layer, namely event driven replanning plus operator facing explanation plus reproducible measurement in one system.

Open MCT from NASA supplies interaction concepts. A single time context shared by all views, a now marker, activity swimlanes on a shared axis, and event markers on a strip all transfer at concept level. AMIS applies them as scenario bounds, backend `simulated_time` as the now marker, one row per request, windows as background bands, and mission events in their own lane.

World Monitor supplies product patterns only, with no copied code and no copied assets. Adopted patterns are one operational screen with no navigation, a dense panel shell, a map with correlated side panels where selection highlights the same entity elsewhere, a dense dark console theme, and a chronological event column that becomes the decision trace panel. Not adopted are dual 3D and 2D engines, Tauri packaging, multi variant builds, Redis and CDN tiers, MCP and SDK and CLI layers, and live feeds. The license boundary matters here because World Monitor is AGPL-3.0-only.

Orbit.ctrl supplies loose frontend patterns for query hooks plus a small selection store. AMIS implements this as one custom hook that owns server data and a shared selection slice, with explicit refetch after each mutation and no polling.

For planning methods, the baseline is deterministic greedy sorting by priority descending, deadline ascending, duration ascending, id ascending. OR-Tools CP-SAT is the documented next planner behind the same `Planner` protocol. For windows, synthetic generation is the baseline behind a `WindowProvider` protocol. Skyfield with SGP4 over static TLE files is the documented next provider. No live TLE service is required.

## Problem statement and objective

A researcher cannot today do all of the following in one place. Define a small satellite mission. Get a feasible initial plan. Advance mission time. Inject a controlled disruption. See which actions that disruption invalidated. Get a revised plan that respects executed work. Read why each request moved, arrived, or dropped. Compare two plans on utility, completion, violations, resource use, and churn. Do all of it offline and get the same answer on each run.

The objective is to make that loop visible and repeatable from one dashboard and from one command line demo.

Success means all of the following hold in one repeatable scenario. A mission with one satellite and at least five requests loads. Windows generate. The baseline planner produces a valid initial plan. Simulation advances state. A disruption injects. The system marks at least one affected action. The replanner produces a new plan without altering completed or past actions. The UI compares old and new plans. Each moved, dropped, or inserted request has a structured explanation. Metrics cover initial and revised plans. A rerun gives the same planning result. The full workflow runs locally with no live APIs and no language model.

Demo acceptance uses `SAT-001` and `OBS-A` through `OBS-E`. Plan v1 places `OBS-B` at 10:20. A cloud block on `WIN-OBS-B-1` marks that action infeasible. Replan places `OBS-B` at 11:15 in v2, then shows diff, trace, and metrics.

## Scope of the project

In scope for this build:

- One satellite with battery, storage, and availability flag
- Five to ten requests with target, priority, duration, deadline, and resource costs
- Deterministic synthetic windows from scenario configuration
- Six constraint checks with structured violations
- Deterministic greedy planner behind a replaceable interface
- Simulation engine with clock, resource accounting, expiry, and definite end
- Three event types at a chosen simulated time, namely `CLOUD_BLOCK`, `BATTERY_DROP`, `EMERGENCY_TASK`
- Impact analysis stored against the evaluated plan
- Adaptive replanning that freezes executed work and rebuilds the rest
- Immutable versioned plans with parent links
- Plan comparison keyed by request id
- Structured decision traces with generated text
- Eight metrics
- REST API with thin routes
- In memory repositories, then PostgreSQL with Alembic
- Single page React dashboard
- Command line demo through `python -m amis.demo`
- Docker Compose for db, api, and web

Out of scope for this build:

- Real satellite command and control
- Operational command generation
- Live ISRO, NASA, weather, or TLE feeds
- High fidelity orbital or flight dynamics engine
- Image processing
- Constellations
- Reinforcement learning, genetic algorithms, multi agent planning
- Kubernetes, microservices, cloud deployment
- Access control, authentication, alerting
- CesiumJS or 3D globe
- Language model integration in any role

Deferred until the loop works: `COMMUNICATION_OUTAGE` and `SATELLITE_UNAVAILABLE` events, CP-SAT planner, Skyfield and SGP4 provider, solar recharge, downlink storage release, seeded generator, replay controls, experiment browser, expiry traces, window drawing on the timeline.

Never cut: scenario, mission state, windows, constraints, initial planner, controlled event, impact detection, adaptive replanning, plan comparison, decision trace, metrics, repeatability.

## Proposed system

Backend owns the loop. API exposes it. Frontend displays it. PostgreSQL stores it.

```text
React TypeScript UI
Scenario, map, state, timeline, events, trace, metrics
|
| HTTP JSON
v
FastAPI API
Scenario, planning, simulation, events, metrics
|
+--> Mission state and simulation engine
+--> Planning core with planner and constraints
+--> Scenario and event engine
+--> Adaptive replanner with impact and plan diff
|
v
Decision trace and metrics
|
v
PostgreSQL
```

Domain model:

- Scenario holds id, name, start and end time, one satellite, list of requests. Immutable after load.
- Satellite holds id, battery capacity, starting charge, storage capacity, starting usage, availability flag.
- ObservationRequest holds id, target latitude and longitude, priority 1 to 5, duration, deadline, status, storage cost, energy cost. Never holds start time.
- ObservationWindow holds id, request id, satellite id, start, end, validity flag, optional invalidation reason. `OBS-B` holds two windows.
- MissionState holds scenario id, simulated time, satellite id, current battery, current storage usage, availability flag, active event ids, completed request ids, mission complete flag.
- ScheduledAction holds id, request id, satellite id, window id, start, end, status, expected energy and storage cost.
- MissionPlan holds id, scenario id, version, optional parent id, creation timestamp, actions, unscheduled requests each with reason code, utility, violation count, planning time. Immutable after creation.
- MissionEvent holds id, scenario id, event type, event time, typed payload.
- Impact holds id, event id, evaluated plan id, frozen ids, valid unfrozen ids, invalid unfrozen ids, reason codes. Written at injection, never recomputed.
- Violation holds reason code, request id, details.
- PlanDiffEntry holds request id, change type, optional old start, optional new start, reason code.
- MetricsResult holds plan id, utility, completion rate, violation count, timing, battery and storage utilisation, churn, coverage, pool size, pool id set. Churn and coverage allow null.
- DecisionTrace holds id, plan id, optional event id, optional request id, reason code, optional previous and new action, optional constraint name, generated message, metadata.

Enums: `RequestStatus` with pending, scheduled, completed, dropped, expired. `ActionStatus` with planned, started, completed. `EventType` with the three supported types plus two reserved. `PlanChangeType` with unchanged, moved, inserted, dropped, completed. `ReasonCode` with ten codes including `WINDOW_INVALIDATED`, `INSUFFICIENT_BATTERY`, `INSUFFICIENT_STORAGE`, `DEADLINE_VIOLATION`, `TIME_OVERLAP`, `SATELLITE_UNAVAILABLE`, `DISPLACED_BY_COMPETING_REQUEST`, `ALTERNATIVE_WINDOW_AVAILABLE`, `NO_ALTERNATIVE_WINDOW`, `REQUEST_UNCHANGED`.

Planner: greedy only. It sorts requests in the stated order, orders windows by the stability rule with prior window first if still valid, takes the earliest feasible candidate, else records unscheduled with reason. It never reads UI state and never mutates a prior plan.

Constraints: window containment, deadline, overlap, projected battery, projected storage, satellite availability, plus whole plan aggregate. Each returns violations with reason code and request id. Validation covers unfrozen actions only. Resources project forward in time order with no recharge and no downlink and floor at zero.

Simulation: `step` advances time, marks started and completed, charges costs on start, expires requests past deadline, clamps at end, sets complete, rejects further steps with `SIMULATION_STATE_ERROR`. `reset` returns to load time and clears plans, events, traces, impacts. An action with start at or before now is frozen, including in flight actions.

Events: injection changes state, records the event, writes impact, and never auto replans. Cloud block invalidates one window. Battery drop sets a new battery value. Emergency task adds a request plus explicit windows while the scenario object stays unchanged.

Replan: freezes started actions, applies event effects, rebuilds each unfrozen action from unexpired unfrozen requests, merges, validates unfrozen part, creates version N plus 1 with parent link, computes diff, generates traces, measures metrics. Replan carries expected parent id. Stale parent returns 409 with `PLAN_VERSION_CONFLICT`.

API routes are thin adapters:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/scenarios` | Create scenario |
| GET | `/scenarios/{id}` | Get scenario |
| POST | `/scenarios/{id}/windows/generate` | Generate windows |
| POST | `/scenarios/{id}/plan` | Generate initial plan |
| GET | `/scenarios/{id}/state` | Current mission state |
| POST | `/scenarios/{id}/simulation/step` | Advance simulation |
| POST | `/scenarios/{id}/events` | Inject event |
| GET | `/scenarios/{id}/impact` | Stored impact of latest event |
| POST | `/scenarios/{id}/replan` | Generate next version |
| GET | `/plans/{id}` | Retrieve plan |
| GET | `/plans/{id}/metrics` | Metrics for one plan |
| GET | `/plans/{old}/compare/{new}` | Plan comparison |
| GET | `/plans/{id}/traces` | Decision traces |

Errors use an envelope with code, message, details. Codes are `INVALID_SCENARIO`, `INVALID_EVENT`, `CONSTRAINT_VIOLATION`, `RESOURCE_NOT_FOUND`, `SIMULATION_STATE_ERROR`, `PLAN_VERSION_CONFLICT`. There is no `PLAN_INFEASIBLE` because an empty plan with reasons is a valid result.

Frontend is one dashboard. Panels are scenario controls, mission map, mission state, event panel, plan timeline, plan comparison, decision trace, metrics. Map uses MapLibre plus deck.gl. Timeline uses vis-timeline. The dashboard refetches on user action and never polls. Selection is shared across map, list, timeline, impact, comparison, and traces. The clock shown is backend `simulated_time`.

## Methodology used

Work followed domain first, then simulation, windows, constraints, planner, events, impact, replanner, diff plus trace, metrics, API, UI. The core loop had to work from tests before the API existed, and from the API before the dashboard existed.

Phases and acceptance:

- Phase 1 domain models. Test constructs a scenario, serialises to JSON, deserialises, all values survive. No module outside persistence imports SQLAlchemy.
- Phase 2 mission state and lifecycle. Same scenario plus same steps gives same final state. Step past end clamps, sets complete, further step raises `SIMULATION_STATE_ERROR`. Reset returns each field to loaded value.
- Phase 3 windows. Each demo request has at least one window, `OBS-B` has two, two runs give identical windows.
- Phase 4 constraints. One passing and one failing unit test per check, written before the planner. Each failure returns reason code plus request id. Aggregate skips frozen actions.
- Phase 5 greedy planner. With binding limits the plan has no overlaps, each action sits in a valid window, no deadline breaks, resources hold, unscheduled entries carry reasons, two runs match. Nothing fitting gives an empty plan with reasons, not an error.
- Phase 6 metrics. Metrics return a serialisable object with pool size and id set and no UI dependency.
- Phase 7 demo script. `python -m amis.demo` loads scenario, generates windows, produces v1, validates, prints plan and metrics.
- Phase 8 event engine. Each of the three events changes state, records in the log, never calls replanner, leaves scenario object unchanged.
- Phase 9 impact. Cloud demo marks only the action using the blocked window as invalid. Each impact names its evaluated plan. Frozen actions list separately.
- Phase 10 replanner. Cloud demo gives `OBS-B` at 10:20 in v1 and 11:15 in v2, or drops with `NO_ALTERNATIVE_WINDOW`. Frozen actions stay byte identical. Stale parent returns conflict. Replan with no event returns an identical plan as a new version.
- Phase 11 comparison. Cloud example returns `MOVED` for `OBS-B` with both timestamps. Comparison works for nonadjacent versions. Reorder of action list does not change result.
- Phase 12 trace. Each moved, inserted, dropped entry has a trace. Coverage is 1.0 for the demo. No language model import exists in the codebase.
- Phase 13 replanning metrics. One comparison object serialises for the frontend. Churn near zero for cloud demo. Churn and coverage return null on zero denominator. Cross pool comparison flags mismatch.
- Phase 14 REST API. Full flow runs through httpx tests. Routes stay thin. Out of order calls return `SIMULATION_STATE_ERROR`.
- Phase 15 PostgreSQL. Restart keeps v1, event, v2, impact, traces retrievable. Id counters recover from stored records. No ORM object reaches the planner.
- Phase 16 frontend. Reviewer runs the full demo from the browser. One command starts the stack.

Day plan: day 1 makes planning work through CLI. Day 2 makes adaptation work through backend tests. Day 3 makes it demonstrable through API, Postgres, Docker, and dashboard.

Team split from the guide: member 1 takes domain, simulator, windows, events. Member 2 takes constraints, planner, replanner, metrics. Member 3 takes dashboard, timeline, map, comparison. Member 4 takes FastAPI, PostgreSQL, Docker, integration tests. Domain and API contracts freeze before parallel work.

Test layers: integration through `MissionSession` as the primary layer, unit tests for pure logic, API contract tests through httpx ASGI transport, determinism tests that diff full output minus wall clock and timing fields.

## Hardware and software requirements

Software:

- Python 3.12 for backend
- FastAPI plus Uvicorn for HTTP API
- SQLAlchemy plus Alembic for persistence
- PostgreSQL 16 for stored experiments
- pytest plus httpx for backend tests
- Node with React plus TypeScript plus Vite for frontend
- React-Leaflet with Leaflet or MapLibre with deck.gl for 2D map, Recharts for metrics, date-fns for timeline formatting, fetch or Axios for REST
- Docker Compose for db, api, web services

The `pyproject.toml` in this repo pins FastAPI, Uvicorn, SQLAlchemy, Alembic, plus test extras for httpx, mypy, pytest, and a postgres extra for psycopg2.

Environment:

```text
AMIS_ENV=development
DATABASE_URL=postgresql+psycopg2://amis:amis@db:5432/amis
```

No live API keys are required. No language model is required.

Hardware: standard student laptop or lab machine is enough. The MVP scenario holds one satellite and five to ten requests. Planning and replanning should feel interactive at that size. No GPU is needed. Disk needs cover Postgres volume plus `node_modules` plus Python venv. Docker Desktop is needed only for the Compose path.

Run:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn amis.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Backend runs at `http://127.0.0.1:8000`. Frontend runs at `http://localhost:5173`. Backend must start first because the frontend fetches the OpenAPI schema on startup.

## Expected outcomes

The expected result is a working closed loop with proof, not a static dashboard.

Functional outcomes:

- Bundled demo loads with one command or one click
- Scenario holds bounded start and end, battery and storage settings, JSON roundtrip, immutable after load, invalid input rejected with a code
- Requests carry stable ids, target coordinates, priority, duration, deadline, energy and storage cost, visible status
- Windows generate per request, `OBS-B` has two, generation is deterministic, each window carries validity plus reason
- Plan v1 is deterministic greedy in the stated order, with unscheduled reasons, version plus parent, planning time, immutable after creation
- Validation rejects the six cases with reason code plus request id, validates whole plans in one call, covers unfrozen actions only
- Simulation steps by fixed seconds, charges resources on execution, marks started and completed, exposes readable state, clamps at end, resets cleanly, stays deterministic
- Expiry marks requests past deadline, excludes them from later plans, keeps them counted against completion
- Events inject cloud block by window id, battery drop by value, emergency task with request plus explicit windows, at chosen time, with injection kept separate from replan, with logged events and replay from scenario plus log
- Impact splits unfrozen actions into valid and invalid, freezes started actions, returns reason codes, stays precise for cloud, reads before replan, names evaluated plan
- Replan is manual, keeps frozen actions identical, applies event effects first, reconsiders unexpired unfrozen requests including dropped and introduced ones, uses the same planner interface, versions with parent, validates before return, keeps prior placement when still feasible, moves displaced requests to later windows or drops with `NO_ALTERNATIVE_WINDOW`, records replanning time, returns identical plan on no event replan, rejects stale parent
- Comparison keys by request id, classifies five change types, reports old and new start for moves, carries reason codes, works for any two versions
- Explanation gives one trace per change with fixed vocabulary, event plus constraint plus prior plus new action, generated sentence, no language model, coverage 1.0 in demo
- Metrics give deduplicated utility, completion rate, violation count, wall clock timing, battery and storage utilisation, unfrozen only churn, coverage, null on zero denominator, pool identity plus mismatch flag, side by side view, serialisable output
- Dashboard runs the full demo from the browser with control strip, state panel, 2D map, stacked timelines, change marks, frozen styling, unscheduled lists with reasons, cloud dropdowns, trace panel, metrics panel, trace to timeline highlight, dark console theme, readable errors with codes
- Reproducibility holds offline, from test or demo script with no frontend, from one command stack, across restarts, with sequential ids from persisted state, with diffable reruns minus wall clock fields

## Experiment results and discussion

Backend: `python -m pytest tests -q` reports 136 passed. Frontend: `npm run test -- --run` reports 12 files with 139 passed. Demo: `python -m amis.demo` prints v1 `OBS-B` at 10:20 and v2 at 11:15 with `WINDOW_INVALIDATED`, churn 0.25, coverage 1.0.

Build spec coverage recorded in `.doc/implementation-status.md` is 16 of 16 phases, 117 of 117 user stories functionally, 12 of 12 PRD functional requirements, 12 of 12 PRD success criteria, 14 of 14 SRD cases, 12 of 12 never cut items, 8 of 8 metrics, 6 of 6 constraint checks, 3 of 3 in scope event types, 10 of 10 reason codes, 5 of 5 change types.

Canonical cloud run verified through `test_canonical_replan_demo.py`: step 300 seconds, block `WIN-OBS-B-1`, impact shows invalid `ACT-002` with `WINDOW_INVALIDATED`, v2 moves `OBS-B` to 11:15, other placements unchanged, diff reports `MOVED`, coverage 1.0.

Battery run verified: step so `OBS-A` starts and charges, drop battery, impact marks future infeasible actions with `INSUFFICIENT_BATTERY`, v2 keeps feasible prefix and drops the rest with reasons, utility falls while churn and coverage measure the change.

Emergency run verified: priority 5 emergency request with explicit window enters the pool, v2 schedules it and displaces at least one existing request with `DISPLACED_BY_COMPETING_REQUEST`, pool mismatch flag is true, utility reflects the new pool.

Production wiring now uses `ProductionWindowProvider` in `amis/main.py`. Canonical demo ids get canonical multi window sets. Other ids get synthetic single windows. This keeps the browser demo on the intended story.

Discussion: the audit in `AMIS_FULL_SYSTEM_AUDIT.md` still lists cautions. The planner tries one start per window, so a wide window with an early overlap can drop a request that could fit later in the same window. Resource projection checks the candidate start but does not recheck later committed actions that the candidate may starve. Lifecycle guards are thin for repeat plan, repeat window generation after events, and post completion operations. SQL saves commit per table rather than in one transaction. Per scenario ids for events, impacts, and traces need composite keys. Emergency payloads need strict timezone and start before end checks. Multi event replans attribute all traces to the latest event. Violation count mirrors unscheduled count. Newly arrived but still unscheduled requests read as unchanged in diff. These items do not block the canonical single event demo, but they matter before release claims.

## Conclusion

AMIS delivers the full adaptive loop in one reproducible system. Scenario leads to windows, windows lead to plan v1, simulation leads to an event, impact leads to replan, replan leads to explanation, comparison, and metrics.

The design choices that carry the result are the `MissionSession` seam, immutable versioned plans, frozen started actions, stored impacts keyed to evaluated plans, reason codes before prose, greedy ordering with id tiebreak and stability rule, unfrozen only validation and churn, null on empty denominators, pool identity on metrics, thin API routes, and protocol based planner, window provider, and repositories.

The project is complete when the loop runs end to end, repeatably, offline. That condition holds for the canonical demo in tests, in the command line demo, and from the browser with current wiring.

## References

- `CONTEXT.md`, project glossary and fixed terms
- `.doc/specs/AMIS_Build_Spec.md`, single buildable specification and conflict authority
- `.doc/specs/AMIS_PRD.md`, product requirements, scope, demo acceptance
- `.doc/specs/AMIS_SRD.md`, software requirements, architecture, contracts, test cases
- `.doc/specs/AMIS_Implementation_Guide.md`, sprint order and checkpoints
- `.doc/AMIS_REDESIGN_CONTEXT.md`, redesign decisions and locked behavior
- `.doc/implementation-status.md`, phase and story counts plus reproduce commands
- `AMIS_FULL_SYSTEM_AUDIT.md`, independent audit with probes and gaps
- `.doc/adr/0001-mission-session-as-the-single-test-seam.md`
- `.doc/adr/0002-scenario-is-immutable-and-the-event-log-is-the-replay-unit.md`
- `.doc/adr/0003-frozen-actions-are-exempt-from-plan-validation.md`
- `.doc/adr/0004-replanning-runs-through-the-planner-protocol.md`
- `.doc/adr/0005-repository-plan-ids-include-the-scenario-id.md`
- `.doc/adr/0006-persistence-log-tables-skip-cross-table-foreign-keys.md`
- `amis/demo.py`, canonical and multi request demos
- `amis/session.py`, `amis/planning`, `amis/constraints`, `amis/impact.py`, `amis/diff.py`, `amis/trace.py`, `amis/metrics.py`
- `tests/test_canonical_replan_demo.py`, expected v1 to v2 behavior
- `frontend/src/App.tsx`, `frontend/src/state/useMissionSession.ts`, dashboard wiring
- World Monitor, Open MCT, orbit.ctrl, openmct-mcws, concept level references only
- OR-Tools CP-SAT and Skyfield with SGP4, documented future providers
