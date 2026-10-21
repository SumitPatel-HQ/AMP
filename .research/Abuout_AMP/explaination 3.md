## Technical deep dive

- Use these lines in front of examiner. Each bullet is one fact you can point to in code.

### Domain types and files

- `Scenario` in `amis/domain/scenario.py:86-116` is frozen dataclass with id, name, start, end, satellite, requests tuple. `to_dict` and `from_dict` give JSON round trip.
- `Satellite` in `amis/domain/scenario.py:16-22` has id, battery capacity and charge in Wh, storage capacity and usage in MB, available bool, plus optional `orbit`.
- `OrbitalElements` in `amis/domain/orbit.py` has norad id, name, international designator, epoch, omm dict, optional tle lines, source, retrieved at, sha256.
- `WindowPolicy` in same file has provider name plus max off nadir deg, min sun elevation deg, station ids, settling time s, culmination placement bool.
- `ObservationRequest` in `amis/domain/scenario.py:46-83` has id, target lat and lon, optional target name, priority 1 to 5, duration s, deadline with timezone, energy and storage cost, status.
- `ObservationWindow` in `amis/domain/window.py:11-18` has id, request id, satellite id, start, end, valid, invalid reason, plus peak time, peak elevation, min off nadir, sun elevation, source.
- `ContactWindow` is same idea for ground station. Derived, never persisted.
- `ScheduledAction` in `amis/domain/plan.py:12-49` has id, request id or None for downlink, satellite id, window id, start, end, costs, status, kind, station id. Downlink has negative storage cost.
- `MissionPlan` in `amis/domain/plan.py:68-110` has id, scenario id, version, parent id, created at, actions tuple, unscheduled tuple, utility, violation count, planning time ms, planner name, solver details or None.
- `MissionState` in `amis/domain/state.py:12-60` has clock, battery Wh, storage MB, available, active event ids, completed ids, mission complete.
- `MissionEvent` in `amis/domain/event.py:14-106` has CLOUD_BLOCK, BATTERY_DROP, EMERGENCY_TASK, PAYLOAD_OUTAGE, COMMUNICATION_OUTAGE.
- Say, all core types are frozen. Replan creates new plan, never edits old.

### Planner contract

- Protocol is `plan(scenario, state, requests, windows, previous_plan, plan_id, outages, contacts)` returns `MissionPlan`. See `amis/planning/protocol.py` and SRD section 7.
- Planner must not import FastAPI, React, Postgres. Only domain plus constraints plus windows. This keeps it unit testable.
- `select_planner` picks `greedy` or `cp_sat` by name. Name is stored on plan.

### Greedy internals in `amis/planning/greedy.py:62-274`

- Sort key is minus priority, deadline, duration, id. Ties always resolve same way.
- Skip COMPLETED and EXPIRED and frozen request ids.
- Group windows by request id.
- `ResourceProjection` starts from state battery and storage. Frozen PLANNED actions are committed first. Downlink reservations committed next.
- For each request in order:
  - Order candidate windows with stability rule. Previous window first if still valid, then earliest start. See `_ordered_candidates`.
  - Clamp window start to max of window start and sim time. You cannot schedule in past.
  - If culmination placement is on and peak fits, try peak centered start first. Else try window start first. See `_culmination_start` and `_candidate_starts_in_window`.
  - Also try instant right after each placed action plus settling gap, if it still ends inside window. This lets long windows pack many takes.
  - Check in order:
    - window containment
    - deadline
    - satellite availability plus outage intervals
    - projected battery and storage via `check_commit`
    - overlap plus min gap
  - First passing slot wins. Costs are copied from request.
  - If no slot, keep last violation. If zero windows, use NO_OBSERVATION_WINDOW for first plan or NO_ALTERNATIVE_WINDOW for replan. Else map violation via `_unscheduled_reason`.
- After loop, finalize downlinks, compute utility as sum priorities of scheduled ids, compute planning time with `perf_counter`, then set violation count from `validate_plan`.
- Frozen rule in `_frozen_actions` is `action.start <= sim_time`. Carried unchanged, still blocks time.
- Complexity is small. For R requests, W windows, P placed, checks are O(R times W times P). For 5 to 10 tasks it is instant, measured in ms.

### CP-SAT internals in `amis/planning/cp_sat.py`

- Wraps same greedy as baseline first. Never returns worse utility than baseline. Falls back if infeasible or worse.
- Normalizes time to int seconds from scenario start. Duration is ceiled. This fits CP-SAT int model with 1 s resolution.
- For each eligible request and each valid window:
  - Compute low equals ceil of max of window start, sim time, origin.
  - Compute high equals floor of min of window end, deadline, scenario end minus duration.
  - Skip if high less than low.
  - Create bool `present` plus int `start` in low to high plus optional fixed size interval of length duration plus gap.
  - At most one window per request with `sum literals <= 1`.
- Adds `NoOverlap` over all frozen plus optional intervals.
- Outage modeled with two bools before and after plus `BoolOr` enforced only if present.
- Resources modeled as knapsack with Fraction exact math:
  - Scale decimals to int with lcm of denominators.
  - Add sum cost times present less than or equal to budget.
  - Budget is state battery or free storage minus frozen committed.
  - Guard against 2 power 62 overflow.
  - Downlink release ignored in bound, kept conservative. Downlink gains kept via baseline fallback.
- Objective is maximize weighted priority:
  - Weight equals len eligible plus 1.
  - Term equals priority times weight plus 1 if same window as previous plan.
  - This keeps stability without losing utility rank.
  - If culmination on, subtract sum of distance to centered target scaled so geometry never beats priority. Scale equals sum ranges plus 1.
- Solver settings for determinism:
  - `num_search_workers = 1`
  - `random_seed = 0`
  - `max_deterministic_time` default 1.0
- Output stores solver details with status, objective, bound, gap, fallback bool, ortools version, workers, seed, limit, weight, resolution.
- Explain step reuses greedy checkers to label unscheduled. If feasible but omitted by bounded search, label DISPLACED_BY_COMPETING_REQUEST, not broken window.

### Constraints in `amis/constraints/`

- `containment.py:17` checks start greater than or equal to window start and end less than or equal to window end.
- `deadline.py:14` checks end less than or equal to request deadline.
- `overlap.py:15` checks no intersect with placed plus min gap settling time.
- `availability.py:14` checks state available true and no overlap with outage intervals.
- `resources.py:21-120` has `ResourceProjection` that walks timeline in order, commits costs, checks battery floor at 0 and storage cap. Not just point check at candidate start.
- `plan_validation.py:35-74` runs all checks over unfrozen imaging actions. Frozen exempt per ADR-0003. Downlinks validated separately by subject key action id.
- Each violation has reason code plus subject key. Imaging key is request id. Downlink key is action id.

### Simulation in `amis/session.py:464-522`

- `step(seconds)` advances sim time deterministically.
- Marks PLANNED to IN_PROGRESS to COMPLETED based on start and end.
- Charges energy and storage on start, not on end.
- Expires requests where deadline passed and no completed action. Expired stays in pool, never scheduled again.
- Clamps at scenario end and sets mission complete.
- Same scenario plus same steps gives same state.

### Events, impact, replan, diff, trace, metrics

- `inject_event` in `amis/session.py` writes event, updates windows or state, then calls `analyze_impact` in `amis/impact.py:20-63` which runs `validate_plan` and splits unfrozen into valid and invalid with codes.
- `replan` in `amis/session.py:137-192` takes expected parent id, calls planner with previous plan, compares, builds traces, computes metrics.
- `compare_plans` in `amis/diff.py:58-165` keys by request id to UNCHANGED, MOVED, INSERTED, DROPPED, COMPLETED. Downlinks ignored.
- `build_traces` in `amis/trace.py:61-106` makes one trace per moved, inserted, dropped with event id, constraint, old action, new action, template sentence from `trace.py:29-58`.
- `compute_metrics` in `amis/metrics.py:30-123` gives utility, completion rate, violation count, planning time, battery use, storage use, churn, coverage. Churn equals changed unfrozen over unfrozen before. Coverage equals changed with trace over changed.

### Orbital math in `amis/orbital/geometry.py`

- Constants are R equals 6378.137 km, MU equals 398600.4418 km3 per s2.
- `mean_altitude_km` from mean motion rev per day via Kepler third law.
- `target_elevation_threshold` converts max off nadir to min elevation at target. Formula is 90 minus arcsin of ratio where ratio equals R plus h over R times sin off nadir. If ratio greater than or equal to 1, return 0.
- `off_nadir_angle` is inverse for verification.
- At 705 km:
  - 7.5 deg needs 81.7 deg elevation, 93 km offset
  - 30 deg needs 56.3 deg elevation, 415 km offset, about 120 s window
  - 45 deg needs 38.3 deg elevation, 751 km offset, about 220 s window
  - 0 deg horizon implies 64.3 deg off nadir, about 2860 km away
- Provider in `amis/windows/orbital.py` builds `EarthSatellite` from stored orbit, calls `find_events` at target with altitude equals threshold, pairs rise and set, handles open at start or end and double culmination, filters by sun with `(earth + target).at(t).observe(sun).apparent().altaz()`, rounds start up and end down to seconds, drops shorter than duration, numbers `WIN-request-n`, fills source string with skyfield and sgp4 versions.

### API and persistence

- Base is `http://127.0.0.1:8000`. Frontend is `http://localhost:5173`. Backend must start first because frontend fetches OpenAPI on load.
- Key routes in `amis/api.py:71-317`:
  - POST `/scenarios` creates scenario
  - GET `/scenarios` lists summaries
  - POST `/scenarios/{id}/windows/generate` builds windows, refused after plan exists
  - POST `/scenarios/{id}/plan` makes v1 with planner name
  - GET `/scenarios/{id}/state` reads clock and resources
  - POST `/scenarios/{id}/simulation/step` advances time
  - POST `/scenarios/{id}/events` injects disruption
  - POST `/scenarios/{id}/replan` makes next version
  - GET `/plans/{old}/compare/{new}` diffs
  - GET `/plans/{id}/traces` explains
  - GET `/scenarios/{id}/metrics` scores
  - GET `/examples`, GET `/orbital-elements`, GET `/scenarios/{id}/ground-track`, POST `/scenarios/validate` are Phase 2 additions
- DTOs in `amis/api_schemas.py` use `extra=forbid`. Bad fields fail fast.
- Tables are scenarios, satellites, observation requests, observation windows, mission states, mission plans, scheduled actions, mission events, impacts, decision traces, experiment results. See `amis/db/schema.py` and `migrations/versions/0001_initial_schema.py`.
- Repos have in memory and SQLAlchemy impl in `amis/repositories.py` and `amis/db/repositories.py`. One transaction per save.
- Migration 0002 adds nullable orbit JSON, window policy JSON, target name, peak fields, source. Old volume from edited 0001 needs reset or repair.

### Frontend data flow

- One hook owns server state in `frontend/src/state/useMissionSession.ts`.
- Map model in `frontend/src/map/missionMapModel.ts:88-117` draws satellite over current target in synthetic mode because domain has no position. Orbital mode adds backend ground track layer from same elements so map and windows agree.
- Timeline model in `frontend/src/timeline/missionTimelineModel.ts:187-223` draws windows as bands and actions as blocks.
- Plan compare labels in `frontend/src/state/planComparison.ts` must include new NO_OBSERVATION_WINDOW label.

### Determinism and offline guarantees to quote

- Sort keys include id. No dict order dependence. Requests and windows sorted before CP-SAT.
- Single worker, fixed seed 0, fixed deterministic time limit.
- Timescale uses built in tables, no download. Ephemeris is committed excerpt with sha256. Windows rounded inward to whole seconds.
- Element snapshot has source URL, retrieved at, sha256 per record. Scenario stores copy, not live ref.
- Validation rules are timezone required, end after start, unique request ids, lat lon range, priority 1 to 5, duration positive, costs non negative, charge less than or equal to capacity, mission within 14 days of epoch, max off nadir 0 to 60, horizon limit 7 days suggested.
- Tests to cite are `tests/test_replan.py`, `tests/test_rest_api.py`, `tests/test_emergency_request_event.py`, `tests/test_production_wiring.py`, `tests/test_battery_drop_event.py`, plus new orbital determinism test that runs generate twice and diffs JSON.