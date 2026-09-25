# AMIS Full-System Independent Implementation and Reference Audit

Audit date: 2026-09-25
Auditor mode: read-only. No source, test, schema, or dependency file was changed. This report is the only file created in the repository. Probe scripts, the regenerated OpenAPI document, the migrated scratch database, and the reference clones were kept outside the repository, in the system temp directory.

## Reproducibility record

| Item | Value |
| --- | --- |
| AMIS repository | `SumitPatel-HQ/AMP`, branch `main` |
| AMIS commit | `dec0bc2cd119705aa3bfd9bf0e178ab0ff30d58e` ("Polish mission workspace integration and stale-plan recovery") |
| AMIS working tree | Staged, uncommitted moves of documentation only (`docs/` to `.doc/`). No staged source changes. |
| World Monitor | `koala73/worldmonitor` at `b95863bddb4176585e717079cf2556230020af5d` (AGPL-3.0) |
| NASA Open MCT | `nasa/openmct` at `b589f7f4de94f847aa8660e90fd85c87fa5e4026` (Apache-2.0) |
| orbit.ctrl | `patrickkuei/Satellite-Mission-Control-Dashboard` at `89825ffc0a889cd555623aaf8568262e35e1b696` |
| openmct-mcws | `NASA-AMMOS/openmct-mcws` at `fe99c20e9d9abe54fdfe17d69f0096a62abaac69` |
| Authority order | `.doc/AMIS_REDESIGN_CONTEXT.md` first, then `.doc/specs/AMIS_PRD.md`, `AMIS_SRD.md`, `AMIS_Implementation_Guide.md`. `AMIS_Build_Spec.md` and `CONTEXT.md` were used as supporting detail where they do not conflict. |

### Verification commands run

| Check | Result |
| --- | --- |
| `pytest -q` (backend) | 136 passed |
| `vitest run --environment jsdom` (frontend) | 12 files, 139 tests passed |
| `tsc -p tsconfig.app.json --noEmit` | exit 0 |
| `oxlint` | exit 0, no findings |
| `mypy amis` | no issues in 42 files |
| `vite build` (output sent to a temp directory) | succeeds. The lazily loaded map chunk is 1.79 MB (498 kB gzip). |
| Generated types vs live schema | The OpenAPI document was generated in-process from `create_app()` and passed through `openapi-typescript`. The result is byte-identical to `frontend/src/api/schema.ts`. |
| `alembic upgrade head` on a scratch SQLite DB | succeeds. All 12 tables match `amis/db/schema.py` column for column. |
| `docker compose config` | valid |
| Docker / PostgreSQL runtime | **Not run.** The Docker Desktop engine was not running (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`). PostgreSQL behavior is inferred from code and from the same SQLAlchemy repositories running on SQLite. |
| End-to-end HTTP probes | Six probe scripts drove the FastAPI app through `TestClient`. They used the production wiring (`amis.main.build_app`), the in-memory repositories, and the SQLAlchemy repositories on migrated SQLite. The results are quoted in each finding. |

---

# Executive Summary

**Overall system health.** The domain model, the adaptive loop, the contract layer, and the frontend architecture are well built and well documented. Both test suites pass. But the system as shipped does not deliver the canonical loop to a user. Two independent defects stop it:

1. The production app generates one full-scenario window per request. The greedy planner tries only one start time per window. So the demo scenario loaded from the browser schedules only `OBS-A`, and the other four requests go unscheduled with `TIME_OVERLAP`. The `OBS-B` cloud-block story cannot happen in the browser (GAP-01, GAP-04).
2. With SQL persistence, which is the Docker Compose configuration, the event, impact, and trace tables use a global primary key on ids that repeat for every scenario. After the first event anywhere in the database, every later scenario fails its first event injection with HTTP 500. The failure also leaves a half-written state (GAP-02, GAP-06).

The passing test suites do not catch either defect. The REST tests always inject `CanonicalWindowProvider`, and the SQL tests never persist events for two scenarios.

**Backend and domain.** Mostly correct. The types are immutable dataclasses with symmetric `to_dict`/`from_dict`. The canonical terminology is used consistently. The constraint checks exist and the planner and impact analysis really call them. Defects: the planner's resource projection is not safe in time order (GAP-03), and it considers only one placement per window (GAP-04).

**Planner and replanner.** The ordering, the frozen-prefix handling, the "previous window first" stability rule, the empty-plan-with-reasons behavior, replan without an event (zero churn), and optimistic concurrency are all correct. Stability step 2 ("another placement in the previous window") is missing (GAP-04). The planner can emit a plan that its own `validate_plan` rejects (GAP-03).

**Simulation, events, and impact.** Stepping, the end clamp, expiry, reset (at session level), frozen in-flight behavior, and the persisted valid/invalid impact are all correct. The three event types work through the session and over HTTP. The emergency payload validation has a hole that permanently breaks a scenario (GAP-07). Lifecycle guards are missing for re-planning, window regeneration, and post-completion operations (GAP-05).

**Persistence.** The repositories convert strictly at the boundary. No ORM object leaks. Id counters recover from stored records. Rehydration per request works. There are two defects: the global primary keys on per-scenario ids (GAP-02) and a non-atomic save across tables (GAP-06).

**API and contracts.** Strong. The generated types match the live schema exactly. Events use discriminated unions. Every error is returned in the documented envelope. A stale parent returns `409 PLAN_VERSION_CONFLICT`. The routes are thin adapters with no business logic. One unsafe cast remains, and its comment is out of date.

**Frontend and integration.** The architecture is sound. There is one shared selection model and one mission clock (the backend's `simulated_time`). The timeline uses `vis-timeline` with windows as background bands. Impact and diff are shown from backend data, never recomputed. N/A renders as "N/A", not 0%. Invalidation is explicit, with no polling. The "Generate plan" control stays enabled after replans and events, and it triggers GAP-05 from the UI. TanStack Query, part of the stated stack, was never adopted. State is a hand-written `useState` hook. This is not a functional defect.

**Reference execution.** World Monitor had a real structural influence: MapLibre with the deck.gl `MapLibreOverlay` is the same map stack as World Monitor's `src/components/DeckGLMap.ts`, and the dense panel shell follows its layout. Open MCT concepts (a single time axis, a now marker, activity swimlanes, event markers) are transferred at the concept level. orbit.ctrl's hooks-plus-query and selection-store patterns are only loosely reflected. No sign of inappropriate adoption was found: no WebSockets, no LLM, no fake orbital tracks, and no client-side planning, impact, or diff.

**Testing and runtime.** The unit and domain tests are meaningful and specific. Integration coverage has blind spots that hid the two Critical defects (GAP-11). PostgreSQL was not exercised at runtime in this audit.

**Licensing and provenance.** No reference source code appears to have been copied. The one notice file is inaccurate: it is a source-file header template that claims AGPL-adapted portions and points to a `LICENSE` file that does not exist (GAP-12).

---

# System Findings

## Architecture matrix

| Area | Requirement | Actual implementation | Evidence | Status | Gap |
| --- | --- | --- | --- | --- | --- |
| Domain types | Canonical immutable domain types with round-trip serialization | Frozen dataclasses with `to_dict`/`from_dict` | `amis/domain/*.py`, `tests/test_domain_roundtrip.py` | CORRECT | — |
| Constraints | Availability, containment, deadline, overlap, battery, storage, used by the planner | All six are called by `GreedyPlanner.plan` and `validate_plan` | `amis/planning/greedy.py:119-131`, `amis/constraints/plan_validation.py` | CORRECT | — |
| Resource feasibility in time order | No action may be made infeasible by an action placed later in time | Projection only charges actions starting before the candidate. Later-starting committed actions are not re-checked. | `amis/constraints/resources.py:61-67`, probe A | INCORRECT | GAP-03 |
| Planner ordering | priority desc, deadline asc, duration asc, id asc | Implemented exactly | `greedy.py:83-91`, `test_greedy_planner.py` | CORRECT | — |
| Window placement | Earliest feasible placement, alternative placement inside the previous window | One candidate start per window (`max(window.start, now)`) | `greedy.py:117`, probe B | PARTIAL | GAP-04 |
| Empty plan behavior | Always return a `MissionPlan` with unscheduled reasons, no `PLAN_INFEASIBLE` | Implemented | `test_nothing_fits_produces_an_empty_plan...` | CORRECT | — |
| MissionSession facade | Single facade and test seam, rehydrated per request | `MissionSessionStore.load` then `restore`, and `save` | `amis/repositories.py:233-296` | CORRECT | — |
| Lifecycle guards | Invalid lifecycle operations return `SIMULATION_STATE_ERROR` | `plan()`, `generate_windows()`, `inject_event()`, `replan()` do not guard against an existing plan or a completed mission | `amis/session.py:91-118,251`, probes 1, 2, and 7 | PARTIAL | GAP-05 |
| Persistence keys | Per-scenario ids persist for many scenarios | `mission_events`, `impacts`, `decision_traces` use `id` as the only primary key | `amis/db/schema.py:177-233`, `migrations/versions/0001_initial_schema.py:163-226`, probe 5 | INCORRECT | GAP-02 |
| Persistence atomicity | One request's state change is committed or rejected as a unit | Each repository commits in its own transaction | `amis/repositories.py:272-296`, probe 5 follow-up | INCORRECT | GAP-06 |
| Simulation | Step, start/complete, resources, expiry, end clamp, reset | Implemented. Reset is session-only, with no route. | `session.py:437-506`, `test_simulation_lifecycle.py` | CORRECT | — |
| CLOUD_BLOCK | Window invalidated, persisted impact, move on replan | Correct when given multi-window providers | `test_canonical_replan_demo.py`, probe 2 | CORRECT in the backend, not reachable in production wiring | GAP-01 |
| BATTERY_DROP | Exact value, in-flight completes, future suffix validated | Correct | `test_battery_drop_event.py`, probe 6 | CORRECT | — |
| EMERGENCY_TASK | Immutable scenario, event-log arrival, replay | Correct for well-formed payloads. Naive or inverted timestamps accepted. | `test_emergency_request_event.py`, probe 4 | PARTIAL | GAP-07 |
| Impact | valid/invalid only, persisted against scenario, event, and evaluated plan | Implemented | `amis/impact.py`, `impacts` table | CORRECT | — |
| Replan and versioning | Frozen prefix kept, V1 immutable, parent link, stale parent returns 409 | Implemented | `test_replan.py`, `test_sql_persistence.py::test_a_concurrent_replan...` | CORRECT | — |
| Plan diff | Backend authoritative, five statuses, keyed by request id | Implemented. Newly arrived and still unscheduled requests are classified `UNCHANGED`. | `amis/diff.py:95-133` | PARTIAL | GAP-10 |
| DecisionTrace | Canonical reason codes, correct event linkage, no invented cause | Template-rendered, no LLM. Event linkage uses the latest impact only. Emergency insertions claim `ALTERNATIVE_WINDOW_AVAILABLE`. | `session.py:586-600`, `diff.py:111-114`, probes 2 and 6 | PARTIAL | GAP-08, GAP-10 |
| Metrics | Utility dedup, churn and coverage null on empty denominator, pool identity, mismatch flag | Implemented | `amis/metrics.py`, `test_metrics.py`, `test_replanning_metrics.py` | CORRECT | — |
| Violation metric | "Number of validation violations in the resulting plan" (SRD §17) | `len(plan.unscheduled)` | `greedy.py:180`, `metrics.py:73` | INCORRECT | GAP-09 |
| Deterministic ids | PLAN/ACT/EVT/IMP/TRACE counters recovered from records | Implemented with `ids.next_number` over stored ids | `amis/ids.py`, `test_id_counters_recover...` | CORRECT | — |
| API routes | Thin adapters, documented errors | Implemented. No domain logic in routes. | `amis/api.py` | CORRECT | — |
| Generated types | Types match the live schema, no manual interfaces | Byte-identical regeneration | temp regeneration diff | CORRECT | — |
| Frontend data layer | Query/invalidation after mutations, no polling | Manual `useState` hook with explicit refetch. No polling. No TanStack Query. | `frontend/src/state/useMissionSession.ts` | CORRECT (behavior), PARTIAL (stated stack) | — |
| Operational UI | Map and timeline dominant, compact controls, connected analysis | 3-column workspace, full-width timeline, analysis row | `frontend/src/App.tsx` | CORRECT | — |
| Map | Real targets, selection, event context, no fake telemetry | MapLibre + deck.gl. Targets from the request pool. Satellite drawn at a plan-derived position. | `frontend/src/map/missionMapModel.ts` | CORRECT (see note) | — |
| Timeline | `vis-timeline`, windows as bands, actions, events, now marker, frozen and impacted states | Implemented | `frontend/src/timeline/missionTimelineModel.ts`, `panels/PlanTimeline.tsx:261,387` | CORRECT | — |
| Cross-surface selection | One shared selection across the surfaces | `MissionSelection` in one hook, used by every panel | `useMissionSession.ts:470-520` | CORRECT | — |
| Tests and runtime | Meaningful behavior tested, production wiring tested | Strong unit tests. Integration tests bypass production wiring and multi-scenario SQL. | `tests/test_rest_api.py:60`, `tests/test_sql_persistence.py:30` | PARTIAL | GAP-11 |
| Provenance | Accurate notices where source is adapted | Notice file is a mis-templated header | `.doc/reference/THIRD_PARTY_NOTICES.md` | INCORRECT | GAP-12 |

## Backend / Domain Findings

- **Domain relationships and invariants are sound.** `ScheduledAction` links request, window, and satellite. `MissionPlan` carries `parent_plan_id` and `version`. `Impact` names `event_id` and `evaluated_plan_id`. `DecisionTrace` carries `previous_action` and `new_action` snapshots. `EmergencyRequestPayload` carries full request and window objects, so replay needs only the pristine scenario and the event log (`test_reapplying_the_event_log_to_the_untouched_scenario_reproduces_the_mission`).
- **Constraints are invoked, not just defined.** The planner calls all six in a fixed order (`greedy.py:119-131`). `validate_plan` runs all six per planned action and skips frozen actions, as ADR-0003 requires. Impact analysis runs `validate_plan` against the post-event state.
- **Resource semantics.** Battery decreases and storage increases on action start. There is no recharge and no downlink. The planning projection is a temporary `ResourceProjection`. The simulation mutates `MissionState`. All of this matches the locked decisions. The in-flight rule is also met: the cost is deducted when the action starts, so a battery drop during an in-flight action does not recharge the action. Battery floors at zero (`session.py:462`). One defect: the projection is not safe in time order (GAP-03).
- **Frozen definition.** `start <= simulated_time` is used consistently by the planner (`_frozen_actions`), impact (`impact.py:44`), and the timeline. A frozen action that is still `PLANNED`, which happens when a replan lands exactly on its start instant, is committed to the projection so its cost is not lost (`greedy.py:96-101`). This is correct.
- **Stability preference.** Step 1, the previous window first while still valid, is implemented in `_ordered_candidates`. Because the candidate start inside a window is fixed, "exact previous placement" is reproduced whenever the previous window is tried. Step 2, another placement inside the previous window, does not exist (GAP-04). Step 3, the earliest alternative, is only "the earliest window start", not the earliest feasible instant.
- **Unscheduled reason codes.** `_unscheduled_reason` maps a `WINDOW_INVALIDATED` failure to `NO_ALTERNATIVE_WINDOW` and an overlap failure to `DISPLACED_BY_COMPETING_REQUEST` when the request had a previous placement. This is reasonable. A request with no windows at all is reported as `WINDOW_INVALIDATED`. That is imprecise but not misleading enough to count as a gap.
- **Terminology.** `ObservationRequest`, `ObservationWindow`, `ScheduledAction`, `MissionPlan`, and `MissionEvent` are used throughout. `EMERGENCY_TASK` appears only as the wire enum. No ambiguity was found. The impact id prefix is `IMP` (`ids.py:22`), while the redesign context gives `IMPACT-001` as an example. The context says "e.g.", so this is noted, not flagged.
- **Id determinism.** `next_number` scans stored ids. Plan ids carry the scenario id (ADR-0005). Event, impact, and trace ids do not, which causes GAP-02 at the storage layer.

## Persistence Findings

- **No ORM leakage.** `amis/db/repositories.py` uses SQLAlchemy Core tables and converts through the domain `to_dict`/`from_dict`. Every public method returns domain types. The planner and domain never import `amis.db`.
- **Reads and writes trace to real tables.** Scenario, satellite, requests, windows (including emergency windows and cloud invalidation), mission state, plans, actions, unscheduled entries, events, impacts, and traces are all written in `MissionSessionStore.save` and read in `MissionSessionStore.load`. Probe 5 confirmed a full plan, step, event, and replan cycle survives on the SQL repositories for one scenario.
- **Rehydration.** `MissionSession.restore` rebuilds the request pool from the scenario plus emergency events. It rebuilds per-plan pool identity from `impact.evaluated_plan_id` versions, and it re-derives request statuses. Per-plan pool identity survives restart. So do id counters, since they come from the ids themselves.
- **Metrics are not persisted.** They are computed on demand. `experiment_results` exists in the schema and migration, but nothing writes to it (`schema.py:236-241` says so). The redesign context says only "metrics where designed", so this is consistent with the design.
- **PostgreSQL is really wired.** `amis/main.py:21-28` builds the SQL repositories when `AMIS_DATABASE_URL` is set. Compose sets it, and the API container runs `alembic upgrade head` before `uvicorn` (`Dockerfile` CMD). PostgreSQL is not decorative. It was not exercised live in this audit.
- **Defects.** Global primary keys on per-scenario ids (GAP-02). Non-atomic multi-table save (GAP-06). `with_for_update` on the plan row makes the replan conflict check sound inside the plans transaction. The other tables are not covered by that lock.
- **Reset persistence.** `MissionSession.reset` clears plans, events, traces, and impacts, and the test covers it. No route exposes reset. The SRD §18 minimum endpoint list does not require one, so this is not a gap. The frontend instead creates a fresh scenario id per "Load demo scenario". The persistence behavior of reset is therefore unreachable and UNVERIFIABLE.

## API / Contract Findings

- **Routes are thin.** Every handler is load, one session call, save, then `to_dict`. No scheduling or business rule lives in `amis/api.py`.
- **Error envelope.** Six codes are documented. `SimulationStateError`, `PlanVersionConflictError`, and `ConstraintViolationError` map to 409, invalid scenario or event to 400, not found to 404, and validation errors to 422 with a path-derived code. Probe 2 confirmed that a stale `expected_parent_plan_id` returns `409 PLAN_VERSION_CONFLICT`.
- **OpenAPI and generated types.** `separate_input_output_schemas=False` avoids `-Input`/`-Output` splits. Events are discriminated unions on `event_type`. The generated file matches the live schema exactly. `frontend/src/api/client.ts` exposes only aliases of generated types. There are no manual backend interfaces.
- **One unsafe cast.** `frontend/src/timeline/missionTimelineModel.ts:121` casts `event as unknown as { payload?: unknown }`. Its comment says "the generated API types only expose the CLOUD_BLOCK shape". That is no longer true: `MissionEventSchema` is a three-way union. This is a hygiene issue only. The runtime behavior is correct, so it is not listed as a gap.
- **Validation holes.** `ObservationWindowSchema` has no `start < end` check and no timezone requirement. `ObservationRequestSchema.deadline` requires a timezone only when it is nested in `ScenarioSchema`, because that check lives in `validate_scenario`. The emergency payload therefore bypasses both checks (GAP-07).
- **Lifecycle holes.** `POST /plan` and `POST /windows/generate` can be repeated at any time. `POST /events` and `POST /replan` are accepted after `mission_complete` (GAP-05).
- **Endpoints.** Every SRD minimum endpoint exists, except that metrics are served per plan (`/plans/{id}/metrics`) rather than per scenario. That per-plan form is version-bound and fits Prompt 6. Extra read routes (`/requests`, `/windows`, `/events`, `/impact`, `/demo/scenario`) are used by the frontend and are not speculative.

## Frontend / Integration Findings

- **The data layer does not bypass the API module.** Every network call goes through `src/api/amis.ts` and `openapi-fetch` with generated `paths`. There is no `fetch` or `axios` elsewhere.
- **No polling.** No `setInterval`, `refetchInterval`, or WebSocket exists in non-test sources. Every mutation (`generatePlan`, `step`, `injectEvent`, `replan`) explicitly refetches what it moved (`useMissionSession.ts`).
- **Backend-authoritative impact and diff.** `requestStatus.ts`, `planComparison.ts`, and `missionTimelineModel.ts` read `impact.invalid_unfrozen_action_ids`, `diff.entries[].change_type`, and `reason_code` directly. `comparisonRows` pairs backend diff entries with plan actions and does not classify anything itself. The one derived flag, `newlyArrivedUnscheduled`, compensates for a backend diff gap (GAP-10).
- **Impact and diff stay separate.** `ImpactPanel` shows the persisted impact against its evaluated plan. `PlanComparisonPanel` shows the diff. `requestStatus` applies the impact only when `impact.evaluated_plan_id === plan.id`.
- **Conflict handling.** On `PLAN_VERSION_CONFLICT`, `refreshAfterConflict` records the conflict, loads the backend's current plan, and shows `PlanConflictBanner`. Mutations are blocked while `stalePlan` is true. This is correct and visible.
- **N/A handling.** `formatPercent(null)` returns "N/A". Completion with an empty pool returns null and renders "N/A". Churn and coverage nulls render "N/A", not 0%.
- **Unscheduled requests stay visible.** `PlanTimeline.tsx:48-80` lists unscheduled requests under each plan. `MissionNavPanel` shows id, `P{priority}`, and the reason code for every request.
- **Event controls.** A compact popover under the mission bar. CLOUD_BLOCK uses a request dropdown and then a window dropdown. BATTERY_DROP and EMERGENCY_TASK use their real contracts. The emergency form always emits `Z` timestamps, so the browser path does not trigger GAP-07.
- **Mission clock.** There is one clock: `missionState.simulated_time` from the backend, drawn as the `vis-timeline` custom time (`PlanTimeline.tsx:387-392`) and in `MissionClock`. There is no local ticking clock.
- **Cross-surface identity (OBS-B case).** Selecting OBS-B sets `selection.requestId`. The nav list, map target (`selectedRequestId`), timeline group and items, impact rows, comparison rows, and traces all read the same field. Selecting a window also sets its request. Selecting an event sets the event plus its anchored request and window. This is coherent and not duplicated.
- **Map satellite marker.** The map draws the satellite over the target its current action observes, otherwise over the last observed target (`missionMapModel.ts:98-125`). The domain has no satellite position, so this position is derived. The code comment says so, and nothing claims orbital truth, so it is not flagged. The `planSequence` path joins targets in plan order. It is not a ground track, but it could be read as one. A legend label would remove the ambiguity.
- **Stated stack deviation.** TanStack Query is listed in the redesign context §8, and the orbit.ctrl reference uses it (`apps/web/src/hooks/useSatellites.ts`). AMIS never added it (`git log -S "@tanstack/react-query"` returns nothing). The hand-written hook implements the required invalidate-after-mutation behavior correctly, so this is recorded as a deviation, not a gap. Recharts is also unused. Prompt 6 makes charts optional.
- **Defects reachable from the UI.** "Generate plan" is enabled after plans, events, and replans (`MissionBar.tsx:206`), which triggers GAP-05. The demo loaded in the browser shows a one-action plan (GAP-01). With Compose, the first event of every scenario after the first fails (GAP-02).

## Reference Findings

| Reference | Exact reference file | Reference behavior | AMIS file | AMIS implementation | Classification |
| --- | --- | --- | --- | --- | --- |
| World Monitor | `src/components/DeckGLMap.ts` (imports `MapLibreOverlay` from `@deck.gl/maplibre`, `ScatterplotLayer`/`PathLayer`/`TextLayer`, `maplibre-gl`) | Vector basemap with a deck.gl overlay, interleaved mode, popups | `frontend/src/map/missionMapEngine.ts:1,104-105`, `map/missionLayers.ts`, `map/basemap.ts` | Same library stack and overlay approach. Non-interleaved. Different layer code. Own fallback basemap chain. | Structural adaptation |
| World Monitor | `src/components/Panel.ts` (`PanelOptions`, span/collapse persistence, severity) | Dense resizable panel grid with persisted spans | `frontend/src/panels/PanelFrame.tsx`, `App.tsx` grid, `index.css` | Thin-bordered dense panels in a fixed CSS grid. No persistence, no resize. The `index.css` header credits World Monitor as a conceptual reference. | Conceptual inspiration |
| World Monitor | top bar and status treatment (`src/app/*`, header components) | Compact status and navigation bar | `panels/MissionBar.tsx` | One-row mission bar: identity, clock, status chip, plan chip, compact controls | Conceptual inspiration |
| Open MCT | `src/plugins/plan/components/PlanView.vue`, `ActivityTimeline.vue` | Activities in swimlanes on a shared time axis, row packing | `panels/PlanTimeline.tsx`, `timeline/missionTimelineModel.ts` | One row per ObservationRequest, windows as background ranges, actions as ranges | Conceptual inspiration |
| Open MCT | `src/plugins/timeConductor/*` (`useClock.js`, `useTimeBounds.js`, `ConductorAxis.vue`) | One time context shared by every view, with bounds and a now indicator | `PlanTimeline.tsx:387-392`, `MissionBar.tsx` `MissionClock` | Scenario start and end as bounds, backend `simulated_time` as the now marker, one clock | Conceptual inspiration |
| Open MCT | `src/plugins/timeline/TimelineViewLayout.vue` | Stacked time strips sharing one axis | `PlanTimeline.tsx` (per-plan strips with the comparison) | Stacked current and previous plan strips | Conceptual inspiration |
| Open MCT | Event Timestrip | Event markers on a strip | `missionTimelineModel.ts` event items, `MISSION_EVENTS_GROUP_ID` lane | Event markers at `event_time`, mission-level events in their own lane | Unverifiable similarity. No `eventTimestrip` plugin directory was found at the inspected commit. |
| orbit.ctrl | `apps/web/src/hooks/useSatellites.ts` (TanStack `useQuery`), `apps/web/src/stores/selectedSatellite.ts` (Zustand) | Query hooks plus a small global selection store | `state/useMissionSession.ts` | One custom hook owns both the server data and a `MissionSelection` slice | Conceptual inspiration (weak) |
| openmct-mcws | provider classes such as `src/channelLimits/ChannelLimitsProvider.js` | Adapter and provider boundary between UI and services | `amis/repositories.py` protocols, `src/api/amis.ts` | Protocol-based repositories and a single API module | Unverifiable similarity. Same general pattern, no specific transfer. |

**Reference misuse audit.** No INAPPROPRIATE adoption was found. No World Monitor news, geopolitical, or AI layers exist. No orbit.ctrl LLM, MCP, WebSocket, anomaly, or 3D globe code exists. `test_no_language_model_is_imported_anywhere_in_the_codebase` enforces the no-LLM rule. There are no fake orbital tracks or telemetry, no second mission clock, and no client-side planning, impact, or diff. The Open MCT plugin architecture was not adopted.

## Test / Runtime Findings

**Well tested:** constraint checks one by one; planner ordering and tie-breaks; determinism; the 25 Wh five-action projection case (actions in time order only); expiry; the end clamp; reset (session); cloud impact including the "starts at event time is frozen" edge case; battery drop exact value and floor at zero; emergency immutability and replay; replan stability, frozen identity, parent link, and stale parent; diff keyed by request with non-adjacent comparisons; trace templates and the no-LLM guard; metrics dedup, the null denominators, pool mismatch, and churn that does not drift; SQL round trip and id recovery for one scenario; the REST lifecycle with the canonical provider; frontend view models (timeline, map, comparison, metrics, request status, transition) and panel interactions against a mocked API.

**Implemented but weakly tested:**
- REST tests always construct `create_app(window_provider=CanonicalWindowProvider())` (`tests/test_rest_api.py:60,370,...`). No test runs `amis.main.build_app()` wiring.
- SQL tests use one scenario each (`tests/test_sql_persistence.py`). None persists events, impacts, or traces for two scenarios.
- No planner test places a lower-priority action earlier in time than an already committed higher-priority action.
- No planner test puts two requests into one shared wide window.
- The frontend `App.test.tsx` mocks the whole `api/amis` module, so no frontend test exercises a real backend.

**Missing:** lifecycle guard tests (repeated plan, window regeneration after events, operations after completion); emergency payload timestamp validation; trace-to-event attribution with several events before one replan; save atomicity.

**Obsolete or misleading:** `test_domain_roundtrip.py:80-82` builds a plan with one unscheduled entry and `violation_count=0`, while the planner always sets `violation_count=len(unscheduled)`. The fixture describes a state the planner cannot produce. `test_metrics.py::test_violation_count_and_planning_time_pass_through_from_the_plan` confirms pass-through only, not the SRD meaning.

**Runtime:** Build, typecheck, lint, and mypy are clean. The migration applies cleanly and matches the schema. Compose configuration is valid. PostgreSQL connectivity, Compose startup, and browser-to-API integration were not run because the Docker engine was not running.

## Licensing / Provenance Findings

- World Monitor is AGPL-3.0 (`LICENSE`). Open MCT is Apache-2.0 (`LICENSE.md`).
- No AMIS file matched distinctive reference source. The AMIS map engine uses non-interleaved mode with its own layer builders. World Monitor's `DeckGLMap.ts` is a much larger class with interleaved-mode workarounds that AMIS does not contain. Shared use of the public MapLibre and deck.gl APIs is not source adaptation.
- `frontend/src/index.css:4-8` states "conceptual reference, no source copied". That is consistent with the code.
- `.doc/reference/THIRD_PARTY_NOTICES.md` contradicts this (GAP-12).

---

# Workflow Verification

## CLOUD_BLOCK

- **Does the complete flow work?** In the backend with a multi-window provider: yes. From the browser or Compose as shipped: no (GAP-01, GAP-02).
- **Actually verified.** `python -m amis.demo`-equivalent tests pass. Probe 2 over HTTP with `CanonicalWindowProvider` gave V1 `OBS-B@10:20`. The cloud block on `WIN-OBS-B-1` produced impact `{'ACT-002': ['WINDOW_INVALIDATED']}`. V2 has `OBS-B@11:15` and every other placement unchanged. The diff reports `MOVED`/`WINDOW_INVALIDATED`, the churn is 0.25, and the coverage is 1.0 (`test_canonical_replan_demo.py`).
- **Production wiring.** Probe 1 against `amis.main.build_app()` produced five windows, all `10:00-14:00`. V1 held only `OBS-A`. `OBS-B`, `OBS-C`, `OBS-D`, and `OBS-E` were unscheduled with `TIME_OVERLAP`. With no `OBS-B` action, the canonical story cannot start.
- **Persistence.** The window invalidation, event, and impact persist. On SQL, the second scenario's event fails with 500, and the invalidated window is left persisted without an event or impact (probe 5).
- **Plan and replan.** Correct given the windows.
- **Trace.** `OBS-B moved from 10:20 to 11:15 because its observation window was invalidated.` This is correct when the cloud block is the only event since V1. With a later event before the replan, the trace names the wrong event (GAP-08).
- **Metrics.** Before and after are measured at the same instant, with pool identity checked.
- **Frontend.** Request dropdown, then window dropdown, then inject. The injected event is selected. The impact panel and the timeline impacted class show the persisted impact. Replan sends `expected_parent_plan_id`. The comparison and traces load from the backend.
- **Proven failures.** GAP-01, GAP-02, GAP-06, GAP-08.

## BATTERY_DROP

- **Does the complete flow work?** Yes in the backend. From the browser it has little to act on, because V1 holds only `OBS-A` (GAP-01).
- **Actually verified.** Probe 6: step 300 s, so `OBS-A` has started and its cost is charged. Drop to 100 Wh. Impact: frozen `ACT-001`, invalid `ACT-004`/`ACT-005` with `INSUFFICIENT_BATTERY`. V2 keeps `OBS-A`, `OBS-B`, `OBS-C` and drops `OBS-D` and `OBS-E` with `INSUFFICIENT_BATTERY`. Traces are rendered. Churn 0.5, coverage 1.0, utility 15 to 12.
- **In-flight rule.** `test_frozen_in_flight_action_still_completes_and_battery_floors_at_zero` passes. The started action is excluded from validation (`validate_plan` skips non-`PLANNED`).
- **Persistence.** The event payload and state survive a restart (`test_battery_drop_and_emergency_task_payloads_survive_a_restart`). The same GAP-02 failure applies on SQL for later scenarios.
- **Metrics.** `violation_count` for V2 reports 2. That is the dropped-request count, not constraint violations (GAP-09).
- **Proven failures.** GAP-01, GAP-02, GAP-09. The planner time-order issue (GAP-03) can make a battery-constrained plan itself infeasible.

## EMERGENCY_TASK

- **Does the complete flow work?** Yes in the backend for well-formed payloads. The browser form produces well-formed payloads.
- **Actually verified.** Probe 6: priority-5 `OBS-EMERGENCY-1` with window `10:40-10:55`. V2 schedules it at 10:40 and drops `OBS-C` with `DISPLACED_BY_COMPETING_REQUEST`. `request_pool_mismatch` is true. The pool grows 5 to 6. Utility goes 15 to 17. The scenario is unchanged (`test_emergency_event_carries_the_complete_request_and_explicit_windows`). Replay from scenario plus events is identical (test).
- **Trace.** `OBS-EMERGENCY-1 was scheduled at 2026-09-21 10:40 because an alternative window was available.` That is not why it was scheduled (GAP-10).
- **Persistence.** Emergency windows persist through the window table. Restore rebuilds the pool from events.
- **Validation.** Probe 4: naive timestamps and an inverted window (`start > end`) are accepted with 201. Every later `step` and `replan` returns 500, and there is no reset route to recover (GAP-07).
- **Proven failures.** GAP-07, GAP-10, and GAP-05 (regenerating windows after an emergency deletes its windows).

---

# Final Proven Gaps

## GAP-01 — The running application cannot reproduce the canonical demo

**Severity:** Critical
**Status:** INCORRECT
**Area:** Integration

### Requirement
The demo scenario has at least one request with two windows (Build Spec story 17). The complete demo runs from the browser (Build Spec phase 16 acceptance). The redesign context requires that the canonical cloud demo move OBS-B to an alternate window and that the battery and emergency demos show their effects.

### Actual behavior
`amis.main.build_app()` calls `create_app()` with no `window_provider`, so sessions fall back to `SyntheticWindowProvider`. That provider gives each request one window spanning the whole scenario. Combined with GAP-04, the browser demo's Plan V1 schedules only `OBS-A`. The other four requests are unscheduled with `TIME_OVERLAP`. `OBS-B` has one window and no action, so neither the cloud-block move nor the other canonical workflows can be shown.

### Evidence
**AMIS**
- `amis/main.py:21-28`: `create_app()` and `create_app(build_repositories(engine))`, with no provider in either
- `amis/repositories.py:298-303` passes `window_provider=None`, and `MissionSession` then defaults to `SyntheticWindowProvider` (`amis/session.py:79`)
- `amis/windows/synthetic.py:15-28`: one window from `scenario.start_time` to `scenario.end_time`
- `amis/api.py:141-146`: `/demo/scenario` returns `build_canonical_replan_scenario()`, whose intended windows live only in `amis/demo.py:CanonicalWindowProvider`

**Tests**
- Probe 1 against `build_app()`: windows are all `10:00-14:00`. `V1 actions: [('OBS-A', '10:00')]`. Unscheduled: `OBS-B`, `OBS-C`, `OBS-D`, `OBS-E` with `TIME_OVERLAP`.
- Every REST test passes `CanonicalWindowProvider` explicitly (`tests/test_rest_api.py:60`), so the production path is never tested.

### Why this is a real defect
The product's core demonstration (Plan V1, then cloud block, then OBS-B moves) cannot happen in the shipped application, whether it runs through `uvicorn amis.main:app` or through Docker Compose.

### Smallest reasonable correction
Wire a window provider that produces the canonical windows for the canonical demo scenario in the production app factory. For example, choose the provider per scenario, or pass `CanonicalWindowProvider` for scenarios built from `/demo/scenario`. Keep `SyntheticWindowProvider` for other scenarios. GAP-04 must also be fixed for synthetic windows to be usable.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes (add a test that runs through `amis.main.build_app()`)

## GAP-02 — Event, impact, and trace ids collide across scenarios in SQL persistence

**Severity:** Critical
**Status:** INCORRECT
**Area:** Persistence

### Requirement
Deterministic per-scenario ids (`EVT-001`, `IMP-001`, `TRACE-001`) persist through PostgreSQL for any number of scenarios. PostgreSQL is the real persistence under Compose.

### Actual behavior
`mission_events`, `impacts`, and `decision_traces` declare `id` as the only primary key. The ids restart at 001 for every scenario. The second scenario to inject an event anywhere in the database fails with an `IntegrityError`, which reaches the client as HTTP 500. The frontend creates a new scenario id on every "Load demo scenario", and the Compose database volume persists between runs. So after the first event ever recorded, every later session fails at its first event.

### Evidence
**AMIS**
- `amis/db/schema.py:177-181` (`mission_events`), `:194-198` (`impacts`), `:214-218` (`decision_traces`): `Column("id", String, primary_key=True)`
- `migrations/versions/0001_initial_schema.py:163, 181, 204`: same keys
- `amis/ids.py:17-22`: prefixes carry no scenario id. Only plan ids are scoped (ADR-0005).
- `frontend/src/state/useMissionSession.ts:158-161`: a new scenario id per demo load

**Tests**
- Probe 5, SQL repositories on migrated SQLite: scenario A gives `event 201 replan 201`. Scenario B gives `event 500 replan 500` and `events for B []`.
- `tests/test_sql_persistence.py` never persists events for two scenarios.

### Why this is a real defect
The Compose deployment breaks the event, impact, and replan loop for every scenario after the first.

### Smallest reasonable correction
Make the primary key `(scenario_id, id)` on the three tables, which matches `observation_windows` and `observation_requests`. An alternative is to scope the ids as ADR-0005 does for plans. Composite keys keep the wire ids unchanged.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** Yes
**Frontend changes:** No
**Migration required:** Yes
**Test changes:** Yes

## GAP-03 — Planner resource projection ignores actions that start later in time

**Severity:** High
**Status:** INCORRECT
**Area:** Planner

### Requirement
Chronological resource feasibility: the planner must not produce a plan whose actions cannot all be afforded in time order (redesign context §9, "Resource projection").

### Actual behavior
`ResourceProjection.available_at(t)` subtracts only committed actions with `start <= t`. The planner commits requests in priority order, not time order. A lower-priority action placed before an already committed higher-priority action is checked only against the battery at its own start. It can consume battery that the later action needs. The resulting plan fails `validate_plan`, yet the plan reports `violation_count=0`.

### Evidence
**AMIS**
- `amis/constraints/resources.py:61-67` (`available_at`)
- `amis/planning/greedy.py:117-131`: only the candidate is checked, and committed later actions are never re-checked

**Tests**
- Probe A: battery 100. HIGH (priority 5) costs 80 at 01:00. LOW (priority 1) costs 50 at 00:00. The planner schedules both. `validate_plan` then returns `('HIGH', 'INSUFFICIENT_BATTERY', {'required_wh': 80, 'available_wh': 50})`.
- `test_five_actions_costing_20_wh_...` covers only actions placed in time order.

### Why this is a real defect
The planner emits infeasible plans. In simulation, the battery floors at zero and the high-priority observation runs without the energy it needs. The metrics show no violation.

### Smallest reasonable correction
When testing a candidate, check the projection at the candidate and at every committed action that starts at or after it. In other words, confirm the remaining balance never goes negative across the whole committed timeline. Apply the same rule to storage.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-04 — Planner considers only one start time per observation window

**Severity:** High
**Status:** PARTIAL
**Area:** Planner

### Requirement
Stability preference step 2, "another feasible placement in the previous window", and step 3, "earliest feasible alternative" (redesign context §9).

### Actual behavior
Each window yields one candidate, `max(window.start, simulated_time)`. If that instant overlaps another action, the window is rejected, even when most of the window is free. Step 2 does not exist, and step 3 means "the earliest window start" rather than the earliest feasible time.

### Evidence
**AMIS**
- `amis/planning/greedy.py:116-118`

**Tests**
- Probe B: R1 and R2 each have a 2-hour window starting at 00:00, and each needs 10 minutes. The plan is `[('R1','00:00')]`, with `R2` unscheduled with `TIME_OVERLAP`.
- Probe 1 shows the same failure on the production demo.

### Why this is a real defect
Feasible requests are dropped. With realistic wide windows, the plan degenerates to one action (GAP-01). Replans also report `TIME_OVERLAP` or `DISPLACED_BY_COMPETING_REQUEST` when a later slot in the same window was free.

### Smallest reasonable correction
Within each window, also try the earliest instant after each conflicting committed action that still fits the window and the deadline. Keep the existing candidate first so that step 1 is preserved.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-05 — Missing lifecycle guards corrupt plan lineage and erase event effects

**Severity:** High
**Status:** INCORRECT
**Area:** Replanning

### Requirement
Invalid lifecycle operations return `SIMULATION_STATE_ERROR`. MissionPlan versions form one parent-linked sequence. Event effects persist (redesign context §9, API lifecycle).

### Actual behavior
- `POST /windows/generate` after events regenerates windows from the provider. Cloud-block invalidations and emergency windows are discarded, while the emergency request stays in the pool.
- `POST /plan` after plans exist appends another plan with `version=1` and no parent.
- `compare_versions` then resolves version 1 to the first match, so `/plans/PLAN-001/compare/PLAN-003` compares PLAN-001 with itself.
- `POST /events` and `POST /replan` are accepted after `mission_complete`.
- The UI "Generate plan" button stays enabled after plans, events, and replans, so the first three problems are reachable from the browser.

### Evidence
**AMIS**
- `amis/session.py:91-118` (`generate_windows`, `plan`: no existing-plan guard)
- `amis/session.py:212-219` (`get_plan_by_version`: first match)
- `amis/session.py:251-257` and `:120-124` (no `mission_complete` check)
- `frontend/src/panels/MissionBar.tsx:206`

**Tests**
- Probe 2: after a cloud block, an emergency, and V2, regenerating gives every window `valid=True`, with `WIN-OBS-X-1` gone. `POST /plan` returns `SCN-002:PLAN-003 version 1 parent None`. `OBS-X` becomes `dropped`. The comparison returns `from_plan_id=to_plan_id=SCN-002:PLAN-001`.
- Probe 7: after `mission_complete`, the event returns 201 and the replan returns 201 with version 2.

### Why this is a real defect
One click in the UI silently rewrites mission history. Invalid windows become valid again, the event log no longer matches the window state (which breaks replay), and plan comparison returns wrong results.

### Smallest reasonable correction
Have `MissionSession` raise `SimulationStateError` when `plan()` or `generate_windows()` is called after a plan exists, and when `inject_event` or `replan` is called after `mission_complete`. Disable "Generate plan" once a plan exists. To restart, the user loads a new scenario, or a reset route is added.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** Yes
**Migration required:** No
**Test changes:** Yes

## GAP-06 — Session save is not atomic across tables

**Severity:** Medium
**Status:** INCORRECT
**Area:** Persistence

### Requirement
The persisted state is reconstructable and consistent. Replay equals the pristine scenario plus the ordered events (ADR-0002).

### Actual behavior
`MissionSessionStore.save` calls seven repository writes. Each SQL repository opens its own `engine.begin()` transaction. A failure partway through commits the earlier tables and not the later ones. Concurrent non-replan mutations (for example step and inject) also interleave, and the last writer wins per table.

### Evidence
**AMIS**
- `amis/repositories.py:272-296`
- `amis/db/repositories.py`: every method uses `with self._engine.begin()`

**Tests**
- Probe 5 follow-up: after the failed event on scenario B, `/windows` shows `WIN-OBS-B-1` with `valid=False`. `/impact` returns `SIMULATION_STATE_ERROR: no impact exists`. `active_event_ids` is `[]`.

### Why this is a real defect
The database holds an invalidated window with no event that explains it, a state the event log cannot reproduce.

### Smallest reasonable correction
Run the whole save in one connection and transaction. Pass the connection into the repositories, or add a unit-of-work wrapper. Keep the existing plan-row lock inside that transaction.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** Yes
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-07 — Malformed emergency payloads are accepted and permanently break the scenario

**Severity:** High
**Status:** INCORRECT
**Area:** Event

### Requirement
Invalid events are rejected with `INVALID_EVENT` and without partial changes.

### Actual behavior
The emergency payload accepts timezone-naive `deadline`, `start`, and `end`, and windows where `start > end`. The event is stored. After that, each `step` compares a naive deadline with an aware clock, and so does the planner during `replan`. Both return HTTP 500 on every later call. No reset route exists to recover.

### Evidence
**AMIS**
- `amis/api_schemas.py:35-44` (the request deadline timezone is checked only inside `ScenarioSchema.validate_scenario`)
- `amis/api_schemas.py:69-76` (`ObservationWindowSchema` has no validators)
- `amis/session.py:_validate_emergency_request` (no time checks)

**Tests**
- Probe 4: naive and inverted payload gives `inject 201`, then `step 500`, then `replan 500`. An aware but inverted window is also accepted with 201.

### Why this is a real defect
One bad API call makes a scenario unusable for good. The frontend form always sends UTC, so the browser is not exposed, but the public API contract is.

### Smallest reasonable correction
Require timezone-aware datetimes and `start < end` on `ObservationWindowSchema`, and a timezone-aware deadline on `ObservationRequestSchema`. Check again in `_validate_emergency_request` for direct session callers.

**Backend changes:** Yes
**API contract changes:** Yes (stricter validation, no shape change)
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-08 — Decision traces attribute every change to the latest event

**Severity:** Medium
**Status:** INCORRECT
**Area:** Replanning

### Requirement
A DecisionTrace links a plan change to the event that caused it (`CONTEXT.md`, "DecisionTrace"). Traces link to the correct changes (audit spec §7).

### Actual behavior
`replan` sets one `event_id` for all traces: the event of the latest impact recorded against the previous plan. When several events occur before one replan, a change caused by an earlier event is attributed to the later one.

### Evidence
**AMIS**
- `amis/session.py:156-163` (`event_id=self._triggering_event_id(previous_plan)`)
- `amis/session.py:586-600`
- `frontend/src/state/planComparison.ts` (`traceEventId`) shows and selects this event

**Tests**
- Probe 2: CLOUD_BLOCK (`EVT-001`) on OBS-B, then EMERGENCY (`EVT-002`), then replan. Traces: `('OBS-B', 'WINDOW_INVALIDATED', 'EVT-002')`.

### Why this is a real defect
The explanation names the wrong cause. Selecting the trace's event in the UI focuses the emergency, not the cloud block.

### Smallest reasonable correction
Resolve the event per changed request. For example, use the earliest event whose impact first marked that request's action invalid, or the cloud-block event naming its window. Use the triggering event only when no specific cause exists.

**Backend changes:** Yes
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-09 — `violation_count` counts unscheduled requests, not constraint violations

**Severity:** Medium
**Status:** INCORRECT
**Area:** Domain

### Requirement
"Constraint Violations: number of validation violations in the resulting plan" (SRD §17). The plan holds "a constraint violation count" (Build Spec, MissionPlan).

### Actual behavior
The planner sets `violation_count=len(unscheduled)`. The metrics pass it through, and the UI shows it as "Violations" with a warning color. A feasible plan with a dropped request shows 1 violation. The infeasible plan from GAP-03 shows 0.

### Evidence
**AMIS**
- `amis/planning/greedy.py:180`
- `amis/metrics.py:73`
- `frontend/src/state/metricsView.ts:165-171`

**Tests**
- Probe 6 (BATTERY) V2 reports `violation_count: 2` for a plan that passes `validate_plan`.
- Probe A reports 0 for a plan that fails it.
- `tests/test_domain_roundtrip.py:80-82` assumes the opposite convention.

### Why this is a real defect
The "Did it improve?" metric misreports plan correctness in both directions.

### Smallest reasonable correction
Compute `violation_count` from `validate_plan` on the resulting plan, and report unscheduled requests separately (they already appear in `unscheduled`). An alternative is to rename the field and label to describe what it counts.

**Backend changes:** Yes
**API contract changes:** Yes (field meaning, or field name)
**Persistence changes:** No
**Frontend changes:** Yes (label)
**Migration required:** No
**Test changes:** Yes

## GAP-10 — Emergency arrivals get a made-up reason, or no change at all, in the diff

**Severity:** Medium
**Status:** INCORRECT
**Area:** Replanning

### Requirement
Canonical reason codes remain authoritative. No invented causal reasoning is presented as backend truth. An emergency replan produces an "appropriate trace".

### Actual behavior
- An emergency request scheduled in Vn+1 is classified `INSERTED` with the fallback `ALTERNATIVE_WINDOW_AVAILABLE`. The trace says "was scheduled ... because an alternative window was available". That is not why it was scheduled.
- An emergency request that stays unscheduled is classified `UNCHANGED`/`REQUEST_UNCHANGED`, although it is new in the pool. The frontend adds `newlyArrivedUnscheduled` to work around this.

### Evidence
**AMIS**
- `amis/diff.py:111-114` (the `INSERTED` fallback)
- `amis/diff.py:120-124` (both-absent case gives `UNCHANGED`)
- `frontend/src/state/planComparison.ts:61-67, 101-103`

**Tests**
- Probe 6 (EMERGENCY): `('OBS-EMERGENCY-1', 'INSERTED', 'ALTERNATIVE_WINDOW_AVAILABLE')`. Trace: `...because an alternative window was available.`

### Why this is a real defect
The explanation layer asserts a false cause for the emergency workflow's central change. The frontend compensates for a backend classification gap.

### Smallest reasonable correction
When a request is absent from the parent plan's pool and present in the child's, classify it as `INSERTED` (scheduled) or `DROPPED` (unscheduled) with a cause tied to its arrival. Ideally that is a dedicated reason code for a newly introduced request, which the locked vocabulary does not yet have. Otherwise use the child plan's unscheduled reason. Then remove the frontend workaround.

**Backend changes:** Yes
**API contract changes:** Yes (if a reason code is added)
**Persistence changes:** No
**Frontend changes:** Yes
**Migration required:** No
**Test changes:** Yes

## GAP-11 — Integration tests bypass the production wiring and multi-scenario persistence

**Severity:** Medium
**Status:** MISSING
**Area:** Test

### Requirement
Tests show the real behavior of the API lifecycle and persistence (audit spec §13).

### Actual behavior
Every REST test injects `CanonicalWindowProvider`. No test uses `amis.main.build_app()`. SQL tests use one scenario each. No planner test covers placement against actions that start later in time, or a shared wide window. Together these gaps let GAP-01 through GAP-04 through with a fully passing suite.

### Evidence
**AMIS**
- `tests/test_rest_api.py:60, 370, 385, 456, 506, 566, 602, 619`
- `tests/test_sql_persistence.py`
- `tests/test_greedy_planner.py`

**Tests**
- 136 of 136 pass while probes 1, 3, and 5 fail.

### Why this is a real defect
A green suite gives false confidence about the shipped configuration.

### Smallest reasonable correction
Add a smoke test through `build_app()` that plans the demo scenario and expects OBS-B scheduled. Add a two-scenario SQL test that injects events in both. Add planner tests for the probe A and probe B cases.

**Backend changes:** No
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** Yes

## GAP-12 — The third-party notice misstates provenance

**Severity:** Low
**Status:** INCORRECT
**Area:** Licensing

### Requirement
Accurate provenance. Material adaptation must be recorded with the license and attribution. Conceptual inspiration must not be recorded as copied code (redesign context §13).

### Actual behavior
`.doc/reference/THIRD_PARTY_NOTICES.md` holds only a source-comment header: "Portions adapted from World Monitor ... Licensed under GNU AGPL v3. See LICENSE and THIRD_PARTY_NOTICES.md." No `LICENSE` file exists in the repository. No AMIS source carries the header. `frontend/src/index.css:4-8` states "conceptual reference, no source copied". The file lives under `.doc/reference/`, not at the repository root.

### Evidence
**AMIS**
- `.doc/reference/THIRD_PARTY_NOTICES.md`
- `frontend/src/index.css:4-8`
- `ls LICENSE*` returns nothing

**Reference evidence**
- `koala73/worldmonitor` `LICENSE` (AGPL-3.0) and `src/components/DeckGLMap.ts` at `b95863bddb4176585e717079cf2556230020af5d`: no matching source found in AMIS

### Why this is a real defect
The only provenance record claims an AGPL adaptation that did not happen and points to a license file that does not exist. That misleads anyone reviewing licensing obligations.

### Smallest reasonable correction
Replace the file with an accurate notice listing each reference and whether it was conceptual or structural, with no adapted source. Place it where the project's notices are expected to live. Add a project `LICENSE` if the AGPL-compatible direction is intended.

**Backend changes:** No
**API contract changes:** No
**Persistence changes:** No
**Frontend changes:** No
**Migration required:** No
**Test changes:** No

---

## Items examined and found correct, or not defects

- Replan without an event: new immutable version, identical placements, churn `0.0`, coverage `null` (probe 6).
- `PLAN_VERSION_CONFLICT`: checked in the session and again under a row lock in the SQL repository. The frontend shows a conflict banner and refreshes to the backend's current plan.
- The null denominators for churn and coverage, and the frontend rendering "N/A".
- Utility deduplicates request ids (set union of scheduled and completed).
- Expired requests stay in the pool and are excluded from replanning.
- No global `PLAN_INFEASIBLE`: an empty plan with per-request reasons is returned. SUPERSEDED — NOT A DEFECT relative to older documents.
- The Build Spec lists "Drawing observation windows on the timeline" as cut. The redesign context later asks for window bands, and they are implemented. SUPERSEDED — NOT A DEFECT.
- The SRD lists `GET /scenarios/{id}/metrics`. AMIS serves version-bound `GET /plans/{id}/metrics` instead, as Prompt 6 intended. SUPERSEDED — NOT A DEFECT.
- React-Leaflet (redesign context §8) was never in use. The previous map was SVG, replaced by MapLibre and deck.gl in commit `2b9be0d`. Not a migration away from Leaflet.
- TanStack Query and Recharts are absent. This deviates from the stated stack, but the required behavior (explicit invalidation, no polling) is met. Recorded, not a gap.
- The map's plan-derived satellite marker is a documented presentation choice, not fabricated telemetry. UNVERIFIABLE as a user-perception risk.
- PostgreSQL runtime, Compose startup, and live browser integration: UNVERIFIABLE in this audit (Docker engine not running). GAP-02 and GAP-06 were proven through the same SQLAlchemy repositories on SQLite. Primary-key uniqueness behaves the same way on PostgreSQL.
