## AMIS in one line

- AMIS is a local simulator that plans which Earth photos a satellite should take, breaks the plan on purpose, fixes it, and explains the fix.
- You are not building satellite control. You are building decision support for planning.
- Full loop you must show in demo:
  - Create scenario
  - Generate windows
  - Create valid plan
  - Simulate
  - Inject change
  - Detect impact
  - Replan
  - Explain
  - Compare and measure

## Where this came from

### The 7 sources listed in `.doc/specs/Research paper`

- 1. Satellite scheduling problems survey. Imaging tasks, constraints, optimization methods. This gives your problem definition and proof that scheduling is NP-hard.
- 2. Dynamic Earth observation scheduling. Tasks arrive over time, with deadlines and stability. This gives your emergency request and frozen actions idea.
- 3. Cloud aware scheduling. Clouds make optical takes useless. This gives your CLOUD_BLOCK event.
- 4. NASA JPL CASPER. Continuous Activity Scheduling, Planning, Execution and Replanning. This gives your core loop of plan, execute, replan in one loop.
- 5. NASA EO-1 Autonomous Sciencecraft Experiment. Real flight test on Earth Observing-1 since 2004. Onboard science, CASPER planner, robust execution. This proves autonomy works in space and saves cost.
- 6. Dynamic scheduling with perturbations. How to adapt a plan with minimum disruption. This gives your churn metric and stability rule.
- 7. Autonomous planning for Earth observation, IEEE. Long term planning, rolling replanning, emergency planning. This gives your versioned plans and replan flow.

### What web research adds

- Ferrari et al 2024 in Computers and Operations Research surveys satellite scheduling. It models agile scheduling as Team Orienteering with Time Windows. It confirms exact methods do not scale, heuristics are normal.
- Wang et al surveys Agile Earth Observation Satellite Scheduling Problem, AEOSSP, 62 papers 1997 to 2019. It defines Visible Time Window, VTW, and Observation Time Window, OTW. It lists energy and memory limits per orbit.
- NASA ASE validation report. EO-1 ran CASPER onboard with 8 MIPS CPU and 32 MB heap. It used iterative repair. Fix conflicts one by one until clean. It cut ops cost from 3.6M to 1.6M dollars per year. Your greedy plus CP-SAT is the same family of ideas, run on ground as simulator.
- Pleiades flies at 694 km, plus or minus 30 deg standard view, 47 deg max. Sentinel-2 has 290 km swath but cannot point, it follows a fixed plan. Landsat 8 and 9 fly at 705 km with 185 km swath. Your project says honestly, real orbit plus hypothetical agile imager with 30 deg field of regard.
- Orbit data path is standard. CelesTrak gives TLE and OMM JSON. SGP4 propagates. Skyfield 1.55 wraps sgp4 2.27, adds frames, sun, event search. TLE is good to about 1 km at epoch and degrades in weeks. That is why you validate epoch age.

## Non technical story to tell examiner

- Think of one delivery rider, one day, many orders.
- Each order has location, tip, time needed, deadline, fuel cost.
- Rider can only reach some orders at some times. Those are windows.
- You make best route first. That is Plan v1.
- Then rain blocks a road, fuel drops, or urgent order arrives. Those are events.
- You check what broke. That is impact.
- You keep delivered orders fixed and remake rest. That is replan to Plan v2.
- You list what moved, what dropped, what is new, and why in plain sentences. That is diff plus trace.
- You score both plans. That is metrics.
- Say this in first 60 seconds. Internal professor wants clarity, not jargon.

## Technical core, part by part

### Scenario

- A scenario is one full mission definition.
- It holds id, name, start and end time with timezone, one satellite, list of observation requests.
- It is immutable. You never edit it. You replay it plus event log to get same result. See `.doc/adr/0002-scenario-is-immutable-and-the-event-log-is-the-replay-unit.md`.
- Say, scenario is the exam paper. Plans are answers. Events are disturbances during exam.

### Satellite

- One satellite per scenario, for example SAT-001.
- It has battery capacity and charge in Wh, storage capacity and usage in MB, available flag.
- Phase 2 adds orbit. `satellite.orbit` is OrbitalElements or None. It holds NORAD id, name, epoch, OMM dict, optional TLE lines, source, retrieved time, sha256.
- No live position in domain. Ground track is computed for display only, never fed back to planner.

### ObservationRequest

- What user wants observed. No start time.
- Fields are id, target lat and lon, optional target name, priority 1 to 5, duration in seconds, deadline, energy cost, storage cost, status.
- Demo uses Indian cities. Bengaluru 12.97, 77.59. Delhi 28.61, 77.21. Mumbai 19.08, 72.88. Chennai 13.08, 80.27. Kolkata 22.57, 88.36. Hyderabad 17.38, 78.49. Emergency is Los Angeles 34.05, -118.24.
- Say, request is wish. Window is chance. Action is booking.

### ObservationWindow and contact window

- ObservationWindow is span where one target can be imaged under policy.
- Fields are id, request id, satellite id, start, end, valid, invalid reason, plus optional peak elevation, min off nadir, sun elevation, source.
- Contact window is span where satellite is above a ground station mask at 5 to 10 deg. Derived, never stored. Comms outage marks overlapping contacts invalid.
- Synthetic mode gives one whole horizon window per request. File `amis/windows/synthetic.py:14-29`.
- Canonical demo gives fixed offsets. OBS-B has two windows at +20 and +75 min so cloud move is possible. File `amis/demo.py:130-163`.
- Orbital mode computes real VTW from orbit with Skyfield `find_events`, sun filter, inward rounding to seconds, drop if shorter than duration. File `amis/windows/orbital.py` plus `amis/orbital/geometry.py`.
- Geometry rule for spherical Earth:
  - sin off nadir equals R over R plus h times cos elevation
  - At h equals 705 km, 30 deg off nadir needs about 56.3 deg elevation at target, lasts about 120 sec max
  - Horizon pass would be about 64 deg off nadir and 2860 km away. Too tilted for imaging. That is why you do not use 0 deg threshold.
- WindowPolicy holds provider name plus max off nadir, min sun elevation, station ids, settling time, start at culmination flag.

### Planner

- Planner takes scenario, mission state, requests, windows, returns mission plan. See `amis/planning/protocol.py`.
- `select_planner` picks by name. Choice is stored as `planner_name` on plan.
- GreedyPlanner in `amis/planning/greedy.py:62-274`:
  - Sort by priority down, deadline up, duration up, id up
  - Try window start and slots after placed actions
  - Check containment, deadline, overlap, battery, storage, availability
  - Put in earliest feasible slot
  - Else mark unscheduled with reason code
  - Frozen actions carried forward unchanged
  - Fast, deterministic, easy to explain
- CpSatPlanner in `amis/planning/cp_sat.py`:
  - Uses OR-Tools CP-SAT, single worker, fixed seed, time limit
  - Stores solver details with status, objective, bound, gap, fallback flag, lib version
  - Better utility on tight problems, slower, harder to explain step by step
  - Same protocol, so simulation and UI do not change. See `.doc/adr/0009-planner-selection-and-cp-sat-determinism.md` and `0004-replanning-runs-through-the-planner-protocol.md`.
- MissionPlan is immutable version with parent id, actions, unscheduled with reasons, utility, violation count, planning time.
- ScheduledAction is one request in one window at one start, imaging or downlink kind. Downlinks are re derived each plan, ignored in diff and churn per ADR-0011.
- Mission utility equals sum of priorities of scheduled plus completed, deduplicated.
- Say, greedy is first come best served by rank. CP-SAT is full search with proof of quality.

### Constraints

- Six checks in `amis/constraints/`:
  - Containment in window
  - Deadline
  - No overlap
  - Battery projected
  - Storage projected
  - Satellite available
- Each break gives Violation with reason code and subject key.
- `validate_plan` checks unfrozen actions only. Frozen are exempt per ADR-0003.
- Say, constraints are exam rules. Violation is which rule broke and for which request.

### MissionState and simulation

- MissionState holds clock, battery, storage, availability, active event ids, completed ids, mission complete flag. File `amis/domain/state.py:12-60`.
- `MissionSession.step` in `amis/session.py:464-522`:
  - Advances clock
  - Starts and completes actions
  - Charges cost on start
  - Expires requests past deadline with no action. Expiry is permanent.
  - Clamps at end
- Deterministic for same scenario and seed.
- Say, simulation is time machine with fixed script.

### MissionEvent, impact, replan

- Five events:
  - CLOUD_BLOCK with request id and window id, marks window invalid
  - BATTERY_DROP with new battery level, breaks future power plans
  - EMERGENCY_TASK with new request plus windows, or computed in orbital mode
  - Payload outage over interval, toggles availability
  - Communication outage over interval for one station
- Frozen means start at or before now. Never move, drop, or recost frozen. File `amis/session.py:137-192`.
- Impact is stored at inject time. It names plan version and splits unfrozen into valid and invalid. File `amis/impact.py:20-63`.
- Replan calls same Planner with previous plan, preserves feasible future where possible, creates new version, then diff, traces, metrics.
- Say, event is surprise quiz change. Impact is list of affected answers. Replan is rewrite of remaining pages without touching checked pages.

### Diff, trace, metrics

- PlanDiff in `amis/diff.py:58-165` keys by request id:
  - Unchanged
  - Moved
  - Inserted
  - Dropped
  - Completed
- DecisionTrace in `amis/trace.py:61-106` links event, constraint, old action, new action, sentence. Reason codes are source of truth, text is generated.
- Reason codes include WINDOW_INVALIDATED, INSUFFICIENT_BATTERY, INSUFFICIENT_STORAGE, DEADLINE_VIOLATION, TIME_OVERLAP, SATELLITE_UNAVAILABLE, HIGHER_PRIORITY_TASK_INSERTED, ALTERNATIVE_WINDOW_AVAILABLE, NO_ALTERNATIVE_WINDOW, NO_OBSERVATION_WINDOW, TASK_UNCHANGED.
- Metrics in `amis/metrics.py:30-123`:
  - Utility
  - Completion rate
  - Violation count
  - Planning time ms
  - Battery and storage use
  - Churn equals changed unfrozen over unfrozen before
  - Explanation coverage equals changed with trace over changed
- Say, diff tells what changed. Trace tells why. Metrics tell if new plan is better and stable.

### Architecture

- React 19 plus TypeScript plus Vite frontend. MapLibre plus deck.gl map, vis-timeline, generated OpenAPI types.
- FastAPI backend, thin routes in `amis/api.py:71-317`.
- MissionSession facade in `amis/session.py:59-836` holds all and is single test seam per ADR-0001.
- WindowProvider protocol with `generate(scenario, requests)` in `amis/windows/protocol.py:15-18`.
- Persistence with Postgres tables for scenarios, satellites, requests, windows, states, plans, actions, events, traces, experiment results. In memory repo for tests. One transaction per save.
- Offline rule. No live TLE fetch in server. Snapshots in `amis/data/elements` plus manifest plus small de421 excerpt with checksum. Refresh by `python -m scripts.fetch_orbital_elements`.
- Say, planner never imports FastAPI, React, Postgres, Skyfield core except provider. That keeps it testable.

### Current status

- Backend 152 passed in local venv Python 3.14.3. Frontend 139 passed per `.doc/status/feature-implementation-status.md`.
- Three examples kept as Examples mode:
  - Cloud replanning demo, `build_canonical_replan_scenario` in `amis/demo.py:206`
  - Battery drop demo
  - Emergency request demo, `build_emergency_replan_fixture` in `amis/demo.py:251`
- New mission flow adds scenario builder, Load Mission, orbital provider, ground track endpoint, validation endpoint, NO_OBSERVATION_WINDOW as honest empty result.

## Exact demo script to speak

- Open frontend at localhost 5173 with backend at 127.0.0.1:8000 running first.
- Click Load demo scenario. Say, one satellite SAT-001, five requests OBS-A to OBS-E.
- Click Generate windows. Point to OBS-B with two bands.
- Click Plan. Read utility and placements. Note OBS-C expired on purpose.
- Click Step 300 sec. Show battery drop and started action frozen.
- Click Inject cloud block on OBS-B WIN-OBS-B-1. Show impact with one invalid.
- Click Replan. Show Plan v2 moves OBS-B from 10:20 to 11:15, same reason code.
- Open Compare. Read diff entry MOVED with WINDOW_INVALIDATED.
- Open Traces. Read sentence aloud.
- Open Metrics. Compare utility, churn, coverage, planning time ms.
- If orbital build is ready, open New Mission, pick Sentinel-2A 40697 near epoch 2026-09-25, set 3 to 5 day horizon, 30 to 45 deg field, show preview counts and ground track, then run same loop.
- Closing line to say, same loop works on fixed offsets and real physics. Only window source changed.

## How to run

- Backend:
  - `cd D:\LearningHub\CollegeProjects\AMP`
  - `.\.venv\Scripts\Activate.ps1`
  - `uvicorn amis.main:app --reload`
- Frontend in second terminal:
  - `cd D:\LearningHub\CollegeProjects\AMP\frontend`
  - `npm install`
  - `npm run dev`
- Offline data note. Backend reads `amis/data`. No fetch while serving. New orbital missions must stay within 14 days of element epoch and inside ephemeris excerpt 2026-09-20 through 2026-10-15.

## Questions internal professor may ask, with short answers

- Why simulator, not real satellite control.
  - Real control needs flight software, safety, radio, license. Goal here is planning logic, visible and repeatable. Control is out of scope in PRD section 6.
- What is novel here versus simple calendar.
  - Windows from physics, resource projection, frozen history, impact split, diff, traces from codes, metrics for stability and explainability.
- Why greedy first, why CP-SAT later.
  - Greedy is deterministic, fast, explainable baseline. CP-SAT gives higher utility with bound and gap. Same protocol lets you compare fairly.
- Why immutable plans and event log replay.
  - Audit and repeat. Same scenario plus same events in order gives same plans. Required by ADR-0002 and SRD determinism rule.
- What is frozen and why it matters.
  - Started actions cannot change. Else you rewrite past. Validation skips frozen, replan carries them.
- How do you pick order in greedy. Is it optimal.
  - Priority, deadline, duration, id. No, not optimal. It is baseline. CP-SAT or exact branch and price would beat it on dense cases.
- What happens on tie in priority.
  - Earlier deadline wins, then shorter duration, then id. Emergency fixture tests this.
- How is utility computed.
  - Sum of priorities of scheduled plus completed, deduplicated. Simple and monotone. Later you can weight by off nadir or sun.
- What is churn and coverage.
  - Churn measures disruption. Coverage measures every change has a reason. Both guide stable replanning research.
- Why cloud block, battery drop, emergency in that order.
  - PRD priority. Cloud tests window logic. Battery tests resource logic. Emergency tests insertion and preemption.
- How does impact differ from replan.
  - Impact is diagnosis on old plan. Replan is new plan. You need both to explain before and after.
- Why reason codes, not LLM text.
  - Codes are deterministic and testable. Text is generated from templates. LLM is banned as planner in PRD, optional later for phrasing only.
- Synthetic versus orbital windows.
  - Synthetic is whole horizon for logic tests. Canonical is fixed offsets for demo story. Orbital is Skyfield VTW with off nadir and sun filter for realism.
- Why 30 deg, why 2 min windows, why 20 to 60 sec durations.
  - 30 deg is Pleiades standard view. At 705 km it allows about 120 sec overhead, less off track. Demo 300 to 600 sec cannot fit, so builder defaults change.
- TLE versus OMM, why store both.
  - OMM JSON is canonical, no catalog ceiling, no 2 digit year. TLE lines kept verbatim for cross check with other tools.
- Why offline snapshots, no live CelesTrak in server.
  - Policy limits, firewall on repeat fetch, determinism, SRD offline rule. Fetch script is developer only with manifest and sha256.
- Epoch age rule 7 day warn, 14 day reject.
  - Follows Skyfield guidance of useful for couple weeks, about 1 km error at epoch then degrades.
- Determinism with Skyfield versions.
  - Pin skyfield and sgp4, store versions in provenance, round edges inward to seconds, test twice generation equals JSON, confirm on Python 3.11 Docker and 3.14 local.
- Single satellite only, why not constellation.
  - Scenario has singular satellite, state has one battery, overlap is global. Multi satellite needs allocation layer and is marked final or later.
- No recharge, no downlink in MVP, is that real.
  - No, simplified and locked. Downlink action reopens it per ADR-0011. Contacts first, then storage release logic.
- Ground stations and elevation mask.
  - Catalogue with lat, lon, 5 to 10 deg mask. Contact when above mask. Same pass search as imaging but low threshold.
- How do you test.
  - 14 SRD cases. Feasible schedule, overlap reject, deadline reject, battery reject, storage reject, cloud invalidates, battery invalidates future, emergency enters pool, frozen preserved, new version, diff correct, traces for all changes, same seed same result, v2 validates.
- What breaks most often.
  - Request id reuse hitting canonical provider, horizon far from epoch, 60 sec grid on 120 sec windows, deadline before start, migration 0001 edited in place so old Postgres volume disagrees with Alembic.
- What is next.
  - Orbital builder and Load Mission, ground track layer, NO_OBSERVATION_WINDOW, then CP-SAT compare, then payload outage interval, min gap for slew, energy from power times duration, storage from rate times duration, then downlink, weather ingest, multi satellite.

## Glossary to keep on one slide

- Scenario is mission definition
- Satellite is single spacecraft
- ObservationRequest is wish with priority and deadline
- RequestPool is wishes considered now, expired stay
- ObservationWindow is chance to image
- Contact window is chance to downlink
- ScheduledAction is wish placed in chance at time
- MissionPlan is versioned set of bookings
- Planner is greedy or CP-SAT, picked by name
- Violation is one action breaks one rule
- MissionState is clock plus resources plus done list
- MissionEvent is controlled disruption
- Frozen is started, cannot change
- Replan is rebuild unfrozen to next version
- Impact is valid versus invalid split
- ReasonCode is fixed why, text is generated
- DecisionTrace links event to change to sentence
- PlanDiff is unchanged, moved, inserted, dropped, completed
- Mission utility is sum priorities done or booked
- Plan churn is share of future changed
- Explanation coverage is share of changes with trace