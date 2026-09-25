# AMIS FULL-SYSTEM INDEPENDENT IMPLEMENTATION + REFERENCE AUDIT

You are the **independent auditor** for the AMIS project.

The AMIS redesign has already been implemented.

Your task is to inspect the CURRENT implementation and determine whether the system is actually correct across:

* backend/domain
* planning and replanning
* simulation/events/impact
* persistence
* FastAPI/API contracts
* generated frontend contracts
* frontend architecture
* map/timeline
* end-to-end workflows
* cross-surface synchronization
* tests/runtime
* deliberate use of reference repositories

This is NOT a frontend-only review.

This is NOT a redesign task.

This is NOT an implementation task.

---

# HARD RULE — AUDIT ONLY

**DO NOT MODIFY CODE.**

Do not:

* fix issues
* refactor
* create components
* rewrite architecture
* change schemas
* change dependencies
* change tests
* commit changes

You MAY:

* inspect code
* inspect Git history
* inspect reference repositories
* run tests
* run builds/typechecks
* inspect migrations
* inspect generated OpenAPI/types
* trace execution paths
* perform other non-destructive verification

Another implementation agent will independently verify and fix proven issues later.

Be aggressive about **finding** problems.

Be conservative about **declaring** problems.

Every defect must have concrete repository evidence.

---

# 1. PROJECT + REQUIREMENT AUTHORITY

## Project

AMIS / AMP:

https://github.com/SumitPatel-HQ/AMP

AMIS = Adaptive Mission Planning for Earth Observation Satellites.

Core research/product loop:

`Mission → Plan V1 → Simulate → Event → Impact → Adaptive Replan → Plan V2 → Explanation → Evaluation`

The finished system should both:

1. execute this loop correctly in the backend;
2. expose the loop clearly through the frontend.

## Read these first

* `AMIS_REDESIGN_CONTEXT(2).md`
* `AMIS_PRD.md`
* `AMIS_SRD.md`
* `AMIS_Implementation_Guide.md`

### Authority rule

`AMIS_REDESIGN_CONTEXT(2).md` is the highest authority where later locked decisions supersede older documents.

Use:

* PRD for product requirements;
* SRD for technical intent;
* Implementation Guide for original implementation guidance.

Do NOT report current behavior as defective merely because an older document contains behavior intentionally superseded later.

Mark those cases:

`SUPERSEDED — NOT A DEFECT`

Record the AMIS branch/commit and reference repository commits you inspect so findings are reproducible.

---

# 2. REFERENCE REPOSITORIES

Use these exact repositories.

## World Monitor

https://github.com/koala73/worldmonitor

Primary AMIS reference for:

* application shell
* panel/workspace composition
* information density
* compact controls
* map-centric layout
* top status/navigation treatment
* split/grid behavior
* efficient use of space
* operational visual language

Inspect actual source implementation, not screenshots alone.

Do NOT inherit:

* geopolitical/news domain
* World Monitor backend/data architecture
* news/AI pipelines
* unrelated map layers
* unrelated infrastructure

---

## NASA Open MCT

https://github.com/nasa/openmct

Primary AMIS reference for:

* mission-control UX
* synchronized mission time
* Time Conductor concepts
* timeline semantics
* Timeline
* Plan Layout
* Event Timestrip
* selection/inspection
* operational information hierarchy
* temporal navigation
* planning/operations presentation

Inspect actual source.

AMIS uses its own domain and `vis-timeline`.

Do NOT expect Open MCT's rendering implementation or plugin architecture to be copied.

Evaluate transferred interaction concepts and mission-control semantics.

---

## orbit.ctrl / Satellite Mission Control Dashboard

https://github.com/patrickkuei/Satellite-Mission-Control-Dashboard

Implementation reference for:

* React
* TypeScript
* Vite
* TanStack Query
* satellite-oriented operational UI
* telemetry/status presentation
* selection/detail behavior
* map/spatial interaction
* API/hooks/state/component separation
* Recharts patterns where useful

Do NOT treat its:

* LLM agent
* Gemini/Groq/Anthropic
* MCP server
* WebSockets
* anomaly detection
* live orbital simulation
* 3D globe
* backend architecture

as AMIS requirements.

---

## NASA AMMOS OpenMCT-MCWS — supplementary only

https://github.com/NASA-AMMOS/openmct-mcws

Use selectively for understanding:

* provider/service boundaries
* persistence integration
* adapters
* configuration boundaries
* mission-control UI ↔ external service separation

This repository is NOT an AMIS architecture authority.

Do NOT require:

* MCWS
* Open MCT plugins
* different persistence architecture
* replacement of MissionSession/FastAPI/PostgreSQL

Use it only as supporting evidence.

---

# 3. COMPLETE ARCHITECTURE AUDIT

Trace the real implementation across:

`PostgreSQL`
→ `Repositories`
→ `AMIS Domain`
→ `MissionSession / Application Layer`
→ `FastAPI`
→ `DTOs`
→ `OpenAPI`
→ `Generated TypeScript Types`
→ `Frontend API / Query Layer`
→ `View Models / Shared State`
→ `React UI`

Determine whether responsibilities are correctly separated.

Search for evidence of:

* ORM models leaking into planner/domain logic
* scheduling logic inside FastAPI routes
* planning/replanning logic inside React
* frontend-authoritative impact calculation
* frontend-authoritative plan diff calculation
* persistence-shaped DTOs leaking into UI
* duplicated business rules
* React components bypassing intended data layers
* stale/manual API interfaces
* excessive unsafe casts / `any`
* unnecessary abstractions

Do not flag architectural differences based purely on personal preference.

---

# 4. CORE DOMAIN + PLANNING AUDIT

Inspect:

* Scenario
* Satellite
* MissionState
* ObservationRequest
* ObservationWindow
* ScheduledAction
* MissionPlan
* MissionEvent
* Impact
* DecisionTrace
* Metrics
* plan comparison/diff

Verify domain relationships and invariants.

## Terminology

Canonical terminology includes:

* `ObservationRequest`
* `ObservationWindow`
* `ScheduledAction`
* `MissionPlan`
* `MissionEvent`

Do not replace these broadly with generic `task` / `schedule`.

`EMERGENCY_TASK` may remain as the compatibility wire event name.

Only flag terminology where it creates real ambiguity or contract problems.

## Constraints

Verify actual execution of:

* satellite availability
* observation-window containment
* deadline
* overlap
* battery
* storage
* chronological resource feasibility
* future-plan validation

Expected resource semantics:

* battery decreases with action energy;
* storage increases with action data;
* no battery recharge in MVP;
* no downlink in MVP;
* planning projection is temporary;
* simulation changes actual mission state.

Verify these constraints are actually invoked by planner/replanner rather than merely existing as unused helpers.

## Planner

Verify:

* deterministic ordering
* priority descending
* deadline ascending
* duration tie-breaking
* request-ID tie-breaking
* observation-window selection
* overlap prevention
* resource feasibility
* deadlines
* satellite availability
* unscheduled requests
* reason codes

Locked behavior:

The planner returns a `MissionPlan`, potentially empty, with unscheduled requests/reasons.

Do not incorrectly enforce an older global `PLAN_INFEASIBLE` model.

---

# 5. APPLICATION LAYER + PERSISTENCE AUDIT

Inspect `MissionSession` and persistence together.

Verify MissionSession remains the main:

* application facade
* orchestration layer
* test seam

Check repository-backed reconstruction/rehydration.

Verify sufficient information survives for:

* mission state
* plans/versions
* events
* impacts
* traces
* metrics
* deterministic IDs
* replay

Inspect:

* SQLAlchemy models
* repositories
* migrations
* actual PostgreSQL usage
* persistence ↔ domain conversion

Verify relevant persisted data such as:

* scenario
* requests
* windows
* mission state
* plans
* actions
* events
* impacts
* traces
* metrics where designed

Do not conclude persistence works merely because tables/models exist.

Trace actual reads/writes and reconstruction paths.

Check that ORM/database objects do not become planner/domain models directly.

---

# 6. SIMULATION + EVENT + IMPACT AUDIT

## Simulation

Verify:

* initialization
* mission time
* stepping
* resource accounting
* action start/completion
* frozen/completed history
* request expiry
* mission completion
* reset

### Expiry

After a deadline:

* request becomes `EXPIRED`;
* remains in evaluation/request pool;
* is excluded from future replanning.

### Mission end

Stepping beyond mission end should:

* clamp to mission end;
* mark complete;
* reject further stepping.

### Reset

Reset should return to pristine scenario state and clear run-derived:

* plans
* events
* impacts
* traces

Verify persistence behavior too.

---

## CLOUD_BLOCK

Trace:

event
→ payload validation
→ persistence
→ request/window relationship
→ impact
→ affected/invalid action
→ replanning input
→ frontend representation

---

## BATTERY_DROP

Trace:

event
→ state mutation
→ impact
→ in-flight action behavior
→ resource state
→ future feasibility
→ replanning

Locked behavior:

An in-flight/committed action completes with full resource cost.

If necessary:

* battery floors at zero;
* frozen history is not revalidated as future feasibility;
* only the future suffix is validated from resulting state.

---

## EMERGENCY_TASK

Verify:

* original Scenario remains immutable;
* emergency request enters through event log;
* required windows are carried through event data;
* replay can reconstruct from pristine Scenario + ordered events;
* request enters remaining planning problem correctly.

---

## Impact

Verify impact is computed and persisted against:

* scenario
* event
* evaluated plan

Use current locked impact semantics.

Frontend must display backend-authoritative impact rather than recreate it independently.

---

# 7. ADAPTIVE REPLANNING + VERSIONING + EXPLAINABILITY AUDIT

Verify:

* completed/past actions remain frozen
* committed/in-flight actions remain frozen
* Plan V1 remains immutable
* future work is rebuilt correctly
* Plan Vn+1 is created
* parent plan relationship is correct

## Stability preference

Verify the replanner prefers:

1. exact previous placement if still feasible;
2. otherwise another feasible placement in the previous window;
3. otherwise earliest feasible alternative.

Unrelated feasible work should remain stable where practical.

## Replan without event

Verify it is allowed.

Expected:

* new immutable plan version;
* domain-equivalent result when nothing changed;
* zero churn where appropriate.

## Optimistic concurrency

Verify use of:

`expected_parent_plan_id`

Stale parent should produce:

HTTP `409`

with:

`PLAN_VERSION_CONFLICT`

Verify frontend handles the conflict visibly.

## Plan diff

Backend should authoritatively classify:

* `UNCHANGED`
* `MOVED`
* `INSERTED`
* `DROPPED`
* `COMPLETED`

Verify:

* stable identity matching
* old/new placement
* dropped/unscheduled representation
* completed history
* reason relationships

Frontend must not implement a competing diff algorithm.

## Decision Trace

Trace:

decision
→ reason code
→ DecisionTrace
→ persistence
→ API
→ frontend
→ UI

Verify:

* canonical reason codes remain authoritative;
* readable labels preserve meaning;
* no invented/LLM causal reasoning is presented as backend truth;
* traces link to the correct changes;
* `plan_id` semantics match the locked definition;
* expiry traces do not incorrectly inflate comparison explanation coverage.

---

# 8. METRICS AUDIT

Verify implementation and semantics of:

* utility
* completion
* violations
* battery/storage utilization
* planning/replanning time
* plan churn
* explanation coverage
* request-pool identity
* request-pool size

Check specifically:

* utility deduplicates request IDs;
* empty plan-churn denominator → `null/N/A`;
* empty explanation-coverage denominator → `null/N/A`;
* frontend does not render N/A as `0%`;
* metrics correspond to the correct plan/version;
* incompatible request pools are detected/surfaced when comparing.

Trace calculations from backend to UI.

Also verify deterministic domain ID reconstruction where relevant:

* PLAN
* ACT
* EVENT/EVT
* IMPACT
* TRACE

Counters should survive rehydration/reconstruction where required.

---

# 9. API + FRONTEND CONTRACT AUDIT

Inspect:

* FastAPI routes
* Pydantic DTOs
* OpenAPI
* generated TypeScript types
* API client
* TanStack Query hooks
* adapters/view models
* shared frontend state

Trace major workflows as:

`Frontend action`
→ `API/query layer`
→ `Endpoint`
→ `DTO`
→ `MissionSession`
→ `Domain`
→ `Repository`
→ `Response DTO`
→ `Generated TS`
→ `View model`
→ `UI`

Audit lifecycle:

Scenario
→ Windows
→ Plan V1
→ Simulation
→ Event
→ Impact
→ Replan
→ Plan V2
→ Comparison
→ Traces
→ Metrics

Verify errors including:

* `SIMULATION_STATE_ERROR`
* `PLAN_VERSION_CONFLICT`
* invalid events
* missing resources
* invalid lifecycle operations

Identify evidence of:

* stale generated types
* duplicated manual backend interfaces
* unsafe casts / `any`
* frontend assumptions absent from schema
* unnecessary frontend workarounds
* unused/missing/awkward endpoints
* backend logic placed inside route functions unnecessarily

Frontend-specific presentation models are acceptable.

Do not mistake view models for domain duplication.

---

# 10. OPERATIONAL UI AUDIT

Evaluate the final UI as one operational mission workspace.

The interface should communicate approximately:

`Current Mission State`
→ `Current Plan`
→ `Event`
→ `Impact`
→ `Replan`
→ `New Plan`
→ `Why it changed`
→ `Did it improve?`

Verify:

* map and timeline are dominant operational surfaces;
* mission state remains visible;
* requests/windows/events/plans are compact;
* event controls are operational rather than oversized dashboard cards;
* comparison/trace/metrics remain connected to mission context;
* hierarchy is clear;
* wasted space is controlled.

Avoid purely subjective visual criticism.

---

## Map

Verify:

* scenario-relevant viewport;
* real targets;
* request/target selection;
* selected state;
* event-affected context;
* useful contextual details;
* shared selection;
* only real backend relationships;
* no fake telemetry;
* no fake orbital tracks.

Compare selectively with World Monitor and orbit.ctrl.

---

## Timeline + Mission Time

Verify:

* `vis-timeline` is actually used;
* one authoritative mission clock;
* scenario start/end/current time;
* ObservationRequest rows/groups;
* ObservationWindow background ranges;
* ScheduledAction foreground ranges;
* MissionEvent markers;
* current-time marker;
* completed/frozen/future states;
* impacted state where supported;
* selection synchronization;
* usable zoom/density;
* AMIS visual integration.

Use Open MCT as a semantic/interaction reference, not a rendering requirement.

---

# 11. FRONTEND WORKFLOW + CROSS-SURFACE INTEGRATION AUDIT

Verify the user can execute:

Choose Event
→ Configure
→ Inject
→ Understand Event
→ Inspect Impact
→ Replan
→ Retain Plan V1
→ See Plan V2
→ Compare
→ Understand Why
→ Evaluate Metrics

Check:

* all three event types;
* Request → Window selection for cloud blocking where appropriate;
* explicit refetch/invalidation after mutations;
* no backend polling;
* persisted impact;
* impact vs plan-diff distinction;
* lifecycle-aware controls;
* conflict handling.

## Cross-surface identity

The following should behave as views of one mission:

`Requests`
↔ `Windows`
↔ `Map`
↔ `Timeline`
↔ `Events`
↔ `Impact`
↔ `Plan Comparison`
↔ `Decision Trace`
↔ `Metrics`

Use `OBS-B` as a representative case.

Check whether applicable identity/context remains coherent across:

* request list
* windows
* target
* timeline action
* current plan
* event/impact
* comparison
* trace

Determine whether shared state is coherent or duplicated/brittle.

## Unscheduled requests

Verify unscheduled requests remain visible separately with useful information such as:

* request ID
* priority
* reason

They must not disappear merely because they have no timeline rectangle.

---

# 12. CANONICAL END-TO-END WORKFLOWS

This is a HIGH-PRIORITY audit area.

Do not only inspect individual modules.

Verify actual complete behavior.

---

## CLOUD_BLOCK

Expected:

Plan V1
→ OBS-B scheduled
→ original window blocked
→ persisted impact identifies affected action
→ Replan
→ OBS-B moves to valid alternative when available
→ unrelated feasible work remains stable where practical
→ Plan V2
→ `MOVED`
→ `WINDOW_INVALIDATED`-supported explanation
→ metrics comparison

Trace:

UI
→ API
→ MissionSession
→ domain
→ persistence
→ API response
→ UI

---

## BATTERY_DROP

Expected:

Plan V1
→ battery disruption
→ state changes
→ impact identifies future feasibility issue
→ committed work preserved
→ Replan
→ lower-priority future request may become unscheduled
→ higher-priority feasible work preserved
→ Plan V2
→ diff
→ reason/trace
→ metrics

---

## EMERGENCY_TASK

Expected:

Plan V1
→ emergency request/windows introduced through event
→ remaining planning problem updated
→ Replan
→ emergency request scheduled where feasible
→ competing lower-priority work may be displaced
→ Plan V2
→ diff
→ appropriate trace
→ metrics

Verify original Scenario remains immutable.

---

# 13. TEST QUALITY AUDIT

Do not count tests only.

Determine whether meaningful behavior is tested.

Audit coverage for important areas such as:

* domain serialization
* constraints
* planner determinism
* resource projection
* window selection
* unscheduled reasons
* simulation
* expiry
* mission end
* reset
* cloud event
* battery event
* emergency event
* persisted impact
* in-flight behavior
* replanning
* stability preference
* plan immutability
* diff
* DecisionTrace
* metrics
* deterministic IDs
* persistence roundtrip
* MissionSession rehydration
* API lifecycle
* concurrency
* critical frontend transformations/interactions where feasible

Classify:

* well tested
* implemented but weakly tested
* missing
* obsolete/misleading tests

A passing obsolete test does not prove current behavior.

---

# 14. BUILD + RUNTIME VERIFICATION

Run non-destructive relevant checks where practical:

* backend tests
* frontend tests
* production frontend build
* TypeScript typecheck
* lint if configured
* migrations
* Docker configuration
* Docker Compose
* PostgreSQL connectivity
* frontend/backend integration

Verify PostgreSQL is genuinely used rather than merely present as a decorative Compose service.

Check for API polling/refetch loops.

The intended model is action-driven invalidation/refetch, not repeated backend polling.

Distinguish real polling from legitimate local UI timers.

---

# 15. REFERENCE EXECUTION AUDIT

The goal is NOT to check whether AMIS visually resembles references.

Determine whether the intended concepts were meaningfully transferred.

For significant reference claims provide:

**Reference repository**

**Exact reference file/component**

**Actual reference behavior**

**AMIS file/component**

**AMIS implementation**

**Classification:**

* conceptual inspiration
* structural adaptation
* materially adapted source
* unverifiable similarity

---

## World Monitor

Focus on:

* shell/workspace structure
* panels
* map-centric composition
* density
* compact controls
* status area
* panel chrome
* efficient space use

Dark colors alone are NOT evidence.

---

## NASA Open MCT

Focus on:

* mission time
* Time Conductor concepts
* Timeline
* Plan Layout
* Event Timestrip
* selection
* inspection
* time synchronization
* operational temporal context

Do not demand Open MCT architecture.

---

## orbit.ctrl

Focus on:

* React organization
* query/hooks
* selection state
* operational details/status
* map/detail interaction
* component/API separation
* Recharts where relevant

Do not penalize AMIS for not adopting unrelated orbit.ctrl technology.

---

## openmct-mcws

Use only when useful for evaluating frontend/service/persistence boundaries.

Do not treat differences as defects by themselves.

---

# 16. REFERENCE MISUSE AUDIT

Look for evidence that reference ideas were adopted where they should NOT have been.

Examples:

* unnecessary Open MCT architectural patterns
* World Monitor domain/backend concepts
* orbit.ctrl AI/backend concepts
* fake telemetry
* fake orbital data
* fake event relationships
* duplicated mission clocks
* client-side planning
* client-side authoritative impact
* client-side authoritative plan diff
* speculative APIs
* unnecessary WebSockets
* unnecessary architecture/state complexity

Mark:

`INAPPROPRIATE`

only with evidence.

---

# 17. LICENSING + PROVENANCE AUDIT

If external source appears materially adapted, inspect:

* reference repository
* source file
* inspected commit
* AMIS destination file
* nature of adaptation
* applicable license
* attribution requirements
* `THIRD_PARTY_NOTICES.md`

Distinguish:

* conceptual inspiration
* structural adaptation
* material source adaptation

Do not claim code copying without evidence.

---

# 18. DEFECT VALIDATION RULE

Before declaring a defect, check:

1. Is the requirement current?
2. Was it superseded?
3. Is it actually an AMIS requirement rather than merely reference behavior?
4. Does another layer already implement it?
5. Is the complaint merely visual preference?
6. Is there execution/code evidence?
7. Did you trace the correct code path?
8. Do integration tests demonstrate correct behavior despite implementation differences?

If evidence is insufficient:

`UNVERIFIABLE`

Do not invent a defect.

Use these statuses where appropriate:

* `CORRECT`
* `PARTIAL`
* `MISSING`
* `INCORRECT`
* `INAPPROPRIATE`
* `UNVERIFIABLE`
* `SUPERSEDED`

---

# 19. REQUIRED OUTPUT — EXECUTIVE SUMMARY

Start with:

# Executive Summary

Summarize:

* overall system health
* backend/domain health
* planner/replanner health
* simulation/event/impact health
* persistence health
* API/contract health
* frontend/integration health
* reference execution
* testing/runtime health
* licensing/provenance

Do NOT assign an arbitrary numeric score.

---

# 20. REQUIRED OUTPUT — SYSTEM FINDINGS

Produce a concise architecture matrix:

| Area | Requirement | Actual Implementation | Evidence | Status | Gap |
| ---- | ----------- | --------------------- | -------- | ------ | --- |

Cover major areas:

* domain/planner
* MissionSession/persistence
* simulation/events/impact
* replanning/diff/traces
* metrics
* API/contracts
* frontend data layer
* operational UI
* map
* timeline
* cross-surface integration
* tests/runtime

Then provide focused sections for:

## Backend / Domain Findings

## Persistence Findings

## API / Contract Findings

## Frontend / Integration Findings

## Reference Findings

## Test / Runtime Findings

## Licensing / Provenance Findings

Avoid repeating identical findings across sections.

---

# 21. REQUIRED OUTPUT — WORKFLOW VERIFICATION

Report separately:

## CLOUD_BLOCK

## BATTERY_DROP

## EMERGENCY_TASK

For each state:

* whether the complete flow works;
* what was actually verified;
* relevant implementation evidence;
* persistence behavior;
* plan/replan behavior;
* trace behavior;
* metrics behavior;
* frontend behavior;
* relevant test evidence;
* any proven failure.

This section should prioritize execution evidence over code existence.

---

# 22. FINAL PROVEN GAPS

THIS IS THE MOST IMPORTANT OUTPUT.

Include ONLY defects supported by evidence.

Do NOT include general improvements or speculative cleanup.

For every proven issue use:

## GAP-XX — Short descriptive name

**Severity:** Critical / High / Medium / Low

**Status:** PARTIAL / MISSING / INCORRECT / INAPPROPRIATE

**Area:** Domain / Planner / Simulation / Event / Impact / Replanning / Persistence / API / Contract / Frontend / Integration / Test / Reference / Licensing

### Requirement

What AMIS should do.

### Actual behavior

What AMIS currently does.

### Evidence

**AMIS**

* exact file(s)
* relevant class/function/component

**Tests**

* relevant test/result where applicable

**Reference evidence**

* repository
* exact file/component
* inspected commit

Only include reference evidence when the defect actually concerns reference execution.

### Why this is a real defect

Explain the concrete impact.

### Smallest reasonable correction

Describe the correction conceptually.

**DO NOT IMPLEMENT IT.**

**Backend changes:** Yes / No
**API contract changes:** Yes / No
**Persistence changes:** Yes / No
**Frontend changes:** Yes / No
**Migration required:** Yes / No
**Test changes:** Yes / No

Continue with:

`GAP-02`, `GAP-03`, etc.

Do NOT create gaps merely to make the report look comprehensive.

If something is correct, say it is correct.

Do not turn optional cleanup into a defect.

---

# FINAL AUDITOR RULE

You are the auditor, not the fixing agent.

Do not modify the repository.

Do not redesign AMIS.

Do not align AMIS blindly with external repositories.

Do not invent requirements.

Do not assume functionality because a class/component exists.

Trace actual behavior.

Inspect actual source.

Run relevant verification.

Use references only for their intended responsibilities.

The final goal is to answer:

**Is the current AMIS implementation actually correct across backend, persistence, API, frontend, integration, testing and the deliberate reference strategy — and if not, exactly what is proven to be wrong?**
