# AMIS Redesign Context

## Purpose

This document is the authoritative handoff for continuing the AMIS (Adaptive Mission Planning for Earth Observation Satellites) project in a fresh ChatGPT/coding-agent conversation.

Use it to avoid re-opening decisions that are already settled. The next phase is an incremental frontend redesign, followed by a frontend-backend contract audit and only then targeted backend changes if required.

---

## 1. Project

**Repository:** `SumitPatel-HQ/AMP`

AMIS is a software-only mission planning simulator for Earth Observation satellites.

Core research/product loop:

**Mission -> Plan V1 -> Simulate -> Event -> Impact -> Adaptive Replan -> Plan V2 -> Explanation -> Evaluation**

The project is not intended to control a real satellite. The MVP demonstrates planning under constraints, simulation of disruptions, adaptive replanning, explainability, and measurable before/after results.

---

## 2. Current implementation status

The repository has progressed well beyond a prototype skeleton.

### Backend already implemented

The repository contains real implementations for:

- Domain models
  - Scenario
  - Satellite / MissionState
  - ObservationRequest
  - ObservationWindow
  - ScheduledAction
  - MissionPlan
  - MissionEvent
  - Impact
  - DecisionTrace
  - Metrics
  - Plan diff/comparison
- Constraint engine
  - satellite availability
  - window containment
  - deadlines
  - time overlap
  - battery/storage resource feasibility
  - future-plan validation
- Greedy planner
- MissionSession facade
- Simulation clock and resource accounting
- Request expiry
- Event injection
- CLOUD_BLOCK
- BATTERY_DROP
- EMERGENCY_TASK wire event
- Impact analysis
- Adaptive replanning
- Plan comparison/diff
- Decision traces
- Metrics
- Deterministic per-scenario IDs
- FastAPI REST API and schemas
- PostgreSQL persistence/repositories
- Alembic migrations
- Docker / Docker Compose
- Canonical demo
- Extensive backend tests for planner, constraints, resources, cloud impact, battery drop, emergency request, replanning, metrics, traces, diffs, persistence/domain round trips, etc.

### Frontend already implemented

Tickets 11-15 have been implemented, including:

- dashboard shell
- scenario loading
- initial timeline
- mission state
- simulation stepping
- event panel
- replanning
- Plan V1 / Plan V2 presentation
- comparison
- decision trace
- metrics
- map

The problem is no longer absence of frontend features. The problem is **information architecture, hierarchy, interaction design, and visual presentation**.

---

## 3. Current project problems

### A. Backend architecture is not the current primary problem

The backend already represents the AMIS research loop appropriately.

Do **not** rewrite it around any reference repository.

Backend changes should be evidence-driven and postponed until the redesigned frontend reveals concrete API/data-contract limitations.

### B. Frontend exposes implementation modules instead of the mission

The existing UI is effectively:

- Scenario
- State
- Stepping
- Timeline
- Metrics
- Decision Trace
- Map
- Event panel

as separate dashboard cards.

This exposes the software architecture rather than communicating the mission workflow.

The user should perceive:

**Current Mission State -> Current Plan -> Event -> Impact -> Replan -> New Plan -> Why it changed -> Did it improve?**

### C. Weak visual hierarchy

The current interface resembles a generic engineering/admin dashboard:

- many similarly weighted cards
- excessive unused space
- map isolated or oversized
- timeline does not dominate enough
- event injection occupies too much space
- metrics/trace appear disconnected from the plan they describe
- important operational state is not persistently prominent

### D. Components do not feel synchronized

The map, timeline, requests, events, plan comparison and trace should behave as views of the same mission.

Example desired interaction:

**Select OBS-B -> highlight its target on map -> highlight its windows/action on timeline -> show request details -> show related trace.**

Example event interaction:

**Select EVENT-001 -> highlight event time -> affected window/action -> target -> impact -> trace.**

### E. Existing backend capability is not fully visible in the frontend

Do not infer that a backend capability is absent merely because it is not visible in the current UI.

The redesign should first expose existing backend information correctly.

---

## 4. Reference repositories

Three repositories are being used deliberately, each for a different purpose.

### Reference 1 - World Monitor

Repository: `koala73/worldmonitor`

Role in AMIS:

**Primary reference for application shell, workspace layout, visual density, map-centric operations UI and panel treatment.**

Research identified useful areas including:

- application/panel layout concepts
- base panel patterns
- `MapContainer`
- `DeckGLMap`
- map popups/context
- split/grid workspace behavior
- compact operational controls
- top status/navigation treatment
- dense dark visual language
- minimal wasted space

World Monitor itself is a different product/domain. Do not inherit its news/geopolitical data architecture or semantics.

The project is AGPL-licensed. AMIS intends to remain compatible with that licensing direction. If actual source is materially adapted, preserve required notices/provenance and track it in third-party notices.

### Reference 2 - NASA Open MCT

Repository: `nasa/openmct`

Role in AMIS:

**Primary domain-UX reference for mission control, synchronized mission time, timelines, telemetry and planning/operations presentation.**

Research identified relevant concepts/features:

- Time Conductor
- Timeline
- Plan Layout
- Event Timestrip
- telemetry views
- LAD-style operational tables
- display layouts
- synchronized time context
- object selection / inspection concepts

AMIS should learn mission-control interaction concepts from Open MCT.

Do not adopt Open MCT's entire plugin architecture or rewrite AMIS around it.

AMIS's mission timeline remains purpose-built.

### Reference 3 - Satellite Mission Control Dashboard / orbit.ctrl

Repository: `patrickkuei/Satellite-Mission-Control-Dashboard`

Role in AMIS:

**React/TypeScript implementation reference for satellite-oriented operational UI.**

Research found stack/pattern alignment around:

- React
- TypeScript
- Vite
- TanStack Query
- Recharts
- satellite/globe visualization
- telemetry/status presentation
- alerts
- selection/detail UI
- frontend separation of hooks/components/API/state

Use this repository for implementation patterns where useful.

Do not inherit its unrelated AI/backend/domain architecture.

---

## 5. Reference ownership rule

Use this mapping throughout the redesign:

| Source | AMIS learns from it |
| --- | --- |
| World Monitor | Shell, panel system, map workspace, density, visual language |
| NASA Open MCT | Mission time, timeline, mission-control/operations UX |
| Satellite Mission Control Dashboard | React/TS satellite UI implementation patterns |
| AMIS/AMP itself | Domain model, planner, simulator, constraints, events, impact, replanning, explainability, metrics, API and persistence |

The references must never become architectural authorities over AMIS's core domain.

---

## 6. Target AMIS information architecture

The target should communicate a single operational mission workspace rather than a collection of cards.

Conceptual layout:

```text
+-------------------------------------------------------------+
| AMIS | Mission | Time | Status | Step | Event | Replan      |
+-------------+-------------------------------+---------------+
| MISSION     |                               | MISSION STATE |
|             |             MAP               |               |
| Requests    |                               | Battery       |
| Windows     |      Satellite + Targets      | Storage       |
| Events      |                               | Availability  |
| Plans       |                               | Active Event  |
+-------------+-------------------------------+---------------+
|                     MISSION TIMELINE                        |
| windows / actions / mission time / events / plan changes   |
+-------------------------------+-----------------------------+
| PLAN COMPARISON               | IMPACT / DECISION TRACE     |
+-------------------------------+-----------------------------+
| Utility | Completion | Churn | Violations | Resources      |
+-------------------------------------------------------------+
```

This is conceptual, not a requirement to reproduce exact dimensions.

---

## 7. Frontend principles

1. The **mission**, not backend modules, is the organizing concept.
2. Map and timeline are primary operational surfaces.
3. Mission state/telemetry remains visible.
4. Event injection is a compact control/dialog, not a giant dashboard section.
5. Plan comparison belongs close to timeline/replanning.
6. Decision traces explain visible changes rather than existing as an isolated log.
7. Metrics answer: **Did adaptive replanning help?**
8. Reduce wasted vertical space.
9. Prefer dense, operational presentation over large generic cards.
10. Existing backend behavior must remain functional during frontend restructuring.
11. No polling. Refetch after user actions.
12. Selection/highlighting should eventually synchronize across map, timeline, requests, events, comparison and trace.

---

## 8. Existing frontend stack

Keep the selected stack unless implementation evidence requires otherwise:

- Vite
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- Recharts for conventional metrics/charts
- React-Leaflet currently used for map unless a later map-specific decision justifies change
- Custom SVG for the AMIS mission timeline
- generated TypeScript API types via `openapi-typescript`
- FastAPI backend
- PostgreSQL + SQLAlchemy
- Docker Compose

Do not introduce Next.js. AMIS is an interactive mission-control SPA with an existing FastAPI backend; SSR/SEO/server actions are not required.

---

## 9. Locked backend/domain decisions

Do not casually reopen these.

### Resource projection
Planner performs chronological forward projection.

- Battery decreases by action energy.
- Storage increases by action data.
- No battery recharge in MVP.
- No downlink in MVP.
- Simulation mutates actual state; planning projection is temporary.

### MissionSession
Rehydrate per HTTP request from repositories. MissionSession remains the main application facade/test seam.

### In-flight actions
If an event occurs while an action is in flight, that action is frozen/committed and completes with full resource cost.

### Replanning
Full rebuild of the unfrozen future with stability preference:

1. preserve exact previous placement if still feasible
2. otherwise prefer another feasible placement in previous window
3. otherwise earliest feasible alternative

Frozen history/committed actions are retained.

### Metrics
Metrics are self-describing and include request-pool identity/size.

Utility deduplicates requests by request ID.

If denominator is empty:

- plan churn = null / N/A
- explanation coverage = null / N/A

Expired requests remain in the request pool.

### Terminology
Canonical terms:

- ObservationRequest
- ObservationWindow
- ScheduledAction
- MissionPlan
- MissionEvent

Avoid generic noun `task` except the compatibility wire enum `EMERGENCY_TASK`.

Avoid using noun `schedule` where `MissionPlan` is intended.

### Randomness
No `AMIS_RANDOM_SEED` in MVP. Core domain behavior should be deterministic for fixed inputs.

### Impact
Impact classification is valid/invalid only.

Impact is computed when an event is injected and persisted against:

- scenario
- event
- evaluated plan

### Emergency requests
Scenario remains immutable.

Emergency requests are introduced through the event log. Event payload carries explicit observation windows in MVP.

Replay = pristine scenario + events in order.

### IDs
Deterministic per-scenario sequential IDs, e.g.:

- PLAN-001
- ACT-002
- EVENT/EVT-001
- IMPACT-001
- TRACE-007

Counters must survive rehydration/restart through persisted state reconstruction.

### Request expiry
Simulation marks a request EXPIRED when its deadline passes.

Expired requests are excluded from future replanning but remain part of mission evaluation.

### Replan without event
Allowed. Produces a new immutable plan version; expected domain-equivalent plan and zero churn.

### Future feasibility after battery drop
Frozen history/committed actions are not revalidated as future feasibility.

If an in-flight committed action becomes unaffordable after a battery-drop event, it still completes and battery floors at zero. The future suffix is validated from the resulting resource state.

### Planner infeasibility
No global `PLAN_INFEASIBLE` result.

Planner always returns a MissionPlan, potentially empty, with `unscheduled_requests` and per-request reason codes.

### Unscheduled requests
Displayed separately from the timeline with request ID, priority and reason.

### Demo entry point
Canonical demo command:

`python -m amis.demo`

### Concurrency
Replan uses optimistic concurrency with `expected_parent_plan_id`.

Stale parent -> HTTP 409 `PLAN_VERSION_CONFLICT`.

### Demo behavior
Canonical cloud demo should demonstrate a meaningful replan such as:

- OBS-B scheduled in Plan V1
- cloud invalidates its first window
- OBS-B moves to an alternate valid window in Plan V2
- unrelated feasible placements remain stable
- reason identifies window invalidation

Battery demo should make one lower-priority future request unscheduled while preserving higher-priority work.

Emergency demo should schedule the emergency request and visibly displace a competing lower-priority request.

### Decision traces
`plan_id` means the plan in force when the trace was recorded.

Expiry traces do not count toward explanation-coverage numerator for plan comparison.

### API lifecycle
Expected lifecycle:

Scenario -> windows -> initial plan -> simulation step -> event -> impact -> replan.

Invalid lifecycle operations return `SIMULATION_STATE_ERROR`.

### Simulation reset/end
Reset is a full rewind to pristine scenario state and clears run-derived plans/events/traces/impacts.

Stepping beyond mission end clamps to mission end, marks complete, and rejects further steps.

### Priority
Priority scale is 1-5.

Emergency can use priority 5 and win via deterministic planner tie-breaking (priority desc -> deadline asc -> duration -> ID).

Use `DISPLACED_BY_COMPETING_REQUEST`, not misleading task terminology.

### Observation windows in UI
Event controls should use Request dropdown -> Window dropdown.

Timeline should eventually show observation windows as subtle bands behind scheduled actions when practical.

### PostgreSQL/Compose
Frontend + backend compose first; PostgreSQL is part of actual persistence rather than an unused decorative service.

### Satellite availability
Keep the constraint and `SATELLITE_UNAVAILABLE` reason even if the canonical MVP fixture rarely triggers it.

### ADRs
Only three ADRs were considered necessary initially:

1. MissionSession as Core Test Seam
2. Immutable Scenario + Event Log as Replay Unit
3. Frozen Actions Excluded from Future-Plan Feasibility Validation

---

## 10. Frontend/backend boundary

Do not make React components depend on database-shaped data.

Desired flow:

```text
PostgreSQL
   ->
Repositories
   ->
AMIS Domain
   ->
FastAPI DTOs
   ->
OpenAPI
   ->
Generated TypeScript types
   ->
Frontend query/data layer
   ->
View models
   ->
UI components
```

Frontend-specific projections can include:

- TimelineRow
- TimelineMarker
- ObservationWindowBand
- MapTarget
- TelemetryItem
- PlanDiffItem
- TraceItem

These are presentation models, not new backend domain entities.

---

## 11. Redesign prompt sequence — 7 implementation prompts

The redesign is intentionally split into **7 implementation prompts**, not 11. The merged stages are chosen by coupling: work that shares the same data, interaction model, and screen region is implemented together; high-risk visualization surfaces remain isolated so they can be reviewed before the next stage.

### Execution rule

Run **one prompt at a time**. After each prompt:

1. the coding agent must inspect the current implementation and named reference repository areas before editing;
2. implement only that prompt's scope;
3. run frontend build/typecheck and relevant tests;
4. report changed files, reused/adapted reference patterns, assumptions, and any blocked requirement;
5. capture/review the resulting UI before writing the next prompt.

Do not ask the coding agent to implement all seven stages in one run. Do not silently continue into the next stage.

### Prompt 1 — Mission-Control Shell + Mission State + Requests/Windows

**Primary reference:** World Monitor for shell, density, panel hierarchy, compact controls.  
**Secondary reference:** Open MCT for operational information hierarchy.

These areas are combined because mission state, requests and windows define the information architecture around the central workspace. Building them separately would repeatedly restructure the same shell.

**Before editing:**
- inspect the existing AMP frontend entry point, layout, routes, query hooks, API client/generated types, existing state/request/window components, and responsive CSS/Tailwind setup;
- inspect the relevant World Monitor shell/panel/layout implementation rather than copying screenshots;
- inspect Open MCT only for mission-control hierarchy concepts;
- preserve current backend/API behavior.

**Implement:**
- replace the generic equal-weight card dashboard with one cohesive mission-control workspace;
- create a compact top command/status bar containing mission identity, current mission time/status, and existing Step/Event/Replan actions where those actions already exist;
- create a compact mission/navigation area for Requests, Windows, Events and Plans rather than separate oversized cards;
- create a persistent mission-state/telemetry area for battery, storage, satellite availability and relevant current state;
- reserve the center as the primary operational workspace for the map;
- reserve a dedicated full-width or dominant timeline region directly associated with the operational workspace;
- reserve lower analysis space for comparison, impact/trace and metrics that later prompts will improve;
- expose existing request/window data in a compact operational list, including statuses already available from the backend;
- establish a shared frontend selection model for selected request/window/event/plan if one does not already exist, but do not implement deep cross-view synchronization yet;
- keep existing working components mounted/repositioned where practical instead of rewriting their internals.

**Do not:**
- redesign the backend;
- rewrite map internals;
- rewrite the custom timeline visualization;
- invent data;
- add new domain concepts;
- spend the stage on animation or cosmetic polish;
- turn every region back into a large rounded card.

**Acceptance criteria:**
- on first load, the user can identify mission, current time/status, satellite resource state, requests, main spatial workspace and timeline without scrolling through unrelated cards;
- Step/Event/Replan remain reachable and functional;
- existing scenario load and query behavior still works;
- layout remains usable at the project's target desktop sizes;
- no backend change is required solely to achieve the shell;
- frontend build/typecheck passes.

### Prompt 2 — Mission Map + Spatial Interaction

**Primary references:** World Monitor map workspace + Satellite Mission Control Dashboard satellite-oriented UI patterns.

Keep this prompt separate because the map is a specialized operational visualization and should be reviewed independently before timeline work.

**Before editing:** inspect the current AMIS map implementation and data flow first. Then inspect actual map-related reference code/components. Do not switch mapping libraries merely because a reference uses another one.

**Implement:**
- turn the map from an isolated/oversized world map into the central spatial mission surface established in Prompt 1;
- choose a mission-relevant initial viewport based on current scenario targets/satellite context rather than showing large irrelevant geography;
- clearly distinguish observation targets, selected target/request, satellite context, and event-affected target/window where the backend supplies the relationship;
- provide compact contextual information on selection/hover without obscuring the map;
- connect map selection to the shared selection model from Prompt 1;
- selecting a target/request should update the shared selected request/target state so later timeline/trace stages can react to it;
- preserve existing real backend data and current React Query/API flow.

**Do not:**
- add fake orbital tracks or telemetry;
- migrate from React-Leaflet unless the current library demonstrably blocks a required interaction;
- copy World Monitor's geopolitical layers;
- build timeline behavior in this stage.

**Acceptance criteria:** the map immediately communicates where mission targets are, what is selected, and what spatial item is affected by the current event when such data exists; it occupies useful space without dominating the entire page; build/typecheck passes.

### Prompt 3 — Mission Timeline + Mission Time

**Primary reference:** NASA Open MCT Time Conductor, Timeline, Plan Layout and Event Timestrip concepts.

This remains its own prompt because the timeline is the most domain-specific and interaction-heavy visualization in AMIS.

**Before editing:** inspect the current AMIS custom SVG timeline, current plan/window/event data, and Open MCT's relevant time/timeline concepts. Keep AMIS terminology and backend semantics authoritative.

**Implement:**
- make the custom SVG timeline a first-class mission-control surface rather than a simple action strip;
- use one clear mission-time axis derived from scenario start/end/current time;
- render observation windows as subtle background bands associated with requests;
- render scheduled actions distinctly from windows;
- render the current mission-time marker;
- render event markers at their mission times;
- visually distinguish completed/frozen, future, invalidated/impacted and selected items using data that actually exists;
- prepare the timeline to display Plan V1/Plan V2 change states without prematurely implementing the full comparison UI;
- synchronize request/window selection with the shared selection model so map/list/timeline selection can refer to the same mission object;
- keep labels, density and zoom/readability appropriate for 5–10 request MVP scenarios.

**Do not:**
- replace the purpose-built SVG timeline with a generic chart library;
- fabricate invalidation/change states;
- create a second independent mission clock;
- implement plan comparison logic in the browser if the backend already supplies it.

**Acceptance criteria:** a reviewer can visually answer: what could have been observed, what was planned, what has already happened, where mission time is now, and when a disruption occurred. Selection between request list/map/timeline uses the same selected entity state.

### Prompt 4 — Event -> Impact -> Replan Operational Workflow

**References:** AMIS backend/domain is authoritative; Open MCT contributes operational interaction principles; World Monitor contributes compact control presentation.

Keep the complete adaptive loop together. Splitting event injection, impact and replanning would leave unusable intermediate states and duplicate UI work.

**Implement the user-visible sequence:**

`Choose event -> configure valid payload -> inject -> see event in mission context -> inspect persisted impact -> Replan -> see Plan V2 become available`

Requirements:
- make event injection a compact contextual control/dialog/drawer, not a large permanent card;
- support existing CLOUD_BLOCK, BATTERY_DROP and EMERGENCY_TASK flows using the real API contracts;
- for cloud blocking, use Request -> Window selection rather than raw window-ID typing where the existing API permits it;
- after injection, refetch relevant state explicitly; no polling;
- show the event on the timeline and spatially where meaningful;
- surface persisted impact: evaluated plan, invalid action(s), violation/reason information;
- clearly separate **impact** (what became invalid) from **plan diff** (what changed after replanning);
- enable Replan only when valid for the current lifecycle;
- send `expected_parent_plan_id`; handle `PLAN_VERSION_CONFLICT` visibly rather than hiding it;
- after successful replan, expose the new immutable plan version without discarding Plan V1 context;
- preserve lifecycle errors from the backend and present them intelligibly.

**Do not:**
- reimplement impact analysis in React;
- mutate scenario data to represent emergency requests;
- use polling;
- hide backend reason codes behind invented explanations.

**Acceptance criteria:** a reviewer can execute the adaptive-planning loop from the UI and understand the disruption before seeing the replan result. Cloud, battery and emergency flows remain grounded in backend behavior.

### Prompt 5 — Plan Comparison + Decision Trace / Explainability

**Primary source:** AMIS plan-diff and DecisionTrace backend data.  
**Reference:** Open MCT for inspection/detail interaction patterns.

These are combined because they answer one question together: **What changed, and why did AMIS change it?** Implementing them separately would create duplicate selection and layout work.

**Implement:**
- create a focused Plan V1 <-> Plan V2 comparison surface associated with the timeline rather than an isolated generic card;
- represent backend diff statuses such as UNCHANGED, MOVED, INSERTED, DROPPED and COMPLETED exactly according to available API/domain data;
- show old/new placement details where relevant;
- pair each changed request/action with its actual DecisionTrace/reason data when available;
- selecting a diff row should highlight the corresponding timeline item and, when applicable, map target/request;
- selecting a trace should highlight the mission object/change it explains;
- make reason codes readable with concise labels, but preserve the canonical code and do not invent causal explanations;
- distinguish planning/replanning traces from expiry traces where relevant;
- keep unchanged items visually quieter so changed items dominate analysis.

**Do not:**
- calculate an alternative diff client-side when backend comparison exists;
- use LLM-generated explanations;
- imply a trace explains a change if the backend does not link/support it;
- hide dropped/unscheduled requests just because they have no timeline rectangle.

**Acceptance criteria:** after a replan, a reviewer can select a changed request and immediately determine its previous state, new state, change classification and backend-supported reason.

### Prompt 6 — Mission Evaluation Metrics + Frontend/Backend Contract Audit + Proven Fixes

**Primary source:** AMIS metrics/domain/API.

This prompt intentionally combines metrics with the contract audit because, by this point, every major user workflow exists. The agent can now identify actual API gaps from implementation evidence rather than speculating. Backend changes are allowed here only when the audit proves they are needed.

**Part A - Metrics UX:**
- present utility, completion, violations, resource utilization, plan churn, explanation coverage and request-pool context compactly;
- associate metrics with the exact plan/version they describe;
- make before/after comparison understandable where both plans are available;
- respect `null` as N/A for empty denominators; never render N/A as 0%;
- visibly flag when compared metrics use different request pools;
- avoid decorative charts when a compact value/delta/status communicates the metric better;
- use Recharts only where a real chart adds information.

**Part B - Contract audit:**
For each redesigned surface/workflow, produce an explicit matrix:

`UI requirement -> current frontend source -> API endpoint/DTO -> domain object -> persistence/source -> status (supported / awkward / missing)`

Audit at least:
- mission header/state;
- requests/windows;
- map;
- timeline;
- events;
- persisted impact;
- replanning;
- plan comparison;
- decision traces;
- metrics.

**Part C - Targeted fixes:**
- fix only gaps demonstrated by the matrix;
- prefer a small read endpoint/DTO/projection over changing planner/domain behavior;
- keep MissionSession as facade;
- preserve scenario immutability/event-log semantics;
- preserve deterministic domain behavior;
- update generated OpenAPI TypeScript types after API changes;
- add/update backend and frontend tests for every contract change.

**Do not:**
- perform a general backend cleanup;
- replace the planner/replanner because the UI would prefer a different shape;
- add speculative APIs for future features;
- introduce database-shaped DTOs into React.

**Acceptance criteria:** metrics correctly describe specific plans; the audit is written down; every backend change maps to a demonstrated UI requirement; no unexplained architectural rewrite occurs; all relevant backend tests and frontend build/typecheck pass.

### Prompt 7 — Cross-Surface Integration + UX/Visual Polish + Cleanup

**References:** use all three reference projects only for the areas assigned to them. AMIS remains authoritative.

This is not a redesign-from-scratch prompt. It is the integration pass after all primary workflows exist.

**Implement:**
- finish synchronized selection across requests/windows, map, timeline, events, plan comparison and traces;
- make hover/focus/highlight states consistent;
- ensure selected objects remain understandable when moving between panels;
- refine loading, empty, error, stale/conflict and completed-mission states;
- improve keyboard/focus behavior for primary controls where practical;
- refine responsive behavior for target desktop/laptop widths without sacrificing operational density;
- normalize spacing, typography, borders, panel chrome and status semantics into one coherent visual system;
- reduce decorative card styling and wasted whitespace;
- ensure the map and timeline remain the dominant operational surfaces;
- remove obsolete components/styles left by the old dashboard only after confirming they are unused;
- perform reasonable render/performance cleanup (avoid unnecessary refetch loops/re-renders; still no polling);
- verify the canonical cloud, battery and emergency workflows end-to-end through the UI.

**Final verification:**
- frontend build/typecheck passes;
- relevant frontend tests pass;
- backend regression tests pass if Prompt 6 changed APIs;
- no console-breaking errors in the canonical flow;
- all user actions use real backend data;
- final UI visually communicates the research story: **Plan -> Disruption -> Impact -> Adaptive Replan -> Explanation -> Evaluation**.

### Why the original 11 prompts were merged

The previous sequence was reduced as follows:

- old **Shell** + **Mission State/Requests/Windows** -> new **Prompt 1**, because they share the same shell and information hierarchy;
- old **Mission Map** -> new **Prompt 2**, unchanged in responsibility;
- old **Mission Timeline** -> new **Prompt 3**, unchanged in responsibility;
- old **Event/Impact/Replan** -> new **Prompt 4**, unchanged as one end-to-end adaptive workflow;
- old **Plan Comparison** + **Decision Trace** -> new **Prompt 5**, because change and explanation must share selection/context;
- old **Metrics** + **Frontend/Backend Contract Audit** + **Targeted Backend/API Improvements** -> new **Prompt 6**, because backend changes should follow observed UI/data needs, not precede them;
- old **Final Integration/Polish** -> new **Prompt 7**.

Map and Timeline are deliberately **not** merged: both are complex custom visualization surfaces and should have separate implementation/review checkpoints. Event/Replan and Comparison/Trace are also kept as separate prompts so the operational workflow can be verified before its analytical/explainability layer is refined.

---

## 12. Rules for future coding-agent prompts

Every prompt should explicitly say:

- inspect current implementation before editing
- preserve working functionality
- do not rewrite unrelated areas
- use reference repos intentionally, not blindly
- name specific reference files/components only after actually inspecting them
- preserve AMIS domain terminology
- keep backend authoritative
- do not fabricate API data in frontend
- do not add mock behavior where a real endpoint already exists
- avoid giant rewrites
- keep scope limited to the current prompt
- report changed files and important decisions after implementation
- run relevant tests/build/typecheck
- do not proceed to the next redesign stage automatically

---

## 13. Licensing/provenance

If reference code is materially copied/adapted:

- verify that repository/file's license first
- preserve required copyright/license notices
- maintain `THIRD_PARTY_NOTICES.md`
- annotate materially adapted files where appropriate
- do not assume all GitHub code has the same license
- AMIS intends to retain an AGPL-compatible/open-source direction for World Monitor-derived work

Conceptual inspiration alone should still be documented where useful, but does not mean code was copied.

---

## 14. Immediate next action

Start with **Prompt 1 only: Frontend Shell + Information Architecture**.

Do not begin with backend redesign.

Do not implement Prompt 2 until Prompt 1 has been reviewed.

The first prompt should instruct the coding agent to inspect the current AMP frontend and the relevant World Monitor shell/layout implementation before making changes.

The objective of Prompt 1 is not visual polish. It is to establish the correct AMIS mission-control hierarchy so every subsequent map, timeline, event, comparison, trace and metrics improvement has the correct place to live.
