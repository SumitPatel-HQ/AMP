# AMIS --- Product Requirements Document (PRD)

**Project:** Adaptive Mission Planning for Earth Observation Satellites\
**Document Type:** Product Requirements Document\
**MVP Target:** 2--3 day implementation sprint\
**Positioning:** Student research prototype; software-only mission
planning simulator

## 1. Product Overview

AMIS is a software-based mission-planning simulator for Earth
observation satellites. It allows a user to define observation requests,
generate observation opportunities, schedule tasks under resource and
timing constraints, simulate mission execution, inject disruptions,
automatically replan affected work, and inspect why the revised plan was
selected.

The MVP is not a satellite-control system, image-processing pipeline, or
high-fidelity flight-dynamics simulator. Its purpose is to demonstrate
adaptive mission planning in a controlled and reproducible environment.

## 2. Product Goal

Demonstrate the complete adaptive planning loop:

**Mission objectives → visibility/resources → initial plan → simulation
→ disruptive event → impact detection → replanning → plan comparison →
explanation → metrics**

A successful MVP must make this loop visible and repeatable from one
interface.

## 3. Target User

The primary MVP user is a researcher, student, evaluator, or
operator-like user who needs to:

-   define a small Earth-observation mission scenario;
-   inspect the initial schedule;
-   simulate mission progress;
-   introduce a controlled disturbance;
-   observe which tasks become infeasible;
-   generate a revised schedule;
-   understand why tasks moved, were inserted, or were dropped;
-   compare mission performance before and after replanning.

## 4. Core User Stories

1.  As a user, I can create a scenario containing a satellite and
    observation requests.
2.  As a user, I can assign target location, priority, duration, and
    deadline to each observation request.
3.  As a user, I can generate observation windows for those requests.
4.  As a user, I can generate an initial feasible mission plan.
5.  As a user, I can view scheduled tasks on a mission timeline.
6.  As a user, I can inspect current satellite battery, storage, and
    mission state.
7.  As a user, I can inject a cloud, battery, or emergency-task event.
8.  As a user, I can see which scheduled tasks are affected by the
    event.
9.  As a user, I can trigger adaptive replanning.
10. As a user, I can compare the original and revised plans.
11. As a user, I can see a reason for every significant replanning
    decision.
12. As a user, I can inspect mission-performance metrics.

## 5. MVP Scope

### 5.1 P0 --- Required

  -----------------------------------------------------------------------
  Capability                          MVP Requirement
  ----------------------------------- -----------------------------------
  Scenario Builder                    Create/load one deterministic
                                      mission scenario

  Satellite Model                     1 satellite with battery, storage,
                                      availability, and simulated time

  Observation Requests                5--10 tasks with target, priority,
                                      duration, and deadline

  Observation Windows                 Generate practical/synthetic
                                      visibility windows

  Constraint Validation               Validate time window, deadline,
                                      overlap, battery, storage, and
                                      availability

  Baseline Planner                    Generate an initial schedule using
                                      a deterministic
                                      greedy/constraint-based strategy

  Mission Simulation                  Advance simulated time and update
                                      satellite state

  Event Injection                     Support cloud blockage, battery
                                      drop, and emergency priority task

  Impact Analysis                     Identify tasks invalidated or
                                      affected by an event

  Adaptive Replanner                  Preserve completed/past work and
                                      rebuild the remaining feasible plan

  Plan Versioning                     Preserve initial and revised plans
                                      for comparison

  Decision Trace                      Record trigger, affected
                                      constraint, action, and mission
                                      effect

  Timeline                            Show before/after scheduled actions

  2D Mission View                     Show satellite/target context using
                                      a lightweight map

  Metrics                             Utility, completion, violations,
                                      planning/replanning time, resource
                                      use, churn

  Repeatability                       Scenario seed/configuration
                                      produces repeatable experiments
  -----------------------------------------------------------------------

### 5.2 Event Priority

Implement in this order:

1.  `CLOUD_BLOCK`
2.  `BATTERY_DROP`
3.  `EMERGENCY_TASK`

Only add `COMMUNICATION_OUTAGE` and `SATELLITE_UNAVAILABLE` if the
complete P0 loop already works.

## 6. Explicitly Out of Scope for Sprint

The MVP does not require:

-   real satellite command/control;
-   operational command generation;
-   live ISRO/NASA integrations;
-   live weather APIs;
-   a custom high-fidelity orbital/flight-dynamics engine;
-   Earth-observation image processing;
-   large satellite constellations;
-   reinforcement learning;
-   genetic algorithms;
-   multi-agent planning;
-   Kubernetes or microservices;
-   RBAC, enterprise authentication, or alerting;
-   sophisticated 3D globe visualization;
-   mandatory LLM integration;
-   LLM-based planning.

An LLM must never be the core planning engine.

## 7. Functional Requirements

### FR-01 Scenario Creation

The system shall allow creation of a mission scenario containing a
satellite, simulation interval, initial resources, and observation
requests.

### FR-02 Observation Requests

Each request shall contain at minimum:

-   unique ID;
-   target latitude/longitude;
-   priority from 1--5;
-   observation duration;
-   deadline;
-   status.

### FR-03 Observation Opportunities

The system shall associate each observation request with one or more
valid observation windows. For the sprint, deterministic synthetic
windows are acceptable and preferred before orbital computation is
added.

### FR-04 Initial Planning

The system shall produce a schedule that attempts to maximize mission
utility while respecting configured constraints.

### FR-05 Constraint Validation

A scheduled action shall be rejected or flagged when it violates:

-   observation window;
-   deadline;
-   task overlap;
-   battery availability;
-   storage availability;
-   satellite availability.

### FR-06 Simulation

The user shall be able to advance mission time. State updates shall be
deterministic for the same scenario and seed.

### FR-07 Event Injection

The user shall be able to inject supported events at a selected
simulation time.

### FR-08 Impact Detection

After an event, the system shall identify which scheduled actions remain
valid and which require replanning.

### FR-09 Adaptive Replanning

The replanner shall preserve completed actions and past mission history,
apply the changed state, and generate a new plan for remaining work.

### FR-10 Explanation

For each meaningful plan change, the system shall produce a structured
reason code and human-readable explanation.

Example:

> Task OBS-002 moved from 10:20 to 11:15 because its original
> observation window was invalidated by cloud cover. The later window
> was selected because it remained feasible before the task deadline.

### FR-11 Plan Comparison

The UI shall show the previous and revised plan and identify unchanged,
moved, inserted, and dropped tasks.

### FR-12 Metrics

The system shall calculate:

-   mission utility/reward;
-   task completion rate;
-   constraint violations;
-   planning time;
-   replanning time;
-   battery/storage utilization;
-   plan churn;
-   explanation coverage.

## 8. User Interface Requirements

The sprint should use one functional dashboard rather than multiple
polished screens.

Recommended layout:

``` text
+---------------------------------------------------------------+
| Scenario | Generate Plan | Step | Inject Event | Replan       |
+---------------------------+-----------------------------------+
|                           | Mission State                     |
|  2D Map / Targets         | Time / Battery / Storage          |
|                           | Active Event                      |
+---------------------------+-----------------------------------+
| Initial Plan Timeline                                         |
+---------------------------------------------------------------+
| Revised Plan Timeline                                         |
+---------------------------------------------------------------+
| Decision Trace / Explanation        | Metrics                 |
+---------------------------------------------------------------+
```

The interface must prioritize visibility of the planning/replanning
process over visual decoration.

## 9. Success Criteria

The MVP is successful when all of the following can be demonstrated in
one repeatable scenario:

1.  A mission containing one satellite and at least five observation
    requests can be loaded or created.
2.  Observation windows are generated.
3.  The baseline planner produces a valid initial plan.
4.  The simulator advances mission state.
5.  A disruption can be injected.
6.  The system identifies at least one affected scheduled action.
7.  The replanner produces a new plan without altering completed/past
    actions.
8.  The UI visibly compares the old and new plan.
9.  Every moved/dropped/inserted task has a structured explanation.
10. Metrics are calculated for the initial and revised plans.
11. Re-running the same seeded scenario produces the same planning
    result.
12. The complete workflow operates locally without requiring live
    external APIs or an LLM.

## 10. Demo Acceptance Scenario

Use a deterministic scenario with `SAT-001` and tasks `OBS-A` through
`OBS-E`.

Expected demonstration:

1.  Generate observation windows.
2.  Generate Plan v1.
3.  Begin simulation.
4.  Inject cloud blockage affecting the planned window for `OBS-B`.
5.  Mark the original `OBS-B` action infeasible.
6.  Replan the remaining mission.
7.  Schedule `OBS-B` into a later feasible window if one exists.
8.  Generate Plan v2.
9.  Show the plan diff and decision trace.
10. Compare utility, completion, violations, resource use, and plan
    churn.

## 11. MVP Completion Definition

The project is **not complete** merely because a dashboard displays
satellite data.

The MVP is complete only when this closed loop works:

``` text
CREATE SCENARIO
      ↓
GENERATE WINDOWS
      ↓
CREATE VALID PLAN
      ↓
SIMULATE
      ↓
INJECT CHANGE
      ↓
DETECT IMPACT
      ↓
REPLAN
      ↓
EXPLAIN
      ↓
COMPARE + MEASURE
```

## 12. Post-MVP Candidates

After the core loop is stable, potential extensions include real
TLE/ephemeris inputs, Skyfield/SGP4-based visibility, multiple
satellites, communication/downlink windows, CP-SAT/MILP planners, Monte
Carlo uncertainty experiments, CesiumJS visualization, planner plugins,
human approval workflows, audit features, REST/WebSocket integrations,
and optional local-LLM natural-language explanations.
