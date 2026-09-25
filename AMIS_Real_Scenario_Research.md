# AMIS real scenario research

Research for the second project presentation: how AMIS moves from deterministic demo scenarios to a realistic Earth observation mission-planning simulator without rewriting the adaptive loop.

Prepared 2026-09-25 against commit `3fe5208` on `main`. This is research and planning only. No repository file other than this report was created or changed.

## How to read this report

Every important claim carries one of four tags.

| Tag | Meaning |
| --- | --- |
| `[Repo]` | A fact read from the AMIS code, tests, or migrations, with a file and line reference. |
| `[Spec]` | A decision recorded in `CONTEXT.md`, `.doc/specs/`, `.doc/adr/`, or the redesign context. These are treated as locked unless a section argues otherwise. |
| `[External]` | A claim taken from an outside source, cited as `[S#]` and listed in section 21. |
| `[Rec]` | An engineering recommendation or estimate made in this report. |

Evidence base:

- `[Repo]` Backend suite: `python -m pytest -p no:cacheprovider -q` with `PYTHONDONTWRITEBYTECODE=1` reports 152 passed in the project `.venv` (Python 3.14.3). The frontend suite was not re-run; `.doc/status/feature-implementation-status.md` records 139 passing.
- `[External]` The two reference repositories were cloned read-only into a temporary directory outside the repository: `Ceng-0324/SkyOps` at `aa895e7` and `patrickkuei/Satellite-Mission-Control-Dashboard` at `89825ff`. Every file the brief named exists at those commits.
- Arithmetic in section 7 (off-nadir angles, window lengths, access frequency) was computed for this report from standard spherical-Earth geometry. It is tagged `[Rec]` because it is an estimate, not a measurement from AMIS.

---

## 1. Executive summary

AMIS can reach a realistic Earth observation scenario by adding one new window provider, one new domain value object, and a scenario builder. The planner, replanner, constraints, impact analysis, plan diff, decision traces, and metrics do not need to change beyond one new reason code.

Findings:

1. `[Repo]` The provider boundary already exists and is sufficient. `WindowProvider.generate(scenario, requests)` is defined in `amis/windows/protocol.py:15-18`. `MissionSession` takes a provider in its constructor (`amis/session.py:60-77`), `MissionSessionStore` passes it through (`amis/repositories.py:254-263`, `348-353`), and `build_app` wires one in (`amis/main.py:21-29`). The planner only sees `ObservationWindow` values (`amis/planning/greedy.py:63-201`) and never learns where they came from.
2. `[Repo]` The production provider chooses windows by request id, not by scenario. `ProductionWindowProvider` (`amis/demo.py:166-203`) gives any request named `OBS-A` to `OBS-E` the canonical demo windows, and gives every other request one window spanning the whole mission (`amis/windows/synthetic.py:14-29`). A user-built scenario that reuses those ids would silently get demo timing. Provider selection has to move to the scenario before custom missions mean anything.
3. `[Repo]` The domain holds no orbital data. `Satellite` has only resources and an availability flag (`amis/domain/scenario.py:16-22`). `ObservationWindow` has no geometry (`amis/domain/window.py:11-18`). The map draws the satellite over whichever target the current action observes, because "the domain holds no satellite position" (`frontend/src/map/missionMapModel.ts:88-117`).
4. `[Repo]` Scenario creation already exists at the API layer (`POST /scenarios`, `amis/api.py:147-156`) with validation (`amis/api_schemas.py:18-78`) and persistence. What is missing is a way to list and reopen scenarios, a per-scenario plan list, and any frontend path other than "Load demo scenario" (`frontend/src/state/useMissionSession.ts:153-161`).
5. `[External]`/`[Rec]` An Earth observation window is not a horizon pass. A ground observer sees a 705 km satellite from roughly 2,800 km away, which is about 64 degrees off nadir from the satellite. An imager limited to 30 degrees off nadir needs the satellite at about 56 degrees elevation or higher as seen from the target, and such windows last about two minutes at most. The current demo observation durations of 300 to 600 seconds would never fit a real window, so the scenario builder needs new defaults.
6. `[Rec]` Recommended orbital stack: Skyfield 1.55 (MIT, pure Python over NumPy, built on the `sgp4` 2.27 package) [S1][S6][S7]. Windows come from `EarthSatellite.find_events` evaluated at the target with `altitude_degrees` derived from the maximum off-nadir angle [S2]. Element sets are stored offline as CelesTrak OMM records, with TLE accepted on input [S9]. Sun elevation for optical imaging uses a small excerpt of the JPL `de421` ephemeris committed with a checksum [S4][S8]. Nothing in the core loop touches the network.
7. `[Rec]` Presentation 2 scope: custom mission creation with a real element set and real target coordinates, orbit-derived windows, the unchanged adaptive loop on top of them, an explicit Examples mode for the three existing demos, Load Mission, a backend-computed ground track on the map, and an honest reason code when a target has no window. CP-SAT, ground-station downlink, weather ingestion, and multiple satellites wait.
8. `[Rec]` Top risks: element-set age against mission dates, realistic windows leaving many requests unschedulable in a one-day horizon, determinism drift across Skyfield releases, an Alembic history that was edited in place (`3fe5208` changed `0001` instead of adding `0002`), and the gap between the local Python 3.14 environment and the `python:3.11-slim` Docker image.

---

## 2. Current AMIS architecture relevant to Phase 2

### 2.1 The loop as it runs today

`[Repo]` The adaptive loop is driven through `MissionSession` (ADR-0001). The API rebuilds a session from repositories on every request (`amis/repositories.py:272-284`), acts, and saves (`amis/repositories.py:304-346`).

```text
POST /scenarios                    MissionSessionStore.create -> MissionSession.load_scenario
POST /scenarios/{id}/windows/generate   MissionSession.generate_windows -> WindowProvider.generate
POST /scenarios/{id}/plan          MissionSession.plan -> Planner.plan (GreedyPlanner)
POST /scenarios/{id}/simulation/step   MissionSession.step
POST /scenarios/{id}/events        MissionSession.inject_event -> analyze_impact
POST /scenarios/{id}/replan        MissionSession.replan -> Planner.plan(previous_plan) -> compare_plans -> build_traces
GET  /plans/{old}/compare/{new}    MissionSession.compare_versions -> compute_metrics
```

### 2.2 Where each concept lives

| Concept | Implementation | What it does today |
| --- | --- | --- |
| Scenario | `amis/domain/scenario.py:86-116` | Frozen dataclass: id, name, start and end time, one `Satellite`, a tuple of requests. JSON round trip through `to_dict`/`from_dict`. |
| Satellite | `amis/domain/scenario.py:15-43` | Id, battery capacity and charge, storage capacity and usage, `available`. No orbit. |
| ObservationRequest | `amis/domain/scenario.py:46-83` | Id, `target_lat`, `target_lon`, priority, `duration_s`, deadline, energy and storage cost, status. No target name. |
| ObservationWindow | `amis/domain/window.py:10-41` | Id, request id, satellite id, start, end, `valid`, `invalid_reason`. No geometry or provenance. |
| MissionState | `amis/domain/state.py:12-60` | Clock, battery, storage, availability, active event ids, completed request ids, `mission_complete`. |
| ScheduledAction | `amis/domain/plan.py:12-49` | Request placed in a window at a start time, with its costs and status. Always tied to a request and a window. |
| MissionPlan | `amis/domain/plan.py:68-110` | Immutable version with parent id, actions, unscheduled entries with reason codes, utility, violation count, planning time. |
| MissionEvent | `amis/domain/event.py:14-106` | `CLOUD_BLOCK`, `BATTERY_DROP`, `EMERGENCY_TASK` payloads. Emergency payload carries explicit windows (`event.py:46-66`). |
| Constraints | `amis/constraints/` | Containment (`containment.py:17`), deadline (`deadline.py:14`), overlap (`overlap.py:15`), availability (`availability.py:14`), projected battery and storage with `ResourceProjection` (`resources.py:21-120`), and `validate_plan` over unfrozen actions (`plan_validation.py:35-74`). |
| Simulation | `amis/session.py:464-522` | `step` advances the clock, starts and completes actions, charges costs on start, expires requests, clamps at the end. |
| Greedy planner | `amis/planning/greedy.py:62-274` | Orders requests by priority, deadline, duration, id; tries several start instants per window (`231-257`); stability rule (`216-228`); reason codes for unscheduled requests (`260-274`). |
| Adaptive replanner | `amis/session.py:137-192` | Same `Planner.plan` call with `previous_plan` (ADR-0004). Frozen actions carried forward (`greedy.py:204-213`). |
| Impact analysis | `amis/impact.py:20-63` | Runs `validate_plan` and splits unfrozen actions into valid and invalid with reason codes. |
| DecisionTrace | `amis/trace.py:61-106`, `amis/domain/trace.py:12-58` | One trace per moved, inserted, or dropped request, rendered from reason-code templates (`trace.py:29-58`). |
| Plan diff | `amis/diff.py:58-165` | Classifies each request as unchanged, moved, inserted, dropped, or completed. |
| Metrics | `amis/metrics.py:30-123` | Utility, completion rate, violation count, planning time, battery and storage use, churn, explanation coverage. |
| Persistence | `amis/repositories.py`, `amis/db/schema.py`, `amis/db/repositories.py`, `migrations/versions/0001_initial_schema.py` | Protocol per aggregate, in-memory and SQLAlchemy implementations, one transaction per save when an engine exists (`repositories.py:304-318`). `experiment_results` table exists but nothing writes it (`db/schema.py:246-269`). |
| FastAPI | `amis/api.py:71-317` | Thin routes over the store. Error envelope and status mapping (`97-138`). |
| API DTOs | `amis/api_schemas.py` | `ScenarioSchema` (`59-78`), `SatelliteSchema` (`18-32`), `ObservationRequestSchema` (`35-56`), `ObservationWindowSchema` (`81-100`), discriminated event unions (`177-225`). All models use `extra="forbid"` (`14-15`). |
| MissionSession | `amis/session.py:59-836` | The facade and test seam. Holds scenario, windows, plans, state, request pool, events, impacts, traces. `restore` rebuilds from repository records (`404-462`). |
| Scenario loading | `amis/session.py:79-89`, `amis/api.py:140-156` | Loads a `Scenario`, dict, or JSON path. `GET /demo/scenario` returns the canonical scenario. |
| Synthetic window generation | `amis/windows/synthetic.py:14-29`, `amis/demo.py:29-203` | One whole-horizon window per request, plus fixed-offset demo providers. |
| Frontend | `frontend/src/` | React 19, MapLibre plus deck.gl map, vis-timeline, generated OpenAPI types (`package.json`). One hook owns server state (`state/useMissionSession.ts`). |

### 2.3 Specification decisions that constrain Phase 2

- `[Spec]` The planner must not depend on FastAPI, React, or PostgreSQL (SRD section 2, principle 2; ADR-0001).
- `[Spec]` Scenario is immutable, and replay is the pristine scenario plus the event log in order (ADR-0002).
- `[Spec]` An orbital provider was always intended: "An `OrbitalWindowProvider` built on Skyfield or SGP4, reading static TLE files held in the repository, replaces it later. The core loop never calls a live TLE service." (`AMIS_Build_Spec.md`, WindowProvider protocol section.) The SRD says the same in section 10.
- `[Spec]` ADR-0002 anticipates orbital emergency windows: "Generating windows at injection is the right extension once an orbital provider exists, and it fills the same field."
- `[Spec]` A CP-SAT planner must satisfy the same `Planner` protocol with no changes to simulation, replanning, or UI (Build Spec; ADR-0004).
- `[Spec]` Resources move one way in the MVP: no recharge, no downlink (Build Spec resource model; redesign context section 9).
- `[Spec]` The complete core workflow shall operate without internet access (SRD section 22).

---

## 3. What is currently demo or synthetic

`[Repo]` These parts are placeholders for real data:

| Item | Location | Why it is synthetic |
| --- | --- | --- |
| Whole-horizon windows | `amis/windows/synthetic.py:14-29` | Every request gets one window from scenario start to end, whatever its coordinates. |
| Canonical demo windows | `amis/demo.py:130-163` | Fixed minute offsets keyed by request id (`OBS-B` has two windows at +20 and +75 minutes). |
| Impact demo windows | `amis/demo.py:29-46` | Windows start 10 minutes apart by list index. |
| Production dispatch | `amis/demo.py:166-203`, wired in `amis/main.py:24,29` | Chooses canonical or synthetic windows per request id. |
| Demo scenarios | `amis/demo.py:49-127`, `206-248`, `251-281` | Hand-set battery, storage, costs, deadlines, and dates (`2026-01-01`, `2026-09-21`). |
| Emergency windows | `amis/demo.py:274-280` | The emergency request's window is typed in by hand. |
| Satellite identity | `SAT-001` in every scenario | Not tied to any real spacecraft. |
| Satellite map position | `frontend/src/map/missionMapModel.ts:88-117` | Drawn over the target being observed, derived from the plan. |
| Scenario entry point | `amis/api.py:140-145`, `frontend/src/panels/MissionBar.tsx:189-199` | The only frontend route into a mission is "Load demo scenario". |

`[Repo]` The target coordinates are real places (Bengaluru 12.97, 77.59; Delhi 28.61, 77.21; Mumbai 19.08, 72.88; Chennai 13.08, 80.27; Kolkata 22.57, 88.36; Hyderabad 17.38, 78.49; the emergency target is Los Angeles 34.05, -118.24), but no code uses them to compute timing. They only reach the map.

`[Repo]` Not synthetic: the constraint engine, the greedy planner, simulation, events, impact analysis, replanning, plan diff, decision traces, metrics, and persistence all operate on whatever windows and requests they are given. They are the part that stays.

---

## 4. What can already be reused

| Component | Reuse | Note |
| --- | --- | --- |
| `WindowProvider` protocol | As is | `[Repo]` Signature `generate(scenario, requests)` already receives the scenario, so a provider can read orbit data and policy from it. |
| `SyntheticWindowProvider`, `CanonicalWindowProvider`, `DemoImpactWindowProvider` | As is | Kept for examples and tests. At least eight test files inject providers directly (`tests/test_replan.py`, `test_rest_api.py`, `test_emergency_request_event.py`, and others). |
| `GreedyPlanner` | As is, one small change | `[Repo]` It already tries several start instants inside a window (`greedy.py:231-257`), which is how an agile satellite uses a visible window. Only the reason for a request with zero windows needs a new code (section 9.4). |
| Constraints, `validate_plan` | As is | Window containment works for any window source. |
| Simulation `step` | As is | Time handling is timezone-aware and horizon-agnostic. |
| Events, impact, replan, diff, traces, metrics | As is | They read window ids and times only. |
| `MissionSession` | Extend | Add one helper for generating windows for a single emergency request. |
| Repositories and SQL schema | Extend | Windows are already persisted per scenario (`db/schema.py:92-109`), so orbit-derived windows survive restarts without recomputation. |
| `POST /scenarios` and `ScenarioSchema` | Extend | Add optional orbit and window-policy fields. |
| Frontend map, timeline, event controls | Extend | The timeline already draws windows as bands (`frontend/src/timeline/missionTimelineModel.ts:187-223`); CLOUD_BLOCK already picks a request and then one of its windows. |
| `experiment_results` table | Reuse later | Ready for the evaluation suite and planner comparison. |

---

## 5. Realistic scenario architecture

`[Rec]` The recommended flow keeps every external input outside the planning core and turns it into domain values before the loop starts.

```text
Offline element snapshots (OMM JSON, TLE accepted)      User input (Scenario Builder or JSON file)
   amis/data/elements/*.json + manifest.json               mission, satellite choice, targets
                 \                                          /
                  \                                        /
                   Scenario (immutable)
                     satellite.orbit : OrbitalElements | None
                     window_policy   : WindowPolicy | None
                     requests        : ObservationRequest[] with real lat/lon
                                   |
                   ScenarioWindowProvider (chooses by window_policy.provider)
                     |-- "synthetic"       -> SyntheticWindowProvider
                     |-- "canonical_demo"  -> CanonicalWindowProvider
                     |-- "orbital"         -> OrbitalWindowProvider (Skyfield / SGP4)
                     |-- None (legacy)     -> ProductionWindowProvider (current behaviour)
                                   |
                   ObservationWindow[] (persisted, with geometry and source)
                                   |
   MissionSession: plan -> step -> event -> impact -> replan -> compare -> traces -> metrics
                                   |
   Read-only views: ground track, satellite position (computed from the same orbit, never fed back into planning)
```

Boundaries:

- `[Rec]` Only `amis/windows/orbital.py` and a small `amis/orbital/` package import Skyfield. The planner, constraints, and session stay free of orbital libraries, which keeps the SRD modularity rule enforceable.
- `[Rec]` The scenario carries the element set itself, not a reference to a live source. Replay therefore needs nothing outside the scenario, the event log, and pinned library versions (section 14).
- `[Rec]` The ground track is a presentation read model, like `MapTarget` in the redesign context section 10. It is computed by the backend from the same element set so the map and the windows can never disagree.

Mapping the reference dashboard's chain onto AMIS:

| Reference concept [S30] | AMIS equivalent |
| --- | --- |
| CelesTrak fetch (`scripts/fetch-tle-snapshot.mjs`) | A manual `scripts/fetch_orbital_elements.py` that writes a dated snapshot and manifest, run by a developer, never by the server |
| Cached static snapshot (`satellites-snapshot.json` with `fetchedAt`) | `amis/data/elements/<date>.json` with retrieval time, source URL, and SHA-256 per record |
| SGP4 propagation (`satellite.js`) | Skyfield `EarthSatellite` inside `amis/orbital/` |
| Satellite position | Read-only backend endpoint for the map |
| Ground track (`GroundTrackSchema`, 30 s steps) | `GET /scenarios/{id}/ground-track` |
| Pass prediction (`predictPasses`, elevation above 0 degrees, 60 s steps) | `OrbitalWindowProvider` producing EO target windows, not horizon passes (section 7.3) |
| Frontend visualisation | New map layer over the existing MapLibre plus deck.gl engine |

---

## 6. Orbital data and propagation research

### 6.1 TLE

- `[External]` A TLE is two 69-character lines. The reference dashboard validates exactly that length and parses the epoch from line 1 columns 19 to 32 (`packages/types/src/satellite.ts:18-27`, `scripts/fetch-tle-snapshot.mjs:46-65`) [S30].
- `[External]` Skyfield: "TLE data is accurate to about a kilometer or so at epoch and it quickly degrades", and elements stay useful "for a couple of weeks to either side of its epoch". The epoch is available as `satellite.epoch`, and failed propagation returns NaN positions with a `message` [S1].
- `[External]` CelesTrak explains that TLEs keep a two-digit year and a five-digit catalog number, and that TLE creation stops working around catalog number 69999, not 99999 [S9].

### 6.2 OMM

- `[External]` OMM is the CCSDS Orbit Mean-Elements Message. CelesTrak serves it as XML, KVN, JSON, and CSV, and recommends CSV for size [S9].
- `[External]` Skyfield builds a satellite from OMM fields with `EarthSatellite.from_omm(ts, element_dict)` [S1][S2]. The `sgp4` package reads and writes OMM in CSV, JSON, and XML through its `omm` and `exporter` modules [S7].
- `[Rec]` Store OMM JSON as the canonical form in AMIS. Accept a TLE pair on input and keep the original lines verbatim so a user can compare them with other tools. OMM avoids the catalog-number ceiling and the two-digit year.

### 6.3 Identifiers

- `[External]` The NORAD catalog number (`CATNR`) is the stable key; CelesTrak also queries by international designator (`INTDES`), `GROUP`, and `NAME` [S9]. Names are not unique.
- `[External]` Candidate Earth observation satellites for the presentation: Sentinel-2A 40697 (2015-028A), Sentinel-2B 42063 (2017-013A), Landsat 8 39084, Landsat 9 49260 [S18]. These ids came from a secondary catalogue site and should be confirmed against CelesTrak when the snapshot is fetched.
- `[Rec]` The AMIS `Satellite.id` stays the scenario-local id (`SAT-001` style). The NORAD number, name, and international designator live inside the orbit value object. That keeps every existing id, plan id, and event payload unchanged.

### 6.4 Epochs and element age

- `[Rec]` A scenario with orbital windows is a replay of a specific period, not "now". The scenario start should sit close to the element epoch. Validation rule: warn when any part of the mission is more than 7 days from the epoch, reject beyond 14 days, following Skyfield's "couple of weeks" guidance [S1]. Store the epoch in the scenario so the check can be repeated at replay.
- `[Rec]` Simulated time in AMIS is already decoupled from wall-clock time (`MissionState.simulated_time`), so a mission dated to the snapshot week works with no clock changes.

### 6.5 Offline snapshots versus live sources

- `[External]` CelesTrak GP data updates once every 2 hours. The usage policy says to "only download data once per update", tells machine clients to stop on any non-200 response, and warns that ignoring this sends the client IP to the firewall [S11]. Search results describe a March 2026 change that returns HTTP 403 for a repeat download of unchanged data and an error budget of 50 errors per 2 hours [S11]; the policy page itself confirms the frequency and firewall rules.
- `[External]` Space-Track requires an account, limits API use to under 30 requests per minute and 300 per hour, and restricts redistribution beyond basic data with citation [S12]. This came from search summaries of its documentation, not a direct read.
- `[Spec]` The MVP excludes live TLE feeds (Build Spec out-of-scope list; SRD section 10).
- `[Rec]` Presentation 2 uses committed snapshot files only. A developer script fetches one group or a few catalog numbers from CelesTrak in OMM JSON, writes a dated file plus manifest (source URL, retrieval time, SHA-256), and is never called by the API. Space-Track is not needed.

### 6.6 Propagation: SGP4, `sgp4`, and Skyfield

| Option | What it gives | What AMIS would have to write | Verdict |
| --- | --- | --- | --- |
| `sgp4` package directly [S7] | Official Vallado SGP4/SDP4 code, `Satrec.twoline2rv`, OMM support, vectorised `SatrecArray`, MIT licence. Output is TEME position in km and velocity in km/s. | "The SGP4 propagator itself does not implement the math to convert these positions" into ICRS or Earth-fixed frames [S7]. AMIS would need TEME to ITRS conversion, sidereal time, polar motion choice, topocentric look angles, and event search. | Use only as a cross-check in tests. |
| Skyfield [S1][S2] | Uses the `sgp4` package internally (`satellite.model` is the `Satrec`), converts frames, gives `wgs84.latlon`, topocentric `altaz()`, `find_events`, `is_sunlit`, and Sun positions through ephemerides. | Only the EO-specific rules: threshold choice, sun filter, clipping, rounding. | Recommended for the provider. |
| A custom propagator | Nothing that the two above lack | Everything | Rejected, and the PRD rules out a custom orbital engine. |

`[External]` Versions: Skyfield 1.55 was released 2026-08-07 under MIT; its only binary dependency is NumPy [S6]. `sgp4` 2.27 was released 2026-07-03, supports Python 3.10 to 3.14, and falls back to pure Python agreeing "to within 0.1 mm" [S7]. Skyfield's PyPI classifiers list Python up to 3.13 [S6].

### 6.7 Determinism and offline behaviour of the stack

- `[External]` `load.timescale()` uses built-in leap-second and Delta T tables by default and downloads nothing; "This data will gradually fall out of date after each Skyfield release" [S3]. The consequence for AMIS is that the same element set can give slightly different window edges under two Skyfield versions.
- `[External]` Sun positions need a JPL ephemeris. `de421.bsp` covers 1900 to 2050 and is 17 MB [S4]. The `jplephem` tool can cut an excerpt by date range and target list (`python -m jplephem excerpt 2018/1/1 2018/4/1 de421.bsp excerpt421.bsp`) [S8].
- `[Rec]` Pin `skyfield` and `sgp4` to exact versions in `pyproject.toml`, record both versions in the window provenance, commit a small `de421` excerpt covering the snapshot period with its SHA-256, and round window edges inward to whole seconds (section 7.5) so small numeric drift does not change stored windows.
- `[Rec]` Confirm Skyfield installs and passes the new tests on both Python 3.14 (local `.venv`) and Python 3.11 (`Dockerfile`, `FROM python:3.11-slim`) before Stage 3 is accepted.

### 6.8 What the reference dashboard does with orbital data

`[External]` From `patrickkuei/Satellite-Mission-Control-Dashboard` [S30]:

- `scripts/fetch-tle-snapshot.mjs` fetches `GROUP=stations,starlink,science` in TLE format, keeps up to 50 satellites with a featured list first, and writes `{ fetchedAt, satellites }` to a static JSON file. A GitHub Action runs it every two days. Its comment claims GitHub runner IPs "are not rate-limited by Celestrak"; nothing in the CelesTrak policy supports that [S11].
- `apps/web/src/utils/sgp4.ts` repeats the server's propagation in the browser with `satellite.js` as a fallback when the API sleeps. That gives two propagators that can disagree.
- `apps/web/src/hooks/useSatellitePositions.ts` polls positions every second; `useGroundTrack.ts` and `usePasses.ts` refetch every 5 minutes. AMIS's frontend does not poll (Build Spec frontend section), and that should stay.
- `packages/types/src/*.ts` are Zod wire schemas shared by server and client. AMIS gets the same guarantee from FastAPI's OpenAPI schema and generated TypeScript types (`frontend/scripts/generate-api.mjs`).
- `apps/api/src/services/satellite.service.ts` layers a 24-hour disk cache, a live fetch, a remote snapshot, and a stale cache fallback.
- The repository has no `LICENSE` file at the cloned commit, so AMIS should keep treating it as a concept reference only, as `.doc/reference/THIRD_PARTY_NOTICES.md` already records.

`[Rec]` Worth copying as ideas: a dated snapshot with a retrieval timestamp, strict element validation, a curated featured list, and a selected-satellite detail panel that shows epoch and next window. Not worth copying: runtime fetching, browser-side propagation, TLE-only storage, polling, and the telemetry simulator.

---

## 7. Observation window generation

### 7.1 What an AMIS window should mean

`[External]` Wang et al.'s survey of agile EO scheduling separates two intervals. A conventional satellite that can only roll "can only observe the target during a fixed visible time window (VTW)". For an agile satellite "the VTW for an AEOS is typically longer than the corresponding OTW [observation time window] due to the satellite's ability to look ahead and look back along the pitch axis", so "each VTW contains multiple potential OTWs" [S19].

`[Repo]` AMIS already follows the agile reading. `CONTEXT.md` defines an `ObservationWindow` as "a span of time during which the satellite could observe one request's target", and a `ScheduledAction` as the request placed at a concrete start inside it. The greedy planner tries the window start and every instant right after an already-placed action (`amis/planning/greedy.py:231-257`).

`[Rec]` Define the orbital `ObservationWindow` as the VTW for one request: the interval in which the target lies inside the satellite's field of regard, in daylight when the request is optical, and long enough to hold the request's duration. Record this as an ADR so the meaning stays fixed.

### 7.2 Geometry

`[Rec]` For a spherical Earth of radius `R` and satellite altitude `h`, the off-nadir angle `eta` at the satellite and the elevation `eps` of the satellite seen from the target satisfy:

```text
sin(eta) = R / (R + h) * cos(eps)
earth central angle lambda = 90 deg - eta - eps
ground distance from sub-satellite point to target = R * lambda (radians)
```

This is the classical spherical relation; Nugnes, Colombo, and Tipaldi compare it with an oblate-Earth method and quantify the difference [S22]. Values for `h = 705 km` (Landsat 8 and 9 altitude [S15]), `R = 6378 km`:

| Max off-nadir | Required target elevation | Ground offset from track | Example system |
| --- | --- | --- | --- |
| 7.5 deg | 81.7 deg | 93 km | Landsat 185 km swath half-width [S15] |
| 10.4 deg (at 786 km) | 78.4 deg | 145 km | Sentinel-2 290 km swath half-width [S13][S14] |
| 30 deg | 56.3 deg | 415 km | Pleiades nominal viewing limit [S17] |
| 45 deg | 38.3 deg | 751 km | Near Pleiades maximum of 47 deg [S16][S17] |
| 64.3 deg | 0 deg (horizon) | about 2,860 km | What a horizon pass implies |

`[External]` Pleiades flies at 694 km with a 20 km nadir swath and can roll and pitch up to 60 degrees within 25 seconds [S16]; its user guide gives a standard viewing angle of plus or minus 30 degrees and a maximum of plus or minus 47 degrees [S17]. Sentinel-2 and Landsat do not point: they image a fixed swath under the track and are not tasked by users. Sentinel-2 follows a predefined observation plan [S14].

`[Rec]` AMIS should describe its Presentation 2 satellite honestly as "a hypothetical agile imager with a plus or minus 30 degree field of regard flying on the published orbit of satellite X". The orbit is real; the pointing and resource model are configured assumptions.

### 7.3 Observer pass versus EO target window

| Aspect | Observer pass (reference `usePasses`, `PassSchema`) | AMIS EO target window | Same? |
| --- | --- | --- | --- |
| Question answered | When can a person or antenna at a point see the satellite? | When can the satellite image a point? | No |
| Propagation | SGP4 from published elements | SGP4 from published elements | Yes |
| Geometry evaluated at | Observer location | Target location (same maths) | Yes |
| Threshold | Elevation above 0 degrees (`pass.ts` docstring) | Elevation implied by max off-nadir, about 56 degrees for 30 degrees at 705 km | No |
| Typical length (LEO) | Several minutes | About 2 minutes at most for 30 degrees, about 3.7 minutes for 45 degrees (section 7.6) | No |
| Illumination | Not considered | Sun elevation at the target for optical sensors | No |
| Sensor pointing | Not relevant | Field-of-regard cone, roll and pitch limits, agile or roll-only | No |
| Time resolution | 60 s stepping, "under-resolves brief LEO passes by up to a minute on each edge" (`orbit.service.ts:49-52`) | Root finding to sub-second precision, rounded inward to 1 s | No |
| Request-specific filtering | None | Window must fit `duration_s` and fall inside the mission horizon | No |
| Ground-station contact | Equivalent, with a 5 to 10 degree mask | Not applicable | Yes, this is the downlink case (section 11) |

`[Rec]` The pass algorithm is reusable for EO windows once the threshold is raised and the sun and duration filters are added. Using a 0 degree horizon for imaging would produce windows about 25 times too wide in ground distance and would let the planner schedule observations the sensor could never make.

### 7.4 Recommended algorithm

`[Rec]` For each request, inside `OrbitalWindowProvider.generate(scenario, requests)`:

1. Build one `EarthSatellite` from `scenario.satellite.orbit` with `load.timescale()` (built-in tables) [S1][S3].
2. Compute the elevation threshold `eps_min` from `window_policy.max_off_nadir_deg` and the satellite's mean altitude (from the mean motion), using the relation in 7.2. Store `eps_min` in the provenance.
3. Place the target with `wgs84.latlon(target_lat, target_lon)` and call `satellite.find_events(target, t0, t1, altitude_degrees=eps_min)` with `t0` and `t1` equal to the scenario start and end [S2].
4. Pair rise and set events into intervals. Handle a window already open at `t0` (first event is culmination or set) by starting at `t0`, one still open at `t1` by ending at `t1`, and repeated culminations inside one pass, which Skyfield warns can happen [S1].
5. For optical requests, compute the Sun's altitude at the target at the culmination time with `(earth + target).at(t).observe(sun).apparent().altaz()` [S5] and drop windows below `window_policy.min_sun_elevation_deg`.
6. Round the start up and the end down to whole seconds, so a stored window never extends past the geometric one.
7. Drop windows shorter than the request's `duration_s`. If a request has no windows left, return none for it; the planner reports `NO_OBSERVATION_WINDOW` (section 9.4).
8. Number windows `WIN-{request_id}-{n}` in start order, the existing convention. Fill the new optional fields: peak elevation, minimum off-nadir at culmination, sun elevation, and `source = "orbital:skyfield-1.55"`.

`[Rec]` A second, independent sampler (1 s steps, off-nadir computed directly from satellite and target positions) runs only in tests and must agree with the provider's edges within 2 seconds.

### 7.5 Time resolution

- `[External]` Skyfield's `find_events` returns event times from a search rather than a fixed step grid; its documentation does not state the internal tolerance [S2]. The reference repository's 60 s grid can be off by up to a minute at each edge (`orbit.service.ts:49-52`) [S30].
- `[Rec]` A 60 s grid is not usable for windows of about 120 s. Use `find_events` for the edges, store whole seconds, and let the verification sampler bound the error.

### 7.6 Window length and access frequency

`[Rec]` Estimates for a 705 km orbit (ground speed about 6.8 km/s, period about 98.8 minutes, about 14.6 orbits per day):

- An overhead pass keeps a target inside a 30 degree cone for about 2 x 415 km / 6.8 km/s, roughly 120 seconds. At 45 degrees it is roughly 220 seconds. Passes that do not go overhead are shorter.
- Adjacent daytime ground tracks of a sun-synchronous orbit are about 2,750 km apart at the equator and about 2,600 km at 20 degrees latitude. A 30 degree field of regard covers about 830 km across track, so a given target gets a daytime window roughly one day in three. At 45 degrees (about 1,500 km across track) it is roughly three days in five.

Consequences:

- The current demo durations of 300 s (`amis/demo.py:64`) and 600 s (`amis/demo.py:234`) cannot fit a real window. Builder defaults should be 20 to 60 seconds, with a warning above 120 seconds.
- A one-day mission over five Indian cities will leave several requests with no window. For the presentation, use a 3 to 5 day horizon, a 45 degree field of regard, or more targets, and show the `NO_OBSERVATION_WINDOW` entries as honest results.
- These figures come from the spherical model and must be checked against provider output in Stage 4.

### 7.7 What is physically realistic and what stays simplified

| Realistic in Presentation 2 | Still simplified |
| --- | --- |
| Orbit from a published element set propagated with SGP4 [S1][S7] | TLE and OMM accuracy of about 1 km at epoch, degrading with age [S1] |
| Target on the WGS84 ellipsoid | Elevation threshold derived with a spherical-Earth formula |
| Visibility from target elevation equivalent to an off-nadir limit | Pointing is a cone; no separate roll and pitch limits, no yaw |
| Sun elevation at the target for optical requests | No atmospheric refraction, terrain, or cloud (cloud stays an event) |
| Window edges to the second | No slew or settling time between observations |
| Mission dated to the element epoch | Energy and storage cost per request are user inputs, not derived from power or data rate |
| Real geographic targets | Image quality does not depend on off-nadir angle; the planner places actions at the window start, which is the most oblique point |
| | Battery never recharges and storage never frees (locked MVP resource model) |

---

## 8. Scenario builder requirements

### 8.1 Fields

| Group | Field | Required | Type and unit | Exists today |
| --- | --- | --- | --- | --- |
| Mission | `id` | Yes (client or server generated) | string | Yes |
| Mission | `name` | Yes | string | Yes |
| Mission | `start_time`, `end_time` | Yes | ISO 8601 with timezone | Yes |
| Mission | `window_policy.provider` | Yes for new scenarios | `synthetic`, `canonical_demo`, `orbital` | No |
| Mission | `window_policy.max_off_nadir_deg` | Orbital only, default 30 | degrees, 0 to 60 | No |
| Mission | `window_policy.min_sun_elevation_deg` | Optional, default 10 for optical, null to disable | degrees, -10 to 60 | No |
| Satellite | `id` | Yes | string | Yes |
| Satellite | `orbit` | Required when provider is `orbital` | `OrbitalElements` (section 9.3) | No |
| Satellite | `battery_capacity_wh`, `battery_charge_wh` | Yes | Wh | Yes |
| Satellite | `storage_capacity_mb`, `storage_usage_mb` | Yes | MB | Yes |
| Satellite | `available` | Yes, default true | bool | Yes |
| Request | `id` | Yes, unique | string | Yes |
| Request | `target_name` | Optional | string | No |
| Request | `target_lat`, `target_lon` | Yes | degrees | Yes |
| Request | `priority` | Yes | integer 1 to 5 | Yes |
| Request | `duration_s` | Yes | seconds | Yes |
| Request | `deadline` | Yes | ISO 8601 with timezone | Yes |
| Request | `energy_cost_wh`, `storage_cost_mb` | Yes | Wh, MB | Yes |

`[Rec]` "Current battery" and "current storage" already map to `battery_charge_wh` and `storage_usage_mb`. Payload type (optical or radar) can wait; `min_sun_elevation_deg = null` models a sensor that does not need daylight.

### 8.2 Validation rules

`[Repo]` Existing hard rules: timezone on scenario times and deadlines, end after start, unique request ids, latitude and longitude ranges, priority 1 to 5, positive duration, non-negative costs, charge not above capacity, usage not above capacity (`amis/api_schemas.py:18-78`).

`[Rec]` New hard errors:

- Orbital provider without `satellite.orbit`.
- Orbit that fails to parse, fails checksum, or propagates to NaN at any point in the horizon [S1].
- Mission more than 14 days from the element epoch.
- `max_off_nadir_deg` outside 0 to 60.
- Horizon longer than a configured limit (7 days suggested) to keep window generation interactive.

`[Rec]` New warnings, returned by a validation endpoint and shown in the builder, never blocking creation:

- Mission more than 7 days from the epoch.
- `duration_s` longer than the longest window the geometry allows (about 120 s at 30 degrees).
- A request with zero windows in the preview.
- Deadline before mission start (the existing `OBS-C` demo request does this on purpose, `amis/demo.py:85`, so it must stay legal).
- Deadline after mission end.
- Single request cost above total battery or free storage.

### 8.3 Backend and domain changes

- `[Rec]` New frozen value objects `OrbitalElements` and `WindowPolicy` in `amis/domain/orbit.py`.
- `[Rec]` `Satellite.orbit: OrbitalElements | None = None`, `Scenario.window_policy: WindowPolicy | None = None`, `ObservationRequest.target_name: str | None = None`.
- `[Rec]` `ObservationWindow` gains optional `peak_elevation_deg`, `min_off_nadir_deg`, `sun_elevation_deg`, `source`. All default to `None`.
- `[Rec]` `to_dict` omits these keys when they are `None`, and `from_dict` reads them with `.get`. Existing scenario JSON and every test that compares `to_dict()` output (`tests/test_cloud_block_impact.py:130`, `tests/test_emergency_request_event.py:69,171-172`, `tests/test_replan.py:76`) then stay byte-identical.
- `[Rec]` `ScenarioRepository` gains `list_summaries()` for Load Mission.

### 8.4 API changes

| Route | Change | Why |
| --- | --- | --- |
| `POST /scenarios` | Accept optional `satellite.orbit`, `window_policy`, `target_name` | Builder output is a normal scenario |
| `POST /scenarios/validate` | New. Returns errors, warnings, and a window preview count per request without persisting | Builder feedback before commit |
| `GET /scenarios` | New. Id, name, start, end, provider, created order | Load Mission |
| `GET /scenarios/{id}/plans` | New. All plan versions | Reopening a mission needs its history; today only `/plans/{id}` exists (`amis/api.py:280-287`) |
| `GET /examples`, `GET /examples/{id}` | New. The three demos as scenario templates | Examples mode (8.7) |
| `GET /demo/scenario` | Keep, alias of the cloud example | Existing frontend and tests |
| `GET /orbital-elements`, `GET /orbital-elements/{norad_id}` | New. Bundled snapshot catalogue | Satellite picker |
| `GET /scenarios/{id}/ground-track` | New, read only, orbital scenarios only | Map layer |
| `POST /scenarios/{id}/events` (`EMERGENCY_TASK`) | `windows` becomes optional when the scenario is orbital; the facade fills it before recording | ADR-0002 extension; the stored event still holds the windows |

`[Spec]` Routes stay thin (ADR-0001). The validation logic belongs in a domain or application function that the route calls, not in the handler.

### 8.5 Frontend scenario builder

`[Rec]` A "New mission" panel with four parts:

1. Mission: name, start, end (defaults to the snapshot epoch day and three days later), window provider.
2. Satellite: pick from `GET /orbital-elements` (name, NORAD id, epoch, age at mission start), or paste a TLE; resource fields with current defaults.
3. Targets: a table of requests, plus "click the map to add a target", which fills latitude and longitude. Defaults: priority 3, duration 30 s, deadline at mission end, energy 20 Wh, storage 100 MB.
4. Preview: calls `/scenarios/validate`, lists errors and warnings, shows window counts per target and draws the ground track. "Create mission" posts to `/scenarios` and hands over to the existing loop.

Import and export of scenario JSON matches Build Spec user story 6 at no extra cost because the domain already round-trips JSON (`amis/session.py:79-89`).

### 8.6 Persistence

`[Rec]` Migration `0002`: nullable JSON `orbit` on `satellites`, nullable JSON `window_policy` on `scenarios`, nullable `target_name` on `observation_requests`, nullable `peak_elevation_deg`, `min_off_nadir_deg`, `sun_elevation_deg`, `source` on `observation_windows`. The SQL repositories write and read them. No new tables are needed for Presentation 2.

`[Repo]` Commit `3fe5208` changed the primary keys of `mission_events`, `impacts`, and `decision_traces` inside `0001_initial_schema.py` instead of adding a new revision (`git log -- migrations/versions/0001_initial_schema.py`). A PostgreSQL volume created before that commit still has the old keys, and Alembic will report it as up to date. `[Rec]` Either reset the Compose volume before the presentation or make `0002` detect and repair the old keys.

### 8.7 Keeping the demo as Examples mode

`[Rec]` Navigation:

```text
New Mission
Load Mission
Examples
    Cloud Replanning Demo      build_canonical_replan_scenario()  (amis/demo.py:206)
    Battery Drop Demo          canonical scenario, battery-drop script from tests/test_battery_drop_event.py
    Emergency Request Demo     build_emergency_replan_fixture()   (amis/demo.py:251)
```

- `[Rec]` Each example sets `window_policy.provider = "canonical_demo"`, so its windows no longer depend on request ids. `ProductionWindowProvider` stays only as the fallback for scenarios with no policy, which keeps `tests/test_production_wiring.py` meaningful.
- `[Rec]` An example is loaded as a copy with a fresh id, as the frontend already does (`useMissionSession.ts:157-162`).
- `[Rec]` `python -m amis.demo` and every existing test keep calling the same builder functions. Examples only add a catalogue in front of them.

---

## 9. Synthetic versus orbital provider design

### 9.1 What generates windows today

`[Repo]` `POST /scenarios/{id}/windows/generate` (`amis/api.py:179-188`) loads a session and calls `MissionSession.generate_windows()` (`amis/session.py:91-103`), which calls `self._window_provider.generate(scenario, scenario.requests)`. The provider is `ProductionWindowProvider` in the running app (`amis/main.py:24,29`) and `SyntheticWindowProvider` when nothing is passed (`amis/session.py:75`). Once a plan exists, regeneration is refused so event effects are not erased (`amis/session.py:93-101`). Emergency requests bring their own windows (`amis/session.py:346-348`).

### 9.2 Does the abstraction hold?

`[Repo]` Yes. The protocol is one method with the right inputs. Gaps around it:

- Selection is by request id, not by scenario (`amis/demo.py:187-203`).
- Windows carry no provenance, so a stored window cannot say how it was made.
- Emergency windows bypass the provider. That is correct under ADR-0002 while windows are hand-made, and becomes a convenience gap once they can be computed.
- The provider cannot report why a request got no windows.

### 9.3 Proposed design

`[Rec]` Keep `WindowProvider` exactly as it is and add a dispatcher that is itself a `WindowProvider`:

```python
# amis/domain/orbit.py (sketch)
@dataclass(frozen=True)
class OrbitalElements:
    norad_id: int
    name: str
    international_designator: str | None
    epoch: datetime
    omm: dict[str, Any]              # canonical OMM fields, as published
    tle_line1: str | None = None     # original lines when the input was a TLE
    tle_line2: str | None = None
    source: str = "celestrak-gp"
    retrieved_at: datetime | None = None
    sha256: str = ""

@dataclass(frozen=True)
class WindowPolicy:
    provider: Literal["synthetic", "canonical_demo", "orbital"]
    max_off_nadir_deg: float = 30.0
    min_sun_elevation_deg: float | None = 10.0


# amis/windows/selection.py (sketch)
class ScenarioWindowProvider:
    def generate(self, scenario, requests) -> list[ObservationWindow]:
        policy = scenario.window_policy
        if policy is None:
            return self._legacy.generate(scenario, requests)     # ProductionWindowProvider
        return self._by_kind[policy.provider].generate(scenario, requests)
```

`[Rec]` `OrbitalWindowProvider` implements the algorithm in 7.4. Pure geometry helpers (elevation threshold from off-nadir angle, inward rounding, interval pairing) live in `amis/orbital/geometry.py` so they can be unit tested without Skyfield.

`[Rec]` The minimum sun elevation default of 10 degrees is an assumption for this project, not a figure from a mission document. Keep it configurable and show it in the scenario.

### 9.4 Can the planner and replanner stay unchanged?

`[Repo]` Code that reads windows: the greedy planner (`id`, `request_id`, `start`, `end`, `valid`; `greedy.py:76-78,124-157,216-228`), `validate_plan` (`plan_validation.py:36-48`), impact through `validate_plan`, the session's cloud-block handling (`session.py:319-330`, `696-720`), and trace metadata (`trace.py:124-133`). None of them reads a provider, and none depends on window length or count.

`[Repo]` One behaviour needs attention. When a request has no windows at all, `_unscheduled_reason` falls back to `WINDOW_INVALIDATED` (`greedy.py:260-267`), and the trace then says "its observation window was invalidated" (`trace.py:35-36`). With orbital windows this case becomes common, and the sentence would be false.

`[Rec]` Add `ReasonCode.NO_OBSERVATION_WINDOW` ("no observation window exists for its target within the mission"), return it when a request had zero candidate windows, add its template and constraint name (`window_containment`), and add its label in `frontend/src/state/planComparison.ts`. This is the only planner change in Presentation 2. Existing tests always give every request at least one window, so their outcomes stay the same.

### 9.5 Synthetic scenarios and tests keep working

- `[Repo]` Tests that construct `MissionSession(window_provider=...)` directly are unaffected by any change to `main.py`.
- `[Rec]` `tests/test_production_wiring.py` keeps passing because scenarios without a policy still reach `ProductionWindowProvider`.
- `[Rec]` New orbital tests use a committed element set and a fixed horizon, so they are as deterministic as the synthetic ones.

### 9.6 Emergency requests in orbital mode

`[Rec]` Add `MissionSession.windows_for_request(request)`, which calls the session's provider with `[request]`. The API's emergency path, when the payload has no windows and the scenario is orbital, calls it and injects the result through the existing `inject_emergency_request`. The stored event payload then holds the computed windows, so replay from the event log still needs no provider call (ADR-0002). The existing validation (`session.py:774-836`) runs unchanged on the computed windows.

### 9.7 Provenance and determinism

`[Rec]` Record with each generated set: provider kind, Skyfield and `sgp4` versions, element SHA-256, ephemeris excerpt SHA-256, `eps_min`, and policy values. The simplest place is the new `source` string on each window plus one structured record in the scenario's window-policy echo. A determinism test runs generation twice and compares JSON.

---

## 10. Post-MVP feature evaluation

| Feature | Value for the project | Cost with the current design | Recommendation |
| --- | --- | --- | --- |
| A. Real orbital windows | Highest. Turns fixed offsets into physics an examiner can check. | Medium. New provider, value objects, migration, builder. Planner unchanged. | Presentation 2 |
| B. Configurable satellite and resource models | Medium | Varies by item (below) | Split |
| C. Ground stations and downlink | High for realism, medium for the thesis | High. New action kind, storage release, reverses a locked MVP decision. | Contact windows next, downlink later |
| D. CP-SAT planner comparison | High academic value | Medium. Protocol exists (ADR-0004). | Next, right after Presentation 2 |
| E. Environmental (cloud) data | Medium | Medium. Needs ingestion and event provenance. | Final |
| F. Multi-satellite planning | Medium | High. `Scenario.satellite` is singular, `MissionState` holds one battery, overlap is global. | Final or later |

Detail for B:

| Item | Current state | Worth doing | Phase |
| --- | --- | --- | --- |
| Pointing and off-nadir limit | None | Yes, it is the window threshold | Presentation 2 (inside `WindowPolicy`) |
| Payload or instrument availability | `available` flag, `SATELLITE_UNAVAILABLE` reserved (`amis/domain/enums.py:24-25`) | Yes, as an event that toggles availability over an interval | Next |
| Observation energy from power times duration | Cost typed per request | Yes, a builder default `power_w * duration_s / 3600` | Next |
| Storage from data rate times duration | Cost typed per request | Yes, builder default | Next |
| Fixed setup or settling time between observations | None | Yes, a single `min_gap_s` checked by the overlap rule | Next |
| Time-dependent slew between targets | None | The survey shows it is "highly nonlinear" even when simplified [S19] | Final or later |
| Battery recharge in sunlight | Locked out of MVP | Needs a non-monotone projection | Final or later |
| Place actions near culmination for image quality | Actions start at window start | Changes stability behaviour; needs care | Next |

---

## 11. Ground station and downlink research

- `[External]` Downlink rates of real EO satellites are in the hundreds of Mbit/s: Pleiades transmits at a nominal 465 Mbit/s over three 155 Mbit/s channels and carries 600 Gbit of end-of-life storage [S16]; Sentinel-2 lists 490 Mbps for real-time downlink [S14].
- `[External]` Wang et al. note that most scheduling papers assume enough ground stations and ignore download, and that "the data download windows need to be obtained in advance, greatly increasing the complexity" [S19].
- `[Rec]` A contact window is an observer pass (section 7.3). The same `find_events` call at the station coordinates with a mask of 5 to 10 degrees gives contact windows. For 700 km and a 5 degree mask the spherical estimate gives at most about 10 to 12 minutes for an overhead pass; average passes are shorter. The mask values are a common engineering assumption, not taken from a cited source.
- `[Rec]` One 10 minute contact at 465 Mbit/s moves about 280 Gbit (about 35 GB). With AMIS's megabyte costs, one contact would empty storage, so downlink only matters in scenarios with large per-observation data volumes.

What the resource model would need:

```text
Observation -> storage rises at action start (today)
Contact window (new provider output, per station)
Downlink action (new action kind) -> storage falls by rate x duration, floored at zero
```

- `[Repo]` `ScheduledAction` always has a `request_id` and `window_id` (`amis/domain/plan.py:13-22`), and plan diff, traces, and metrics key everything by request id (`amis/diff.py:58`). A downlink action has no request.
- `[Repo]` `ResourceProjection` assumes storage only rises (`amis/constraints/resources.py:1-10` docstring, `62-69`). `[Spec]` "No downlink in MVP" is a locked decision.
- `[Rec]` Phase split: contact windows drawn on the timeline and map as information only (next); downlink actions, storage release, and `COMMUNICATION_OUTAGE` events (final). The downlink phase needs a new ADR that reopens the one-way resource rule and defines how diff and churn treat actions without a request.

---

## 12. CP-SAT and planner comparison research

### 12.1 Why a second planner matters

`[External]` Lemaître et al. (2002) first defined the agile scheduling problem for the Pleiades programme and compared a greedy algorithm, dynamic programming, constraint programming, and local search; the survey notes that "only the last two methods can tackle all operational constraint in real-world problem" [S19][S20]. Antuori, Wojtowicz, and Hebrard (CP 2025) solve agile constellation scheduling with local search whose sub-problems are solved greedily and then with CP-SAT, and report that CP "significantly improve[s] the solutions" [S21].

`[Rec]` For AMIS, CP-SAT answers a question the greedy planner cannot: how far from optimal is the greedy plan on the same problem, and how does each planner behave under replanning (utility kept, churn, time).

### 12.2 Mapping the AMIS problem to CP-SAT

`[External]` CP-SAT offers optional interval variables whose presence is a Boolean literal, and "the no overlap and cumulative constraints understand these presence literals, and correctly ignore inactive intervals" [S24]. `add_no_overlap` enforces one-at-a-time use of a resource [S23]. A reservoir constraint keeps a running level between bounds [S27].

`[Rec]` Model:

- Time in integer seconds from scenario start.
- For each unfrozen, unexpired request `r` and each valid window `w`: a Boolean `x[r,w]`, a start variable in `[max(w.start, now), min(w.end, r.deadline) - r.duration]`, and an optional fixed-size interval of length `r.duration`.
- `sum_w x[r,w] <= 1` per request.
- One `add_no_overlap` over all optional intervals plus fixed intervals for frozen actions.
- Resources: under the locked one-way model, the rule "each action is affordable at its start" is the same as "the sum of all selected costs fits" because costs are non-negative and nothing refills. So battery and storage are two linear constraints: `sum cost_e * x <= battery_now - committed_frozen` and the same for storage. Once recharge or downlink exist, switch to the reservoir constraint.
- Objective: maximise `sum priority * x`. For replans add a lower-weight term that penalises moving a request away from its previous window, which mirrors the greedy stability rule (ADR-0004) so churn stays comparable.
- Unscheduled reason codes: CP-SAT does not explain omissions. After solving, run the existing constraint checks for each unscheduled request against the solution to find the first failing rule, and use `DISPLACED_BY_COMPETING_REQUEST` when only overlap blocks it. That reuses the constraint functions instead of inventing reasons.

### 12.3 Determinism

`[External]` `max_time_in_seconds` is wall-clock time. `max_deterministic_time` is a work-based limit. `num_workers = 1` means "no parallelism", and with `interleave_search` "the search is deterministic (independently of num_workers!)". `random_seed` reinitialises the generator at each solve [S25].

`[Rec]` Use `num_workers = 1` (or `interleave_search`), a fixed `random_seed`, and `max_deterministic_time` instead of a wall-clock limit. Record solver status and the objective bound in the plan's timing record so the comparison can report an optimality gap. `[External]` OR-Tools 9.15 ships Windows wheels for Python 3.9 to 3.14 under Apache 2.0 [S26].

### 12.4 Comparison protocol

| Measure | Source today | Note |
| --- | --- | --- |
| Utility | `MetricsResult.mission_utility` | Same definition for both planners |
| Scheduled and completed requests | `MissionPlan.actions`, `completion_rate` | |
| Constraint violations | `MissionPlan.violation_count` from `validate_plan` | Must be 0 for both |
| Planning time | `planning_time_ms` | Report median of repeated runs; wall time is excluded from determinism checks |
| Plan churn | `plan_churn` | Replan scenarios only |
| Resource use | `battery_utilisation`, `storage_utilisation` | |
| Optimality gap | New, CP-SAT only | Objective versus bound |

`[Rec]` Run both planners over the same scenario set (the three examples plus generated orbital scenarios with 10, 25, and 50 requests), with and without events, and store results in the existing `experiment_results` table.

### 12.5 Evaluation suite proposal, informed by SkyOps

What SkyOps does [S29]:

- `[External]` Separate modules for planning (`core/orchestration/mission_planner.py`), incident replanning (`incident_replanner.py`), review (`mission_reviewer.py`), rules (`core/rules/engine.py` with `safety_rules.yaml`), and evaluation (`core/evaluation/`).
- `[External]` Metric contracts (`core/evaluation/contracts.py:16-161`) give each metric a role. The hard-constraint metric is a "blocking safety gate" that "must block the overall result" and cannot "be offset by plan efficiency". Every scorer returns the same fields: `score`, `passed`, `matched_items`, `missing_items`, `failure_reasons`.
- `[External]` 39 YAML cases (`backend/app/data/evaluation/`) grouped as smoke, normal, device, compliance, high-risk, incident, and extended. Each lists expected hard constraints, expected risks, expected response behaviours with forbidden actions, and a baseline plan.
- `[External]` The runner (`core/evaluation/runner.py:36-105`) runs load, planning, replanning, review, and scoring as named stages, raises an error naming the failing stage, sorts cases by id, and pins `generated_at` to a fixed date. The report (`core/evaluation/report.py:10-15`) labels itself `mock_simulated_evaluation` with the note that it "does not call real weather, map, airspace, drone, GPS, video link, crowd, or external evaluation APIs". The README says the numbers "are not production certification results" and still publishes the failures (28 of 39 passed).
- `[External]` A regression test replaces `socket.socket` with a function that fails, proving evaluation needs no network (`tests/test_evaluation_regression.py:336-340`).

What not to carry over:

- `[External]` The SkyOps planner returns the plan stored in the scenario file (`mission_planner.py:45-53`), and the replanner is a `match` on event type returning fixed actions (`incident_replanner.py:14-80`). The runner seeds risks from the case's own expected risks (`runner.py:119-123`). Parts of the score therefore check fixtures against themselves.
- Airspace, GPS, crowd, wind, and flight-controller concepts have no AMIS equivalent.

`[Rec]` AMIS evaluation suite:

| Part | Content |
| --- | --- |
| Case format | JSON or YAML under `amis/data/evaluation/`: scenario (or example id), window provider, a script of steps and events, and expectations written independently of the planner output. |
| Categories | `smoke` (three examples), `constraint` (one per reason code), `event_response` (cloud, battery, emergency at early, middle, late times), `orbital_window` (known geometry cases, such as a target on the ground track and one outside the field of regard), `explanation`, `planner_comparison`, `determinism`. |
| Blocking gates | `validate_plan` finds 0 violations in every plan; frozen actions identical across versions; replay from scenario plus event log reproduces plans; identical JSON across two runs. |
| Quality signals | Utility against the best known (CP-SAT) value, completion rate, churn, explanation coverage, planning time. A quality score never offsets a failed gate. |
| Explanation checks | Every changed request has a trace; every trace reason code is one the impact or constraint engine produced; no request with zero windows carries `WINDOW_INVALIDATED`. |
| Runner | `amis/evaluation/runner.py` drives `MissionSession` only, stage by stage, with the failing stage in the error. |
| Report | JSON plus a short Markdown summary: `data_origin` (synthetic or orbital snapshot with its date), library versions, and a statement that results come from a simulator and say nothing about real spacecraft operations. Failed cases are listed, not removed. |
| Network guard | A test that blocks sockets while the runner runs. |

---

## 13. Environmental data integration

- `[External]` Open-Meteo provides hourly `cloud_cover` plus low, mid, and high layers in percent, forecasts up to 16 days, and needs no key for non-commercial use [S28]. Its historical API is built on reanalysis back to 1940, with ERA5 at about 25 km resolution updated daily with a 5-day delay [S28]. Licence terms were not confirmed from the pages read.
- `[External]` The survey lists cloud coverage as a main source of failed acquisitions and describes stochastic and onboard approaches [S19].

`[Rec]` Architecture:

```text
Weather source (forecast or reanalysis)
  -> ingestion script (offline, stores raw responses with retrieval time and hash)
  -> normaliser: cloud fraction at (target, window culmination time)
  -> rule: fraction above threshold
  -> either (a) window marked invalid at generation, reason recorded in the window
     or     (b) CLOUD_BLOCK event appended at a simulated time, payload carries source, value, threshold
  -> existing impact analysis and replanning
```

- `[Rec]` Option (b) fits AMIS better. It reuses `CLOUD_BLOCK` (`amis/domain/event.py:14-27`), keeps the planner blind to weather, and puts the evidence in the event log that ADR-0002 already treats as the replay record. The payload would gain optional `source`, `cloud_cover_pct`, and `threshold_pct` fields.
- `[Rec]` Never call a weather API from the planner, the session, or a route handler. Replays read recorded values only.
- `[Rec]` Phase: final presentation.

---

## 14. Reproducible data-ingestion architecture

`[Rec]` Layers:

```text
External sources        CelesTrak GP (OMM), optional weather, optional station lists
      |  developer-run scripts only, obeying usage policies
Ingestion               raw file + retrieval time + URL + SHA-256
      |
Normalisation           OrbitalElements, CloudSample, GroundStation value objects
      |
Mission snapshot        Scenario JSON that embeds every normalised input it uses
      |                 + manifest: library versions, ephemeris excerpt hash, policy values
AMIS domain             Scenario, ObservationRequest, ObservationWindow (persisted)
      |
Planner / simulator / replanner (unchanged)
```

Replay contract:

- `[Spec]` Replay is the pristine scenario plus the event log in order (ADR-0002).
- `[Rec]` With orbital data, "pristine scenario" means the scenario JSON including its embedded element set and window policy. The same pinned Skyfield and `sgp4` versions and the same ephemeris excerpt regenerate the same windows.
- `[Repo]` Windows are also persisted (`amis/db/schema.py:92-109`) and restored rather than regenerated (`amis/session.py:417-418`), so a saved mission keeps its exact windows even if a later library version would move an edge by a second.
- `[Rec]` A replay check compares regenerated windows with stored ones and reports any difference instead of silently accepting either.
- `[Spec]` SRD principle 6 asks for "Scenario configuration and random seed" to be stored. AMIS has no randomness (redesign context, Randomness), and CP-SAT with a fixed seed and one worker keeps it that way.

---

## 15. Repository gap analysis

| Requirement | Existing implementation | Relevant files | Gap | Change required | Risk |
| --- | --- | --- | --- | --- | --- |
| Scenario creation | `POST /scenarios` with strict schema; JSON load in session | `amis/api.py:147-156`, `amis/api_schemas.py:59-78`, `amis/session.py:79-89` | No orbit, no window policy, no warnings, no listing, frontend loads demo only | Optional fields, `/scenarios/validate`, `GET /scenarios`, builder UI | Low |
| Satellite orbital data | None | `amis/domain/scenario.py:15-43` | No element set, epoch, or NORAD id | `OrbitalElements`, snapshot files, catalogue endpoint, migration | Medium (element age, parsing) |
| Target definition | Lat and lon per request | `amis/domain/scenario.py:46-56` | No name; coordinates unused for timing | Optional `target_name`; provider uses coordinates | Low |
| Synthetic windows | Three providers plus id-based dispatch | `amis/windows/synthetic.py`, `amis/demo.py:29-203`, `amis/main.py:24,29` | Selection by request id | `WindowPolicy` and `ScenarioWindowProvider`; legacy fallback | Low |
| Orbital windows | Protocol only | `amis/windows/protocol.py:15-18` | No implementation | `OrbitalWindowProvider`, geometry helpers, Skyfield dependency | Medium (geometry correctness, determinism) |
| Planner compatibility | Planner reads windows only | `amis/planning/greedy.py`, `amis/planning/protocol.py` | Wrong reason for zero windows | `NO_OBSERVATION_WINDOW` | Low |
| Constraints | Six checks plus aggregate | `amis/constraints/` | None for Presentation 2; setup time later | None now | Low |
| Simulation | Step, expiry, clamp | `amis/session.py:464-522` | Multi-day horizons need larger steps in the UI (the step input is free-form, `MissionBar.tsx:214-231`) | Optional "step to next action" control | Low |
| Events | Three types, emergency carries windows | `amis/session.py:273-389`, `amis/domain/event.py` | Emergency windows must be typed in | Facade computes windows in orbital mode | Low |
| Impact | Stored per event | `amis/impact.py:20-63` | None | None | Low |
| Replanning | Same planner with previous plan | `amis/session.py:137-192`, ADR-0004 | None | None | Low |
| Persistence | SQL and in-memory repositories, windows persisted | `amis/repositories.py`, `amis/db/` | New columns; no scenario list; `0001` edited in place | Migration `0002`, `list_summaries` | Medium (existing volumes) |
| APIs | 17 routes | `amis/api.py` | No examples, orbital catalogue, ground track, plan list | Routes in 8.4 | Low |
| Frontend | Demo-only entry, map places satellite from plan | `useMissionSession.ts:153-189`, `missionMapModel.ts:88-117`, `MissionBar.tsx:189-199` | No builder, no load, no orbit display | Builder, navigation, ground-track layer | Medium (effort) |
| Testing | 152 backend tests, provider injection | `tests/` | No orbital, no network guard, no replay-with-regeneration test | Tests per stage in section 18 | Low |
| Documentation | ADR-0006 says saves span several transactions | `.doc/adr/0006-...md:19` versus `amis/repositories.py:304-318` | Text is out of date since GAP-06 was fixed | Update the ADR consequence paragraph | Low |

---

## 16. Recommended Presentation 2 scope

### 16.1 Is the proposed pipeline realistic?

`[Rec]` Yes. Every step in the brief's Phase 2 chain either exists (constraints through metrics) or is a bounded addition (custom mission creation, element data, propagation, windows). The one step that needs care is "real target coordinates to orbit-derived windows": realistic windows are short and sparse, so the demonstration scenario must be designed around them (section 7.6).

### 16.2 Must be complete

1. Provider selection by scenario, with the three demos moved into Examples and still passing their tests.
2. `OrbitalElements` and `WindowPolicy` in the domain, API, and database, with one committed snapshot of a few EO satellites.
3. `OrbitalWindowProvider` with off-nadir threshold, sun filter, inward rounding, and duration filter.
4. Verification: independent sampler test, golden windows, determinism, network guard, and the full loop through `MissionSession` on orbital windows.
5. `NO_OBSERVATION_WINDOW` reason code and trace text.
6. Scenario Builder (New Mission), Load Mission, Examples in the frontend, and emergency windows computed in orbital mode.
7. Ground track and orbit-derived satellite position on the map, and window geometry shown on selection.

### 16.3 Optional if time allows

- Evaluation suite with the smoke, constraint, event-response, and determinism categories.
- A CP-SAT prototype on the initial plan only, compared against greedy on two or three scenarios.
- Builder helpers for energy and storage from power and data rate.
- A "step to next action" control.
- Fixed setup time between observations.

### 16.4 Suggested demonstration

`[Rec]` Create a three-day mission from the snapshot week for a real EO orbit, with six to eight Indian targets and one far-away target that has no window. Show windows on the timeline with their elevation and off-nadir values, the ground track on the map, Plan v1, a cloud block on the first real window of a high-priority target, impact, replan into its next real window, diff, trace, and metrics. Then open the Cloud Replanning Demo from Examples to show the regression scenario still works.

---

## 17. Features deferred to the final presentation

- CP-SAT planner as a full study with the comparison protocol (section 12.4), if not started as the optional prototype. Classified NEXT.
- Evaluation suite beyond the minimum categories. NEXT.
- Ground-station contact windows as information. NEXT.
- Downlink actions and storage release, `COMMUNICATION_OUTAGE`. FINAL-LATER.
- Payload availability events (`SATELLITE_UNAVAILABLE`). NEXT.
- Time-dependent slew, recharge in sunlight, quality-aware placement. FINAL-LATER or NEXT as listed in section 10.
- Weather ingestion into recorded `CLOUD_BLOCK` events. FINAL-LATER.
- Multiple satellites. FINAL-LATER.
- Live element refresh inside the running application. Not recommended at any phase.

---

## 18. Implementation sequence

`[Rec]` The brief's draft order puts persistence at step 8 and planner integration at step 7. The repository suggests a different order. Persistence columns have to land with the domain fields, because `MissionSessionStore` rebuilds the session from the database on every request and would drop an orbit that was never stored. Planner integration is a test of Stage 4 rather than a stage, because the planner needs no code change apart from one reason code. Provider selection comes first, because it protects the demo before anything new is added.

### Stage 1. Scenario-level provider selection and Examples

| Item | Detail |
| --- | --- |
| Objective | Choose windows by scenario, not request id. Turn the three demos into an Examples catalogue. |
| Existing components reused | `WindowProvider`, `SyntheticWindowProvider`, `CanonicalWindowProvider`, `ProductionWindowProvider` (legacy fallback), demo builders in `amis/demo.py`. |
| Files likely affected | `amis/domain/scenario.py`, `amis/domain/__init__.py`, `amis/api_schemas.py`, `amis/api.py`, `amis/main.py`, `amis/db/schema.py`, `amis/db/repositories.py`, new `amis/domain/orbit.py` (`WindowPolicy` only), new `amis/windows/selection.py`, new `amis/examples.py`, new migration. |
| New components | `WindowPolicy`, `ScenarioWindowProvider`, examples catalogue. |
| API and domain changes | `Scenario.window_policy` optional; `GET /examples`, `GET /examples/{id}`; `GET /demo/scenario` kept. |
| Tests required | All 152 existing tests pass unchanged. New: a scenario with policy `synthetic` and a request named `OBS-A` gets one whole-horizon window; each example reproduces its known outcome through the API; round trip of `window_policy`; SQL persistence of the policy. |
| Dependencies | None. |
| Risks | JSON shape drift. Mitigate by omitting `None` fields in `to_dict`. |
| Acceptance criteria | `python -m amis.demo` output unchanged; `test_production_wiring.py` passes; examples load from the API. |

### Stage 2. Orbital data representation

| Item | Detail |
| --- | --- |
| Objective | Carry a real element set inside a scenario, validated and persisted. |
| Existing components reused | Domain `to_dict`/`from_dict` pattern, `ScenarioSchema` validators, SQL repositories. |
| Files likely affected | `amis/domain/orbit.py`, `amis/domain/scenario.py`, `amis/domain/window.py` (optional geometry fields), `amis/api_schemas.py`, `amis/db/schema.py`, `amis/db/repositories.py`, `migrations/versions/0002_*.py`, `pyproject.toml` (package data), new `amis/orbital/elements.py`, new `amis/data/elements/`, new `scripts/fetch_orbital_elements.py`, new ADR. |
| New components | `OrbitalElements`, element parser for OMM JSON and TLE, snapshot catalogue loader with checksum check, fetch script. |
| API and domain changes | `Satellite.orbit`, `ObservationRequest.target_name`, window geometry fields; `GET /orbital-elements`, `GET /orbital-elements/{norad_id}`. |
| Tests required | Parse OMM and TLE for the same satellite and compare fields; reject bad checksum, bad line length, and bad epoch; JSON round trip; SQL round trip; migration upgrade on an empty database and on a database created from the old `0001`. |
| Dependencies | Stage 1. `skyfield` may be imported here only for `from_omm` validation; otherwise none. |
| Risks | Existing PostgreSQL volumes (section 8.6). Catalogue ids from secondary sources. |
| Acceptance criteria | A scenario with an orbit survives create, restart, and load unchanged. The catalogue endpoint lists the snapshot with epochs. |

### Stage 3. OrbitalWindowProvider

| Item | Detail |
| --- | --- |
| Objective | Produce EO target windows from the orbit, policy, and request coordinates. |
| Existing components reused | `WindowProvider` protocol, `ObservationWindow`, window id convention. |
| Files likely affected | New `amis/orbital/geometry.py`, new `amis/windows/orbital.py`, `amis/windows/selection.py`, `amis/windows/__init__.py`, `pyproject.toml` (pinned `skyfield`, `sgp4`), new `amis/data/ephemeris/` excerpt. |
| New components | Geometry helpers, provider, ephemeris excerpt with checksum. |
| API and domain changes | None beyond Stage 2. |
| Tests required | Geometry unit tests against the table in 7.2; provider returns windows sorted and inside the horizon; windows shorter than the duration are dropped; night windows dropped when the sun filter is on and kept when it is off; target far from any track gets none. |
| Dependencies | Stage 2. |
| Risks | Wrong threshold sign or frame; Python 3.14 compatibility; Skyfield release changes. |
| Acceptance criteria | For the committed snapshot and a fixed three-day horizon, generation is repeatable byte for byte, and each window's peak elevation is at least the threshold. |

### Stage 4. Window verification and loop integration

| Item | Detail |
| --- | --- |
| Objective | Prove the windows are correct and that the unchanged loop runs on them. |
| Existing components reused | `MissionSession`, `GreedyPlanner`, `validate_plan`, `analyze_impact`, `compare_plans`, `build_traces`, `compute_metrics`. |
| Files likely affected | `amis/domain/enums.py`, `amis/planning/greedy.py` (`_unscheduled_reason`), `amis/trace.py`, `frontend/src/state/planComparison.ts`, `frontend/src/api/schema.ts` (regenerated), new tests. |
| New components | `NO_OBSERVATION_WINDOW` reason code; test-only 1 s sampler; golden window fixture. |
| API and domain changes | One new reason code in the OpenAPI enum. |
| Tests required | Sampler agrees with provider edges within 2 s; golden file comparison; two runs identical; socket-blocking test around generation and planning; full loop (plan, step, cloud block on a real window, impact, replan, compare, traces, metrics) with explanation coverage 1.0 and zero violations; request with zero windows reports `NO_OBSERVATION_WINDOW`. |
| Dependencies | Stage 3. |
| Risks | Golden files tied to library versions; mitigate by recording versions in the fixture and failing with a clear message. |
| Acceptance criteria | The canonical loop assertions from `tests/test_canonical_replan_demo.py` have an orbital counterpart that passes. |

### Stage 5. Scenario creation, listing, and emergency APIs

| Item | Detail |
| --- | --- |
| Objective | Give the frontend everything it needs to build, validate, list, and reopen missions. |
| Existing components reused | `MissionSessionStore`, `ScenarioSchema`, emergency validation in the session. |
| Files likely affected | `amis/api.py`, `amis/api_schemas.py`, `amis/repositories.py`, `amis/db/repositories.py`, `amis/session.py` (`windows_for_request`), new `amis/scenario_validation.py`. |
| New components | Scenario validation report (errors, warnings, window preview), scenario summaries. |
| API and domain changes | `POST /scenarios/validate`, `GET /scenarios`, `GET /scenarios/{id}/plans`, optional emergency windows in orbital mode. |
| Tests required | Validation returns each warning in 8.2; stale epoch rejected; listing works in memory and in SQL; plan list matches stored versions; emergency request without windows in an orbital scenario stores computed windows in the event, and replay from the event log gives the same plans. |
| Dependencies | Stage 4. |
| Risks | Routes growing logic. Keep validation in a module the route calls. |
| Acceptance criteria | An httpx test builds a mission from a catalogue satellite, runs the loop, restarts the app, lists the mission, and reopens it with all plan versions. |

### Stage 6. Scenario Builder UI and navigation

| Item | Detail |
| --- | --- |
| Objective | New Mission, Load Mission, Examples in the dashboard. |
| Existing components reused | `useMissionSession`, `MissionBar`, `MissionNavPanel`, generated API client, map engine for click-to-add. |
| Files likely affected | `frontend/src/state/useMissionSession.ts`, `frontend/src/panels/MissionBar.tsx`, `frontend/src/panels/MissionNavPanel.tsx`, `frontend/src/api/amis.ts`, new `frontend/src/panels/ScenarioBuilder.tsx`, new `frontend/src/state/scenarioDraft.ts`, tests. |
| New components | Draft model with validation display, satellite picker, target table. |
| API and domain changes | None. |
| Tests required | Draft model unit tests; builder posts the expected JSON; warnings render; Load Mission restores plans; Examples still reach the cloud demo story (existing `App.test.tsx` flows adapted). |
| Dependencies | Stage 5. |
| Risks | UI scope growth. Keep one panel. |
| Acceptance criteria | A reviewer creates an orbital mission in the browser without editing JSON and runs the loop. |

### Stage 7. Mission-control visualisation updates

| Item | Detail |
| --- | --- |
| Objective | Show where the satellite actually is and why a window exists. |
| Existing components reused | `missionMapModel.ts`, `missionLayers.ts`, timeline window bands. |
| Files likely affected | `amis/api.py`, new `amis/orbital/track.py`, `frontend/src/map/missionMapModel.ts`, `frontend/src/map/missionLayers.ts`, `frontend/src/panels/MissionMapPanel.tsx`, `frontend/src/timeline/missionTimelineModel.ts`. |
| New components | Ground-track read endpoint; map layer; window tooltip with peak elevation, off-nadir, sun elevation. |
| API and domain changes | `GET /scenarios/{id}/ground-track?start&end&step_s`. |
| Tests required | Endpoint returns points within the horizon; map model uses the track position when present and falls back to the current plan-based placement for synthetic scenarios. |
| Dependencies | Stage 5; can run in parallel with Stage 6. |
| Risks | Antimeridian splitting of the track line. |
| Acceptance criteria | For an orbital mission, the satellite marker sits on the ground track at the simulated time and passes over each observed target during its action. |

### Stage 8. Evaluation suite (optional for Presentation 2)

| Item | Detail |
| --- | --- |
| Objective | Measured, repeatable evidence across many cases (section 12.5). |
| Existing components reused | `MissionSession`, metrics, `experiment_results` table. |
| Files likely affected | New `amis/evaluation/`, new `amis/data/evaluation/`, new tests, optional CLI in `amis/demo.py` or a new module. |
| New components | Case loader, runner, gates, report. |
| API and domain changes | None required. |
| Tests required | Runner determinism with fixed timestamps; socket guard; each gate fails on a crafted bad plan. |
| Dependencies | Stage 4. |
| Risks | Self-grading fixtures (the SkyOps lesson). Expectations must not come from the planner's own output. |
| Acceptance criteria | One command prints a report with case counts, failures, data origin, and library versions. |

### Stage 9. CP-SAT planner and comparison (NEXT)

| Item | Detail |
| --- | --- |
| Objective | A second `Planner` and a fair comparison with greedy. |
| Existing components reused | `Planner` protocol, constraint functions for reason attribution, metrics, evaluation runner. |
| Files likely affected | New `amis/planning/cpsat.py`, `amis/planning/__init__.py`, `pyproject.toml` (optional `ortools` extra), `amis/main.py` or a config switch, tests. |
| New components | CP-SAT model, reason attribution pass, comparison report. |
| API and domain changes | Optional planner choice per scenario or per run, recorded in the plan. |
| Tests required | Every existing behavioural planner test run against both planners where the outcome is planner-independent; zero violations; deterministic output with one worker and fixed seed; utility at least equal to greedy on every case. |
| Dependencies | Stage 8 for the comparison report. |
| Risks | Tests coupled to greedy order (the Build Spec warns about this); solve time on larger orbital cases. |
| Acceptance criteria | Comparison table over the case set with utility, violations, time, churn, and gap. |

### Stage 10 and later

Ground-station contact windows (information only), payload availability events, energy and storage derived from power and data rate, fixed setup time, then downlink actions, weather ingestion, and multiple satellites, each behind its own ADR.

---

## 19. File-level change map

| File | Change | Stage |
| --- | --- | --- |
| `amis/domain/orbit.py` | New: `OrbitalElements`, `WindowPolicy` | 1, 2 |
| `amis/domain/scenario.py` | Optional `window_policy`, `Satellite.orbit`, `target_name`; omit `None` in `to_dict` | 1, 2 |
| `amis/domain/window.py` | Optional geometry and `source` fields | 2 |
| `amis/domain/enums.py` | `ReasonCode.NO_OBSERVATION_WINDOW` | 4 |
| `amis/domain/__init__.py` | Export new types | 1, 2 |
| `amis/windows/selection.py` | New `ScenarioWindowProvider` | 1 |
| `amis/windows/orbital.py` | New `OrbitalWindowProvider` | 3 |
| `amis/windows/__init__.py` | Export new providers | 1, 3 |
| `amis/orbital/elements.py` | New: parse, validate, checksum, catalogue | 2 |
| `amis/orbital/geometry.py` | New: pure geometry helpers | 3 |
| `amis/orbital/track.py` | New: ground track samples | 7 |
| `amis/examples.py` | New: Examples catalogue over `amis/demo.py` builders | 1 |
| `amis/demo.py` | Examples set `window_policy`; `ProductionWindowProvider` kept as legacy | 1 |
| `amis/main.py` | Wire `ScenarioWindowProvider` | 1 |
| `amis/planning/greedy.py` | Zero-window reason | 4 |
| `amis/trace.py` | Template and constraint name for the new code | 4 |
| `amis/session.py` | `windows_for_request` | 5 |
| `amis/scenario_validation.py` | New: errors, warnings, preview | 5 |
| `amis/repositories.py` | `ScenarioRepository.list_summaries` and in-memory version | 5 |
| `amis/api.py` | Routes in section 8.4 | 1, 2, 5, 7 |
| `amis/api_schemas.py` | Optional fields, new response models | 1, 2, 5, 7 |
| `amis/db/schema.py`, `amis/db/repositories.py` | New columns, list query | 1, 2, 5 |
| `migrations/versions/0002_orbital_scenarios.py` | New columns; repair old keys if present | 1, 2 |
| `amis/data/elements/` | Snapshot files and manifest | 2 |
| `amis/data/ephemeris/` | `de421` excerpt with checksum | 3 |
| `scripts/fetch_orbital_elements.py` | Developer-only fetch, policy-compliant | 2 |
| `pyproject.toml` | Pinned `skyfield`, `sgp4`; package data; later optional `ortools` | 2, 3, 9 |
| `amis/evaluation/`, `amis/data/evaluation/` | Evaluation suite | 8 |
| `amis/planning/cpsat.py` | CP-SAT planner | 9 |
| `tests/test_window_provider_selection.py`, `test_examples.py`, `test_orbital_elements.py`, `test_orbital_geometry.py`, `test_orbital_window_provider.py`, `test_orbital_loop.py`, `test_no_network.py`, `test_scenario_builder_api.py` | New tests | 1 to 5 |
| `frontend/src/api/schema.ts`, `frontend/src/api/amis.ts` | Regenerated types, new calls | 4 to 7 |
| `frontend/src/state/useMissionSession.ts` | Create, load, examples flows | 6 |
| `frontend/src/state/scenarioDraft.ts`, `frontend/src/panels/ScenarioBuilder.tsx` | New builder | 6 |
| `frontend/src/panels/MissionBar.tsx`, `MissionNavPanel.tsx` | New Mission, Load Mission, Examples | 6 |
| `frontend/src/state/planComparison.ts` | Label for the new reason code | 4 |
| `frontend/src/map/missionMapModel.ts`, `missionLayers.ts`, `panels/MissionMapPanel.tsx` | Ground track, orbit position | 7 |
| `frontend/src/timeline/missionTimelineModel.ts` | Window geometry in tooltips | 7 |
| `CONTEXT.md` | Glossary: `OrbitalElements`, `WindowPolicy`, Example; window as visible time window | 1, 2 |
| `.doc/adr/0007-*.md`, `.doc/adr/0008-*.md` | Window meaning and provenance; offline orbital snapshots | 2, 3 |
| `.doc/adr/0006-*.md` | Update the out-of-date transaction paragraph | 1 |

---

## 20. Risks and open questions

| Risk or question | Impact | Mitigation |
| --- | --- | --- |
| Element age against mission dates | Windows drift by seconds per day of age; beyond two weeks they become unreliable [S1] | Date missions to the snapshot week; warn at 7 days, reject at 14 |
| Sparse, short windows | A one-day demo may schedule little | Three to five day horizon, 45 degree option, more targets; show `NO_OBSERVATION_WINDOW` |
| Determinism across Skyfield versions | Built-in time tables change per release [S3] | Pin versions, store windows, record versions, replay comparison |
| Python 3.14 locally, 3.11 in Docker | A dependency may behave differently or fail to install | Run the orbital tests on both before Stage 3 is accepted |
| `0001` edited in place | Old PostgreSQL volumes keep old keys | Reset volumes or repair in `0002` |
| Geometry mistakes | Wrong windows look plausible | Independent sampler, table checks, golden files |
| Honest framing | An examiner may read "Sentinel-2" as "tasking Sentinel-2" | Label as hypothetical agile imager on a real orbit (7.2) |
| Scope growth in the builder | Delays the orbital core | Builder after Stage 4; one panel |
| Actions start at the most oblique point | Realistic but poor imaging choice | Document; culmination-centred placement is NEXT |
| Open: should `duration_s` include settling time? | Changes window fit | Decide in the window ADR; recommended yes for Presentation 2 |
| Open: minimum sun elevation default | Changes optical windows | 10 degrees as a stated assumption, configurable |
| Open: store OMM only, or OMM plus TLE text | Storage and display | Store OMM, keep TLE lines when supplied |
| Open: licence of the reference dashboard | Copying code | No `LICENSE` at `89825ff`; concepts only |
| Open: exact NORAD ids and snapshot contents | Catalogue correctness | Confirm against CelesTrak when fetching |

---

## 21. Source references

AMIS repository (commit `3fe5208`): `CONTEXT.md`; `.doc/specs/AMIS_PRD.md`, `AMIS_SRD.md`, `AMIS_Implementation_Guide.md`, `AMIS_Build_Spec.md`, `AMIS_Project_Analysis.md`; `.doc/adr/0001` to `0006`; `.doc/audits/AMIS_FULL_SYSTEM_AUDIT.md`, `AMIS_AUDIT_VERIFICATION.md`, `frontend-backend-contract-audit.md`; `.doc/status/feature-implementation-status.md`; `.doc/reference/*`; `.doc/demo/*`; `.doc/prompts/System Redesing Prompts/AMIS_REDESIGN_CONTEXT Prompts.md`; `amis/`, `tests/`, `migrations/`, `frontend/src/`.

External sources:

| Id | Source | URL |
| --- | --- | --- |
| S1 | Skyfield, Earth Satellites | https://rhodesmill.org/skyfield/earth-satellites.html |
| S2 | Skyfield API, EarthSatellite (`find_events`, `from_omm`) | https://rhodesmill.org/skyfield/api-satellites.html |
| S3 | Skyfield, Dates and Time (built-in tables) | https://rhodesmill.org/skyfield/time.html |
| S4 | Skyfield, Planets and ephemeris files | https://rhodesmill.org/skyfield/planets.html |
| S5 | Skyfield, Examples (Sun altitude at a location) | https://rhodesmill.org/skyfield/examples.html |
| S6 | Skyfield on PyPI (1.55, MIT) | https://pypi.org/project/skyfield/ |
| S7 | `sgp4` on PyPI (2.27, TEME, OMM, MIT) | https://pypi.org/project/sgp4/ and https://github.com/brandon-rhodes/python-sgp4 |
| S8 | `jplephem` excerpt command | https://github.com/brandon-rhodes/python-jplephem and https://github.com/skyfielders/python-skyfield/issues/443 |
| S9 | CelesTrak, A New Way to Obtain GP Data (OMM, formats, catalog limit) | https://celestrak.org/NORAD/documentation/gp-data-formats.php |
| S10 | CelesTrak, Current GP Element Sets (groups) | https://celestrak.org/NORAD/elements/ |
| S11 | CelesTrak, Usage Policy | https://celestrak.org/usage-policy.php |
| S12 | Space-Track documentation and the `spacetrack` client docs | https://www.space-track.org/documentation and https://spacetrack.readthedocs.io/en/latest/usage.html |
| S13 | ESA, Sentinel-2 facts and figures | https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-2/Facts_and_figures |
| S14 | Copernicus SentiWiki, S2 Mission | https://sentiwiki.copernicus.eu/web/s2-mission |
| S15 | USGS, Landsat 9 | https://www.usgs.gov/landsat-missions/landsat-9 |
| S16 | eoPortal, Pleiades-HR | https://www.eoportal.org/satellite-missions/pleiades |
| S17 | Airbus, Pleiades Imagery User Guide | https://www.engesat.com.br/wp-content/uploads/PleiadesUserGuide-17062019.pdf |
| S18 | N2YO satellite pages for NORAD ids 40697, 42063, 39084, 49260 | https://www.n2yo.com/satellite/?s=40697 |
| S19 | Wang, Wu, Xing, Pedrycz, "Agile Earth Observation Satellite Scheduling Over 20 Years: Formulations, Methods, and Future Directions", IEEE Systems Journal 15(3), 2021, doi:10.1109/JSYST.2020.2997050 | https://arxiv.org/abs/2003.06169 |
| S20 | Lemaître, Verfaillie, Jouhaud, Lachiver, Bataille, "Selecting and scheduling observations of agile satellites", Aerospace Science and Technology 6(5):367-381, 2002 | https://www.sciencedirect.com/science/article/abs/pii/S1270963802011732 |
| S21 | Antuori, Wojtowicz, Hebrard, "Solving the Agile Earth Observation Satellite Scheduling Problem with CP and Local Search", CP 2025, LIPIcs 340 | https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2025.3 |
| S22 | Nugnes, Colombo, Tipaldi, "Coverage Area Determination for Conical Fields of View Considering an Oblate Earth", 2019 | https://arxiv.org/abs/1906.12318 |
| S23 | OR-Tools, The Job Shop Problem (interval variables, `add_no_overlap`) | https://developers.google.com/optimization/scheduling/job_shop |
| S24 | OR-Tools CP-SAT scheduling documentation (optional intervals) | https://github.com/google/or-tools/blob/stable/ortools/sat/docs/scheduling.md |
| S25 | OR-Tools `sat_parameters.proto` (determinism parameters) | https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto |
| S26 | `ortools` on PyPI (9.15, Apache 2.0) | https://pypi.org/project/ortools/ |
| S27 | OR-Tools CP-SAT Python API (`add_reservoir_constraint`) | https://github.com/google/or-tools/blob/stable/ortools/sat/python/cp_model.py |
| S28 | Open-Meteo Weather Forecast API and Historical Weather API | https://open-meteo.com/en/docs and https://open-meteo.com/en/docs/historical-weather-api |
| S29 | Ceng-0324/SkyOps at `aa895e7` | https://github.com/Ceng-0324/SkyOps |
| S30 | patrickkuei/Satellite-Mission-Control-Dashboard at `89825ff` | https://github.com/patrickkuei/Satellite-Mission-Control-Dashboard |

Sources that could not be read directly:

- S20 returned HTTP 403. Its content is cited through the survey S19, which was read in full as a PDF.
- S8: the `jplephem` PyPI page did not render and the GitHub README did not include the excerpt section. The command comes from search results quoting the package description; confirm it before relying on it.
- S12, S15, S17, S18: facts come from search-result summaries of these pages, not from reading them.
- The NASA Small Spacecraft Technology state-of-the-art chapter on ground systems was read and did not contain elevation-mask or contact-length figures, so section 11 marks those values as assumptions.

---

## Appendix A. Recommended architecture

```text
Realistic inputs
  Offline OMM/TLE snapshots, target coordinates, mission dates, window policy
      ↓
Providers / ingestion
  Developer fetch scripts (never at runtime) -> normalised OrbitalElements
  ScenarioWindowProvider -> Synthetic | CanonicalDemo | Orbital (Skyfield + sgp4)
      ↓
AMIS domain
  Immutable Scenario with embedded orbit and policy; ObservationRequest; ObservationWindow with geometry and source
      ↓
Existing planning core
  Planner protocol: GreedyPlanner now, CP-SAT next; constraint engine; reason codes
      ↓
Simulation
  MissionSession.step: clock, resources, expiry, frozen actions
      ↓
Events / impact
  CLOUD_BLOCK, BATTERY_DROP, EMERGENCY_TASK (orbital windows computed at injection, stored in the event)
      ↓
Adaptive replanning
  Same planner with previous plan, stability rule, immutable versions
      ↓
Explanation / evaluation
  Plan diff, DecisionTrace, metrics, evaluation suite report, planner comparison
```

## Appendix B. Feature classification

| Feature | Classification |
| --- | --- |
| Scenario-level window provider selection | PRESENTATION 2 |
| Examples mode for the three demos | PRESENTATION 2 |
| `OrbitalElements` in the domain, API, and database | PRESENTATION 2 |
| OMM storage with TLE accepted on input | PRESENTATION 2 |
| Committed element snapshot with manifest and checksums | PRESENTATION 2 |
| Developer fetch script obeying CelesTrak policy | PRESENTATION 2 |
| Skyfield propagation (pinned with `sgp4`) | PRESENTATION 2 |
| `OrbitalWindowProvider` with off-nadir threshold | PRESENTATION 2 |
| Sun elevation filter for optical requests | PRESENTATION 2 |
| `de421` ephemeris excerpt | PRESENTATION 2 |
| Window geometry and provenance fields | PRESENTATION 2 |
| Element-age validation | PRESENTATION 2 |
| `NO_OBSERVATION_WINDOW` reason code | PRESENTATION 2 |
| Independent window verification tests and network guard | PRESENTATION 2 |
| Emergency windows computed by the provider | PRESENTATION 2 |
| `POST /scenarios/validate`, `GET /scenarios`, `GET /scenarios/{id}/plans` | PRESENTATION 2 |
| Scenario Builder, Load Mission | PRESENTATION 2 |
| Ground track and orbit-derived satellite position | PRESENTATION 2 |
| Migration `0002` and old-volume handling | PRESENTATION 2 |
| ADR updates (window meaning, offline snapshots, ADR-0006 text) | PRESENTATION 2 |
| Evaluation suite, minimum categories | PRESENTATION 2 (optional) |
| "Step to next action" control | PRESENTATION 2 (optional) |
| Evaluation suite, full | NEXT |
| CP-SAT planner | NEXT |
| Greedy versus CP-SAT comparison study | NEXT |
| Experiment results persistence | NEXT |
| Payload availability events (`SATELLITE_UNAVAILABLE`) | NEXT |
| Energy and storage defaults from power and data rate | NEXT |
| Fixed setup time between observations | NEXT |
| Culmination-centred action placement | NEXT |
| Ground-station contact windows (information only) | NEXT |
| Downlink actions and storage release | FINAL-LATER |
| `COMMUNICATION_OUTAGE` event | FINAL-LATER |
| Time-dependent slew model | FINAL-LATER |
| Battery recharge in sunlight | FINAL-LATER |
| Weather ingestion into recorded `CLOUD_BLOCK` events | FINAL-LATER |
| Multiple satellites | FINAL-LATER |
| Space-Track integration | FINAL-LATER |
| Live element refresh in the running app | Not recommended |
| Browser-side propagation, telemetry simulation, polling (from the reference dashboard) | Not recommended |
| SkyOps drone concepts (airspace, GPS, crowd, flight control) | Not recommended |
