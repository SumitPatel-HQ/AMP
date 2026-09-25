You are acting as a senior systems architect and research engineer for **AMIS — Adaptive Mission Planning for Earth Observation Satellites**.

## Objective

Research how the current AMIS implementation should evolve from its deterministic/demo-based mission scenarios into a **realistic working Earth-observation mission-planning simulator**, while preserving the existing adaptive-planning architecture.

This is preparation for our **second project presentation**, not the final production system.

The goal is to move clearly beyond the original 2–3 day MVP so an examiner can see that AMIS is becoming a real research/engineering project rather than a scripted demo.

**DO NOT IMPLEMENT ANYTHING YET.**

This task is research, repository inspection, gap analysis, and implementation planning only.

---

# 1. Inspect the existing AMIS repository first

Repository:

`SumitPatel-HQ/AMP`

Before proposing changes, inspect the actual current implementation.

Determine what already exists for:

* Scenario
* Satellite
* ObservationRequest
* ObservationWindow
* MissionState
* ScheduledAction
* MissionPlan
* MissionEvent
* constraints
* simulation
* greedy planner
* adaptive replanner
* impact analysis
* decision traces
* metrics
* persistence
* FastAPI
* frontend
* scenario loading
* synthetic window generation
* MissionSession
* API DTOs/contracts

Do not assume something is missing because it is not visible in the UI.

Identify the actual files/classes/functions involved.

---

# 2. Read the existing project documentation

Use the existing AMIS:
.doc/spec
* PRD
* SRD
* Implementation Guide
* Redesign Context / handoff

Treat existing locked architectural/domain decisions as authoritative unless there is strong evidence that a change is necessary.

In particular, preserve:

* planner independence from frontend/API/database
* MissionSession as the application facade/test seam
* immutable MissionPlan versions
* deterministic behavior for fixed inputs
* scenario + event history semantics
* structured reason codes
* impact analysis
* adaptive replanning
* DecisionTrace
* metrics
* current frontend/backend boundary

Do not redesign AMIS from scratch.

---

# 3. Research the transition from demo scenario → realistic scenario

The current system can use deterministic/synthetic observation windows.

Research how we should support:

```text
Mission configuration
        ↓
Real satellite orbital data
        ↓
Real geographic observation targets
        ↓
Orbit propagation
        ↓
Visibility / observation-window calculation
        ↓
ObservationWindow[]
        ↓
Existing AMIS planner
        ↓
MissionPlan
```

Specifically investigate:

### Orbital data

Research practical support for:

* TLE
* OMM if appropriate
* satellite identifiers
* epochs
* offline/static orbital datasets vs live sources

Determine what is appropriate for the second presentation.

### Orbit propagation

Research:

* SGP4
* Skyfield
* direct `sgp4` Python library where relevant

Determine the cleanest integration with the existing Python backend.

### Observation-window generation

Research how AMIS should calculate when a satellite can observe a ground target.

Consider at minimum:

* satellite position over time
* target latitude/longitude
* mission start/end
* minimum elevation / visibility geometry where applicable
* observation duration
* possible off-nadir / pointing assumptions
* window start/end generation
* computational resolution/time stepping

Be explicit about what can reasonably be considered physically realistic for this project and what would still be simplified.

---

# 4. Evaluate the existing WindowProvider architecture

The original design anticipated something conceptually like:

```text
WindowProvider
├── SyntheticWindowProvider
└── OrbitalWindowProvider
```

Inspect whether the current implementation actually supports this cleanly.

Determine:

* what currently generates ObservationWindow
* whether a provider abstraction already exists
* whether it needs modification
* how an OrbitalWindowProvider should plug in
* whether planner/replanner code can remain unchanged
* how synthetic scenarios should continue working for regression tests/demo examples

Prefer extending the existing abstraction over replacing it.

---

# 5. Research a real Scenario Builder

AMIS should no longer depend entirely on one predefined demo scenario.

Research what should be required to create a real mission scenario.

At minimum consider:

### Mission

* mission name
* start time
* end time

### Satellite

* satellite identity/name
* orbital elements
* battery capacity/current battery
* storage capacity/current storage
* availability

### Observation request

* request ID
* target name
* latitude
* longitude
* priority
* observation duration
* deadline
* energy requirement
* storage requirement

Determine:

* required vs optional fields
* validation rules
* backend/domain changes
* API changes
* frontend scenario-builder requirements
* persistence requirements

The Scenario Builder must create real AMIS domain objects rather than frontend-only mock data.

---

# 6. Define how Demo Mode should survive

Do NOT remove the existing deterministic demo.

Research how it should become an explicit examples/testing mode such as:

```text
New Mission
Load Mission
Examples
    Cloud Replanning Demo
    Battery Drop Demo
    Emergency Request Demo
```

The deterministic scenarios should remain useful for:

* regression testing
* demonstrations
* repeatable experiments
* debugging
* automated tests

But AMIS must no longer depend on them as the only operating mode.

---

# 7. Research post-MVP features

We now need to move beyond the original MVP feature list.

Research and evaluate the following potential Phase 2 / later capabilities.

## A. Real orbital observation windows

Highest priority.

## B. Configurable satellite/resource models

Evaluate realistic additions such as:

* payload/instrument availability
* observation energy consumption
* storage generation
* slew/settling time
* pointing/off-nadir limits

Identify what is worth implementing now versus later.

## C. Ground stations and downlink

Research how this could evolve the current resource model:

```text
Observation
→ onboard storage increases
→ ground-station contact
→ downlink activity
→ storage decreases
```

Investigate:

* ground station coordinates
* contact-window generation
* downlink rates
* downlink activities in MissionPlan
* impact on storage constraints

Do not necessarily recommend implementing all of this before Presentation 2. Determine the appropriate phase.

## D. Planner comparison

Research adding a second planner through the existing Planner abstraction.

Compare the suitability of:

* existing deterministic greedy planner
* OR-Tools CP-SAT

Determine what CP-SAT would add academically and how we could compare:

* utility
* completed/scheduled requests
* constraint violations
* execution time
* plan churn
* resource use

## E. Environmental data

Research how cloud/weather data could eventually replace manually injected CLOUD_BLOCK events.

Prefer architecture like:

```text
External data
→ ingestion/normalization
→ mission-state/event representation
→ AMIS core
```

Do NOT couple the planner directly to weather APIs.

## F. Multi-satellite planning

Research the architectural implications, but treat this as later unless it is surprisingly inexpensive with the current design.

---

# 8. Research data-source architecture

We want AMIS to remain reproducible.

Research an architecture like:

```text
External Sources
      ↓
Ingestion
      ↓
Normalization
      ↓
Mission Snapshot
      ↓
AMIS Domain
      ↓
Planner / Simulator / Replanner
```

Determine how AMIS could use realistic/public data while still allowing an exact mission experiment to be replayed later.

Avoid designs where the planner directly calls external APIs.

---

# 9. Research trustworthy sources

Use official/project-primary sources where possible.

Prefer:

* Skyfield documentation
* SGP4 project/documentation
* CelesTrak documentation/data formats
* NASA documentation
* ESA documentation
* OR-Tools documentation
* relevant scientific/academic mission-planning papers

GitHub can be used for implementation references, but verify libraries and avoid blindly copying another architecture.

For every important technical recommendation, provide the relevant source/link.

Distinguish clearly between:

1. AMIS repository facts
2. AMIS specification decisions
3. external research
4. your engineering recommendation

---

# 10. Determine the target for Presentation 2

Evaluate whether this is a realistic target:

```text
AMIS Phase 2

Custom mission creation
        ↓
Real satellite orbital data
        ↓
Real target coordinates
        ↓
SGP4/Skyfield orbit propagation
        ↓
Orbit-derived ObservationWindows
        ↓
Existing constraints
        ↓
Initial planning
        ↓
Simulation
        ↓
Cloud / battery / emergency event
        ↓
Impact analysis
        ↓
Adaptive replanning
        ↓
Plan comparison
        ↓
Decision traces
        ↓
Metrics
```

Tell us explicitly:

* what should definitely be completed before Presentation 2
* what is optional
* what should wait until the final presentation

Prioritize **technical credibility and visible project progression**, not feature quantity.

---

# 11. Produce a concrete gap analysis

Create a matrix like:

| Requirement | Existing implementation | Relevant files | Gap | Change required | Risk |
| ----------- | ----------------------- | -------------- | --- | --------------- | ---- |

Cover at minimum:

* scenario creation
* satellite orbital data
* target definition
* synthetic windows
* orbital windows
* planner compatibility
* constraints
* simulation
* events
* impact
* replanning
* persistence
* APIs
* frontend
* testing

Do not mark something missing without checking the repository.

---

# 12. Produce an implementation sequence

After research, propose the safest sequence of implementation stages.

For example, investigate whether the correct sequence is approximately:

```text
1. Scenario/domain audit
2. Orbital-data representation
3. OrbitalWindowProvider
4. Observation-window verification/tests
5. Scenario creation APIs
6. Scenario Builder UI
7. Integration with existing planner
8. Persistence
9. Mission-control visualization updates
10. Post-MVP extensions
```

But do not blindly use this order.

Derive the final sequence from the actual repository.

For each stage include:

* objective
* existing components reused
* files likely affected
* new components
* API/domain changes
* tests required
* dependencies
* risks
* acceptance criteria

---

# 13. Protect the current working system

The current adaptive loop already works.

Any recommendation must preserve:

```text
Scenario
→ Windows
→ Plan V1
→ Simulate
→ Event
→ Impact
→ Replan
→ Plan V2
→ Explain
→ Metrics
```

Do not recommend a giant rewrite.

Prefer incremental replacements such as:

```text
SyntheticWindowProvider
            ↓
      common interface
            ↑
OrbitalWindowProvider
```

Existing demo tests must continue to work.

---

# 14. Final research output

Produce one structured research report with these sections:

1. Executive Summary
2. Current AMIS Architecture Relevant to Phase 2
3. What Is Currently Demo/Synthetic
4. What Can Already Be Reused
5. Realistic Scenario Architecture
6. Orbital Data & Propagation Research
7. Observation Window Generation
8. Scenario Builder Requirements
9. Synthetic vs Orbital Provider Design
10. Post-MVP Feature Evaluation
11. Ground Station/Downlink Research
12. CP-SAT / Planner Comparison Research
13. Environmental Data Integration
14. Reproducible Data-Ingestion Architecture
15. Repository Gap Analysis
16. Recommended Presentation-2 Scope
17. Features Deferred to Final Presentation
18. Implementation Sequence
19. File-Level Change Map
20. Risks / Open Questions
21. Source References

Finish with a concise recommended architecture diagram:

```text
Realistic Inputs
      ↓
Providers / Ingestion
      ↓
AMIS Domain
      ↓
Existing Planning Core
      ↓
Simulation
      ↓
Events / Impact
      ↓
Adaptive Replanning
      ↓
Explanation / Evaluation
```

And give a final classification of every investigated feature as:

`PRESENTATION 2` / `NEXT` / `FINAL-LATER`

Do not write production code in this task.

The objective is to give us enough evidence to create precise coding-agent prompts afterward without guessing, over-engineering, or breaking the current working implementation.
# Additional reference repositories

Inspect these repositories in addition to official technical sources.

## 1. Ceng-0324/SkyOps

SkyOps is a drone/low-altitude mission autonomy system, not an
Earth-observation satellite planner. Do not copy its drone-specific
domain architecture into AMIS.

Study it specifically for:

- separation between mission planning, rules, incident replanning and review;
- its evaluation architecture;
- evaluation contracts;
- evaluation datasets/cases;
- evaluation runner;
- scoring methodology;
- hard-constraint evaluation;
- incident-response evaluation;
- explainability evaluation;
- plan-efficiency evaluation;
- how it communicates that simulated results are not production certification.

Inspect at minimum:

- backend/app/core/orchestration/mission_planner.py
- backend/app/core/orchestration/incident_replanner.py
- backend/app/core/orchestration/mission_reviewer.py
- backend/app/core/evaluation/
- backend/app/data/evaluation/

Determine which evaluation concepts could strengthen AMIS after the MVP.

Do NOT import SkyOps drone-specific concepts such as airspace, GPS,
crowd or flight-controller semantics unless an equivalent requirement
actually exists in AMIS.

Produce an AMIS-specific proposal for an evaluation suite.

---

## 2. patrickkuei/Satellite-Mission-Control-Dashboard

This repository was originally used primarily as a React/TypeScript
satellite-operations UI reference.

Its role is now expanded.

Inspect it for both:

### A. Satellite operations UI

- globe/workspace organization
- satellite detail presentation
- ground-track visualization
- pass information
- telemetry treatment
- selected-satellite state
- operational density

### B. Real orbital-data implementation

Inspect at minimum:

- scripts/fetch-tle-snapshot.mjs
- apps/web/src/utils/sgp4.ts
- apps/web/src/hooks/useSatellitePositions.ts
- apps/web/src/hooks/useGroundTrack.ts
- apps/web/src/hooks/usePasses.ts
- packages/types/src/satellite.ts
- packages/types/src/position.ts
- packages/types/src/pass.ts
- packages/types/src/ground-track.ts
- docs/ARCHITECTURE.md

Study how it handles:

CelesTrak
→ TLE retrieval
→ cached/static snapshot
→ SGP4 propagation
→ satellite position
→ ground track
→ pass prediction
→ frontend visualization

AMIS uses Python/FastAPI and should NOT adopt this repository's
Node/TypeScript backend architecture merely because the functionality
is useful.

Instead determine how the same concepts map cleanly to:

OrbitalDataProvider
→ Skyfield/SGP4
→ AMIS Satellite state
→ OrbitalWindowProvider
→ ObservationWindow[]
→ existing AMIS Planner

Also compare its concept of an observer pass with AMIS's concept of an
Earth-observation target visibility window. Explicitly identify where
they are equivalent and where they are not.

Do not assume that a satellite being above the horizon is sufficient
for Earth-observation feasibility. Research the additional geometry or
pointing assumptions AMIS requires.