# AMIS Implementation Status

Source of truth: `.doc/specs/AMIS_Build_Spec.md` (wins on conflict), with `AMIS_PRD.md`, `AMIS_SRD.md`, `AMIS_Implementation_Guide.md` as reference.
Glossary: `CONTEXT.md`.

Date: 2026-09-25
Method: code read of `amis/`, `frontend/src/`, `tests/`, plus test runs.

## Evidence

* Backend: `python -m pytest tests -q` → `136 passed`
* Frontend: `npm --prefix frontend run test -- --run` → `12 files, 139 passed`
* Demo: `python -m amis.demo` →
  * Plan v1: `OBS-B @ 10:20`, Plan v2: `OBS-B @ 11:15`
  * `WINDOW_INVALIDATED`, plan churn `0.25`, explanation coverage `1.0`

## Headline counts

| Lens | Implemented |
| --- | --- |
| Build Spec phases 1–16 | 16/16 |
| Build Spec user stories 1–117 | 117/117 functionally |
| PRD FR-01–FR-12 | 12/12 |
| PRD success criteria 1–12 | 12/12 |
| SRD required cases 1–14 | 14/14 |
| Never-cut 12 | 12/12 |
| Metrics 8/8 | 8/8 |
| Constraint checks 6/6 | 6/6 |
| MissionEvent types 3/3 in scope | 3/3 |
| ReasonCode 10/10 | 10/10 |
| PlanChangeType 5/5 | 5/5 |

## Phase-by-phase (Build Spec)

| Phase | Scope | Status | Location |
| --- | --- | --- | --- |
| 1 domain models | Scenario, Satellite, ObservationRequest, ObservationWindow, MissionState, ScheduledAction, MissionPlan, MissionEvent, Impact, Violation, PlanDiffEntry, MetricsResult, DecisionTrace, enums | Done | `amis/domain/` |
| 2 mission state and simulation lifecycle | clock, step, battery/storage accounting, started/completed, end clamp, reset, determinism | Done | `amis/session.py:step`, `test_simulation_lifecycle.py` |
| 3 observation windows | WindowProvider protocol + SyntheticWindowProvider, OBS-B has two windows, deterministic | Done | `amis/windows/`, `amis/demo.py:CanonicalWindowProvider` |
| 4 constraint engine | window containment, deadline, overlap, projected battery, projected storage, satellite availability + whole-plan aggregate, unfrozen-only | Done | `amis/constraints/`, `test_constraint_*.py`, `test_window_containment.py` |
| 5 greedy planner | Planner protocol + GreedyPlanner, order priority desc → deadline asc → duration asc → id asc, stability rule, unscheduled with ReasonCode, empty plan not error | Done | `amis/planning/`, `test_greedy_planner.py` |
| 6 metrics | mission utility (deduped scheduled/completed), completion rate, violation count, planning time, battery/storage utilisation | Done | `amis/metrics.py`, `test_metrics.py` |
| 7 demo script | `python -m amis.demo`, canonical replan demo prints plan/comparison/traces/metrics | Done | `amis/demo.py` |
| 8 event engine | CLOUD_BLOCK, BATTERY_DROP, EMERGENCY_TASK one at a time, no auto-replan, Scenario unchanged, INVALID_EVENT | Done | `amis/session.py:inject_event`, `test_*_event.py` |
| 9 impact analyzer | valid/invalid split, stored Impact with evaluated plan id, Frozen list | Done | `amis/impact.py`, `test_cloud_block_impact.py` |
| 10 adaptive replanner | freeze started, apply event, rebuild unexpired unfrozen RequestPool, same Planner interface, vN+1 + parent, validate, NO_ALTERNATIVE_WINDOW, stale parent → PLAN_VERSION_CONFLICT | Done | `amis/session.py:replan`, `test_replan.py`, `test_canonical_replan_demo.py` |
| 11 plan comparison | per request id, UNCHANGED/MOVED/INSERTED/DROPPED/COMPLETED, old/new start + ReasonCode, non-adjacent | Done | `amis/diff.py`, `test_plan_diff.py` |
| 12 decision trace | trace per changed ScheduledAction, fixed vocabulary, template text, no LLM, coverage 1.0 in demo | Done | `amis/trace.py`, `test_decision_trace.py` |
| 13 replanning metrics | replanning time, churn (unfrozen-only, null on zero), coverage (null on zero), pool tracking + mismatch flag | Done | `amis/metrics.py`, `test_replanning_metrics.py` |
| 14 REST API | thin routes over MissionSession, order enforcement via SIMULATION_STATE_ERROR, OpenAPI types | Done | `amis/api.py`, `test_rest_api.py` |
| 15 PostgreSQL | SQLAlchemy repositories + Alembic, same protocols, restart survival, id recovery, no ORM leak | Done | `amis/db/`, `amis/repositories.py`, `migrations/`, `test_sql_persistence.py` |
| 16 frontend | single dashboard, full loop from browser, one-command start | Done | `frontend/src/`, `docker-compose.yml` |

## Story-by-story (Build Spec 117)

* Scenario definition and loading 1–8: 8/8. Load bundled demo, create Scenario, start/end time, battery capacity/charge, storage capacity/usage, JSON roundtrip, Scenario immutable, INVALID_SCENARIO.
* Observation requests 9–15: 7/7. Stable id, lat/lon, priority 1–5, duration, deadline, energy/storage cost, status (pending/scheduled/completed/dropped/expired).
* Observation windows 16–20: 5/5. Generated per ObservationRequest, OBS-B has two, deterministic, validity flag + reason, provider interface.
* Initial planning 21–28: 8/8. Baseline, deterministic greedy, stated order, unscheduled with ReasonCode, empty plan with reasons, planning time ms, version + parent, immutable.
* Constraint validation 29–37: 9/9. Six rejections, Violation with ReasonCode + request id, whole-plan call, unfrozen-only.
* Simulation 38–44: 7/7. Fixed step, resource change on execution, started/completed, readable MissionState, end clamp + complete flag, reset clears plans/events/traces/impacts, determinism.
* Request expiry 45–47: 3/3. Expired on deadline pass, excluded from later plans, counts against completion rate.
* Event injection 48–55: 8/8. CLOUD_BLOCK by window id, BATTERY_DROP by value, EMERGENCY_TASK with request + explicit windows, chosen simulated time, inject/replan separate, event log, replay from Scenario + event log, INVALID_EVENT.
* Impact analysis 56–61: 6/6. Unfrozen valid/invalid split, Frozen at `start <= now`, ReasonCode list, cloud precision, readable before replan, evaluated plan id.
* Adaptive replanning 62–74: 13/13. Manual trigger, Frozen byte-identical, event applied first, reconsider unexpired unfrozen incl. dropped/introduced, same Planner interface, new version + parent, validated, stability rule, move to later window, NO_ALTERNATIVE_WINDOW drop, replanning time, no-event replan identical, stale parent rejected.
* Plan comparison 75–79: 5/5. By request id, five change types, old/new start, ReasonCode, any two versions.
* Explanation 80–85: 6/6. Trace per change, fixed vocabulary, event/constraint/previous/new action, generated sentence, no language model, coverage 1.0 in demo.
* Metrics 86–97: 12/12. Mission utility deduped, completion rate, violations, wall-clock ms, battery/storage utilisation, churn unfrozen-only, coverage, null on zero denominator, pool id set, pool-mismatch flag, side-by-side, serialisable.
* Dashboard 98–111: 14/14 functionally. One dashboard, control strip, MissionState panel, 2D map, stacked timelines, changed marks, Frozen styling, unscheduled lists with ReasonCode, cloud dropdowns, trace panel, metrics panel, trace→timeline highlight, dark console, readable error + code.
* Reproducibility 112–117: 6/6. Offline, no-frontend loop via test/demo, one-command stack, restart survival, sequential ids from persisted state, diffable rerun excl. wall-clock.

Note: explanation UI lives in `PlanComparisonPanel.tsx` (`TraceLine`) rather than a separate `DecisionTracePanel.tsx`. Functionality present; file split differs.

## PRD / SRD cross-check

* FR-01 Scenario creation through FR-12 metrics: all present via MissionSession + API + dashboard.
* Demo acceptance: `SAT-001`, `OBS-A`–`OBS-E`, `OBS-B 10:20 → 11:15` via `WIN-OBS-B-1` block. Verified in demo output.
* SRD integration loop without frontend: `load → windows → plan v1 → validate → step → inject → impact → replan → validate v2 → compare → traces → metrics`. Covered by `test_session_integration.py`, `test_canonical_replan_demo.py`.
* REST minimum: all SRD endpoints present; Build Spec adds `GET /scenarios/{id}/impact`, `GET /plans/{id}/metrics`. Extra: `GET /demo/scenario`, `GET /scenarios/{id}/requests`, `GET /scenarios/{id}/windows`, `GET /scenarios/{id}/events`.
* Error codes: `INVALID_SCENARIO`, `INVALID_EVENT`, `CONSTRAINT_VIOLATION`, `RESOURCE_NOT_FOUND`, `SIMULATION_STATE_ERROR`, `PLAN_VERSION_CONFLICT`. `PLAN_INFEASIBLE` deliberately absent (greedy returns empty plan with reasons).

## Correctly absent (deferred / out of scope)

* OR-Tools CP-SAT planner (protocol exists, no implementation).
* Skyfield/SGP4 OrbitalWindowProvider (protocol exists, no implementation).
* `COMMUNICATION_OUTAGE`, `SATELLITE_UNAVAILABLE` (reserved in `EventType`, inject rejected).
* Solar recharge, downlink storage release, seeded generator, replay controls, experiment browser/benchmark screen, frontend isolation of expiry trace, 3D globe, language-model explanation, Kubernetes, auth.

## Reproduce

```powershell
python -m pytest tests -q
npm --prefix frontend run test -- --run
python -m amis.demo
```
