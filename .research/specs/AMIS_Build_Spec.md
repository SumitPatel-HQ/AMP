# AMIS build spec

Adaptive mission planning and explainable decision support for Earth observation satellites.

This document is the single buildable specification. It consolidates the PRD, the SRD, the Implementation Guide, the research and development document, and twenty eight design decisions settled in review. Where it disagrees with a source document, this document wins, and the disagreements are called out where they occur.

Companion documents. The glossary is `CONTEXT.md` at the repository root, and this spec uses those terms and no others. Three decisions carry architecture decision records in `docs/adr/`. The source documents remain in `.doc/` for reference.

Repository state when written: empty. No source tree, no dependencies, no CI.

Status: decisions only. This document authorises no code.

## Problem statement

A researcher studying Earth observation mission planning cannot watch an observation plan survive a change in its own assumptions. Planning algorithms get studied apart from the operator tools that make their output readable, and operator dashboards get built without a measurable planner underneath. Someone who wants to ask what happens when cloud covers a target, or the battery drops, or an urgent request arrives mid mission, has to either trust a paper that ran the experiment once in a private test rig, or build the whole environment themselves.

The user cannot today do all of the following in one place. Define a small satellite mission. Get a feasible initial plan from it. Advance mission time. Inject a controlled disruption. See which scheduled actions that disruption invalidated. Get a revised plan that respects everything already executed. Read why each observation request moved, arrived, or got dropped. Compare the two plans on utility, completion, violations, resource use, and churn. Do all of it offline, and get the same answer on every run.

## Solution

AMIS is a local simulator for Earth observation mission planning. It makes the full adaptive loop visible and repeatable from one dashboard. The loop runs in this order: create a scenario, generate observation windows, produce Plan v1, simulate forward, inject an event, read the impact, replan into Plan v2, explain every change, then compare and measure.

The user loads a deterministic demo scenario holding one satellite, `SAT-001`, and five observation requests, `OBS-A` through `OBS-E`. Each request carries a target coordinate, a priority from 1 to 5, a duration, a deadline, and its energy and storage cost. The system generates observation windows, runs a greedy planner under timing and resource constraints, and draws the resulting plan on a mission timeline beside live battery, storage, and simulated clock readouts, with the targets plotted on a 2D map.

The user then steps the simulation forward and injects one of three events. `CLOUD_BLOCK` invalidates one observation window. `BATTERY_DROP` lowers the available energy. `EMERGENCY_TASK` introduces a new priority 5 request mid mission. The system marks which unfrozen actions became invalid and says why, but it does not replan on its own. Replanning is a separate action the user takes, which keeps cause and effect readable.

On replan, the system freezes every action that has already started, rebuilds the rest, and creates an immutable Plan v2. The dashboard stacks both timelines, shows a per request comparison, lists a decision trace giving a reason code and a generated sentence for every change, and puts the v1 and v2 metrics side by side. Running the same scenario again produces identical output. Nothing in the loop needs a network, an API key, or a language model.

## Scope

In scope for this build:

One satellite with a battery, storage, and an availability flag. Five to ten observation requests with targets, priorities, durations, deadlines, and resource costs. Deterministic synthetic observation windows generated from scenario configuration. Six constraint checks returning structured violations. A deterministic greedy planner behind a replaceable interface. A simulation engine with a clock, resource accounting, request expiry, and a definite end. Three event types injected at a chosen simulated time. Impact analysis recorded against the plan it was evaluated against. Adaptive replanning that freezes executed work and rebuilds the rest. Immutable versioned plans with parent links. Plan comparison keyed by request id. Structured decision traces with generated text. Eight metrics. A REST API. In memory repositories, then PostgreSQL. A single page React dashboard. A demo script that runs the loop at the command line. Docker Compose.

## Out of scope

Out entirely, for this build:

Real satellite command and control, and operational command generation. Live ISRO, NASA, weather, or TLE integrations. A high fidelity orbital or flight dynamics engine. Earth observation image processing. Satellite constellations, since the MVP models one satellite. Reinforcement learning, genetic algorithms, and multi agent planning. Kubernetes, microservices, and cloud deployment. Access control, authentication, and alerting. CesiumJS and any 3D globe. Language model integration of any kind, in any role.

Deferred until the loop demonstrably works:

The `COMMUNICATION_OUTAGE` and `SATELLITE_UNAVAILABLE` event types. The OR-Tools CP-SAT planner, whose protocol exists from day one though its implementation does not. Skyfield and SGP4 window generation, whose provider protocol exists from day one though its implementation does not. Solar recharge and downlink driven storage release. A seeded scenario generator for bulk experiments. Replay mode and playback controls. The experiment browser and benchmark screen. Frontend component tests. A decision trace for request expiry, which the request status covers instead. Drawing observation windows on the timeline.

Cut order if the sprint runs behind: 3D visualisation, then OR-Tools, then Skyfield and SGP4, then the experiment browser, then replay controls, then the extra event types, then elaborate charts, then animations, then language model explanations, then advanced planning algorithms.

Never cut, for any reason: the scenario, mission state, observation windows, constraints, the initial planner, the controlled event, impact detection, adaptive replanning, plan comparison, the decision trace, metrics, and repeatability. These twelve are the research contribution. Without all of them the project is a dashboard that displays satellite data, which the PRD names as insufficient.

## User stories

### Scenario definition and loading

1. As a researcher, I want to load a bundled demo scenario with one command or one click, so that I can see the system work before I author anything myself.
2. As a researcher, I want to create a scenario holding a satellite and a set of observation requests, so that I can model the mission I care about.
3. As a researcher, I want to set the scenario's simulation start and end time, so that the planning horizon is bounded and explicit.
4. As a researcher, I want to set the satellite's battery capacity and starting charge, so that I can build missions that run out of energy on purpose.
5. As a researcher, I want to set the satellite's storage capacity and starting usage, so that I can build missions that run out of storage on purpose.
6. As a researcher, I want to save a scenario to a JSON file and load it back unchanged, so that I can version scenarios in git beside the code.
7. As a researcher, I want the scenario to stay unchanged no matter what events I inject, so that "the same scenario" means one fixed thing throughout an experiment.
8. As an evaluator, I want an invalid scenario rejected with a specific error code rather than a stack trace, so that I can tell what I got wrong.

### Observation requests

9. As a researcher, I want every observation request to carry a stable id, so that I can follow one request through planning, replanning, comparison, and explanation.
10. As a researcher, I want to give each request a target latitude and longitude, so that it corresponds to a place I can see on the map.
11. As a researcher, I want to give each request a priority from 1 to 5, so that the planner can choose between requests that compete for the same time.
12. As a researcher, I want to give each request an observation duration, so that the planner knows how much of a window it consumes.
13. As a researcher, I want to give each request a deadline, so that requests can become infeasible through the passage of time alone.
14. As a researcher, I want to declare the energy and storage each request consumes, so that the resource constraints actually bind.
15. As a researcher, I want to see each request's current status, so that I can tell at a glance what the mission has achieved.

### Observation windows

16. As a researcher, I want observation windows generated for every request from the scenario configuration, so that the planner has concrete opportunities to choose between.
17. As a researcher, I want at least one request in the demo scenario to have two windows, so that replanning has somewhere to move a displaced request.
18. As a researcher, I want window generation to depend only on the scenario, so that two runs of the same scenario produce the same windows.
19. As a researcher, I want each window to carry a validity flag and an invalidation reason, so that I can see which opportunities an event destroyed and why.
20. As a maintainer, I want window generation to sit behind a provider interface, so that a Skyfield or SGP4 provider can replace the synthetic one later without changing the planner.

### Initial planning

21. As a researcher, I want to generate an initial mission plan from the scenario, so that I have a baseline.
22. As a researcher, I want the baseline planner to be a deterministic greedy algorithm, so that I can explain every one of its choices to a reviewer.
23. As a researcher, I want the planner to consider requests in a stated order, priority descending, then deadline ascending, then duration ascending, then id ascending, so that ties never resolve arbitrarily.
24. As a researcher, I want the plan to record which requests it could not schedule and why, so that the failures inform me as much as the successes.
25. As a researcher, I want an empty plan carrying a reason code per request when nothing can be scheduled, rather than an error, so that I learn why nothing fit instead of only that nothing fit.
26. As a researcher, I want the plan to record its own planning time in milliseconds, so that I can report performance honestly.
27. As a researcher, I want the plan to carry a version number and its parent plan's id, so that I can walk the plan history.
28. As a researcher, I want a plan to become immutable once created, so that replanning cannot rewrite history.

### Constraint validation

29. As a researcher, I want a scheduled action rejected when it falls outside its observation window, so that plans respect visibility.
30. As a researcher, I want a scheduled action rejected when it ends after its request's deadline, so that plans respect mission timing.
31. As a researcher, I want a scheduled action rejected when it overlaps another scheduled action, so that plans are executable.
32. As a researcher, I want a scheduled action rejected when the projected battery at its start time cannot cover it, so that plans respect energy.
33. As a researcher, I want a scheduled action rejected when the projected storage at its start time cannot hold its output, so that plans respect onboard capacity.
34. As a researcher, I want a scheduled action rejected when the satellite is unavailable, so that outages change the plan.
35. As a researcher, I want every rejection to return a violation carrying a reason code and the offending request's id, rather than a bare false, so that the explanation layer has something authoritative to read.
36. As a researcher, I want to validate a whole plan in one call and receive every violation, so that I can assert a revised plan is fully feasible.
37. As a researcher, I want validation to cover unfrozen actions only, so that a plan cannot fail permanently over an action nobody can change.

### Simulation

38. As a researcher, I want to advance simulated mission time by a fixed step, so that I can watch the mission unfold at my own pace.
39. As a researcher, I want battery and storage to change as observations execute, so that the mission state reflects what the plan did.
40. As a researcher, I want actions to become started and then completed as simulated time passes them, so that "already executed" is a concrete property.
41. As a researcher, I want to read the current mission state at any point, so that I always know the situation the planner reasons about.
42. As a researcher, I want the clock to stop at the scenario's end time and mark the mission complete, so that the mission has a definite finish where final metrics belong.
43. As a researcher, I want to reset the simulation to the moment of load, clearing plans, events, traces, and impacts, so that a reset state is always reproducible from the scenario and its event log.
44. As a researcher, I want the same scenario and the same step sequence to produce the same final state, so that I can verify determinism rather than assert it.

### Request expiry

45. As a researcher, I want a request marked expired the moment simulated time passes its deadline, so that the state panel never shows a request as live after it is lost.
46. As a researcher, I want expired requests excluded from every later plan, so that the planner does not produce a deadline violation for something already lost.
47. As a researcher, I want expired requests to keep counting against the completion rate, so that a mission that loses everything cannot report perfect completion.

### Event injection

48. As a researcher, I want to inject a `CLOUD_BLOCK` event naming one observation window, so that I invalidate exactly the opportunity I intend to.
49. As a researcher, I want to inject a `BATTERY_DROP` event setting a new battery value, so that I can make energy the binding constraint mid mission.
50. As a researcher, I want to inject an `EMERGENCY_TASK` event carrying a new high priority request and its windows, so that I can test how the system absorbs urgent work.
51. As a researcher, I want to choose the simulated time at which an event applies, so that I can test early, middle, and late disruptions.
52. As a researcher, I want event injection and replanning to stay separate operations, so that I can inspect the damage before I decide to repair it.
53. As a researcher, I want every injected event recorded with its id, type, time, and payload, so that I can replay the experiment from its event log.
54. As a researcher, I want to replay an experiment by loading the original scenario and reapplying the event log, so that reproduction needs no saved intermediate state.
55. As a researcher, I want a malformed event rejected with a specific error code, so that bad input fails early and loudly.

### Impact analysis

56. As a researcher, I want the system to split every unfrozen action into valid or invalid after an event, so that I can see how far the damage reaches.
57. As a researcher, I want actions that have already started treated as frozen, so that the system cannot rewrite what already happened.
58. As a researcher, I want impact analysis to return the reason codes behind each invalid action, so that the explanation layer reads authoritative data.
59. As a researcher, I want a cloud block to invalidate only the action using the blocked window, unless real knock on effects exist, so that I can trust the analyzer to be precise.
60. As a researcher, I want to read the impact before I replan, so that the demo tells a cause then effect story.
61. As a researcher, I want each impact record to name the plan version it was evaluated against, so that an impact read later cannot be mistaken for an assessment of the current plan.

### Adaptive replanning

62. As a researcher, I want to trigger replanning myself, so that adaptation is a visible decision point rather than a hidden side effect.
63. As a researcher, I want replanning to leave every frozen action exactly as it was, so that mission history survives intact.
64. As a researcher, I want replanning to apply the event's effect on state, windows, and requests before it reschedules, so that the new plan reasons about the world as it now is.
65. As a researcher, I want replanning to reconsider every unexpired unfrozen request, including ones the previous plan dropped and ones an event introduced, so that nothing gets quietly forgotten.
66. As a researcher, I want replanning to call the same planner interface the initial plan used, so that a future CP-SAT planner replaces it without touching the replanning logic.
67. As a researcher, I want replanning to produce a new plan version naming its parent, so that the plan lineage stays complete.
68. As a researcher, I want the resulting plan validated before it is returned, so that a revised plan is never less feasible than the one it replaced.
69. As a researcher, I want a request to keep its previous start time whenever that placement is still feasible, so that plan churn measures the disruption rather than the planner's own variability.
70. As a researcher, I want a displaced request moved into a later feasible window when one exists, so that the system demonstrates repair rather than deletion.
71. As a researcher, I want a displaced request dropped with reason `NO_ALTERNATIVE_WINDOW` when no later window fits, so that the failure is explicit and explained.
72. As a researcher, I want replanning time recorded apart from initial planning time, so that the cost of adapting is measurable.
73. As a researcher, I want to replan without injecting an event and get an identical plan back as a new version, so that I can verify replanning adds no variability of its own.
74. As a researcher, I want a replan that names a stale parent plan rejected, so that two concurrent replans cannot both write the same next version.

### Plan comparison

75. As a researcher, I want plans compared by request id rather than by list position, so that the comparison stays correct when the plan reorders.
76. As a researcher, I want each request classified as `UNCHANGED`, `MOVED`, `INSERTED`, `DROPPED`, or `COMPLETED`, so that the change set is complete and unambiguous.
77. As a researcher, I want a moved request to report its old and new start times, so that I can quote the change precisely.
78. As a researcher, I want the comparison to carry the reason code behind each change, so that the comparison and the explanation cannot disagree.
79. As an evaluator, I want to compare any two plan versions rather than only consecutive ones, so that I can measure a whole mission's drift.

### Explanation and decision trace

80. As an operator, I want a decision trace record for every plan change, so that no change goes unaccounted for.
81. As an operator, I want each trace to carry a reason code from a fixed vocabulary, so that I can compare explanations across experiments.
82. As an operator, I want each trace to name the triggering event, the broken constraint, the previous action, and the new action, so that I can reconstruct the decision without reading source code.
83. As an operator, I want the readable sentence generated from the trace data, so that the sentence cannot contradict the decision.
84. As a researcher, I want explanations generated without a language model, so that the system stays offline and deterministic.
85. As an evaluator, I want explanation coverage to reach 1.0 in the demo scenario, so that "every change is explained" is measured rather than hoped for.

### Metrics

86. As a researcher, I want mission utility computed as the sum of priorities across the deduplicated set of scheduled or completed requests, so that plan quality has one headline number with no double counting.
87. As a researcher, I want a completion rate, so that I can report robustness.
88. As a researcher, I want a count of constraint violations in a plan, so that feasibility is quantified.
89. As a researcher, I want planning and replanning wall clock times in milliseconds, so that I report the cost rather than claim it.
90. As a researcher, I want battery and storage use relative to capacity, so that efficiency is visible.
91. As a researcher, I want plan churn computed over unfrozen actions only, so that frozen history cannot dilute the number.
92. As a researcher, I want explanation coverage computed as changed actions with a trace over changed actions, so that explainability is measured.
93. As a researcher, I want churn and coverage to return "not applicable" when their denominators are zero, so that a metric with no basis is never displayed as a score.
94. As a researcher, I want every metrics result to name the request pool it was computed over, so that a comparison across two different pools cannot mislead me.
95. As a researcher, I want the system to flag a comparison whose two sides used different request pools, so that the emergency request demo reports honestly.
96. As a researcher, I want before and after metrics shown side by side, so that the effect of an event reads as one comparison.
97. As a researcher, I want metrics returned as a plain serialisable object with no UI dependency, so that I can feed them into a paper, a notebook, or a CSV.

### Dashboard

98. As an evaluator, I want one dashboard that runs the whole demo, so that I never open a terminal or the API docs to see the research claim.
99. As an evaluator, I want a control strip holding load, generate plan, step, inject event, and replan, so that the stages appear in the order I perform them.
100. As an evaluator, I want a mission state panel showing simulated time, battery, storage, and the active event, so that I always know the current situation.
101. As an evaluator, I want a 2D map showing the satellite and the target locations, so that the mission has geographic context.
102. As an evaluator, I want the initial and revised plan timelines stacked vertically, so that I compare them by eye without switching views.
103. As an evaluator, I want changed requests marked on the revised timeline, so that the comparison reads at a glance.
104. As an evaluator, I want frozen actions drawn differently from unfrozen ones, so that I can see what replanning was never allowed to touch.
105. As an evaluator, I want an unscheduled list beneath each timeline with each request's reason code, so that I can see what a plan failed to fit and why.
106. As an evaluator, I want to pick a cloud block target from a request dropdown and then a window dropdown, so that I can choose a window without reading JSON.
107. As an evaluator, I want a decision trace panel listing each change with its reason code and sentence, so that the explanation sits beside the thing it explains.
108. As an evaluator, I want a metrics panel comparing v1 and v2, so that the outcome of adapting is quantified on screen.
109. As an evaluator, I want to click a trace entry and see the matching request highlight on both timelines, so that the trace and the plan link together.
110. As an evaluator, I want a dense dark console theme, so that the interface reads as mission tooling.
111. As an evaluator, I want API errors shown as readable messages with their codes, so that I can diagnose a failed step from the browser.

### Reproducibility and operations

112. As a researcher, I want the whole core workflow to run offline with no API keys, so that the demo cannot fail because of a network.
113. As a researcher, I want to run the full loop from a test or a demo script with no frontend, so that the backend is provably the system of record.
114. As a researcher, I want the whole stack to start with one command, so that a reviewer can run it unaided.
115. As a researcher, I want plans, events, and traces to survive a backend restart once persistence lands, so that experiments are recoverable.
116. As a researcher, I want generated ids to be sequential and derived from persisted state, so that they survive a restart and stay identical across runs.
117. As a researcher, I want a rerun of a scenario to produce identical output once the wall clock and timing fields are removed, so that I can diff two runs rather than compare selected fields.

## Data model

Every entity below is a domain type. Persistence records convert into these at the repository boundary, and nothing outside persistence handles an ORM row.

### Scenario

Holds an id, a name, the simulation start and end time, one satellite, and a list of observation requests. Immutable after load. See ADR-0002.

### Satellite

Holds an id, a battery capacity in watt hours, a starting battery charge, a storage capacity in megabytes, a starting storage usage, and an availability flag.

### ObservationRequest

Holds an id, a target latitude and longitude, a priority from 1 to 5, a duration in seconds, a deadline, a status, a storage cost in megabytes, and an energy cost in watt hours. Never carries a start time.

### ObservationWindow

Holds an id, the request id it belongs to, the satellite id, a start time, an end time, a validity flag, and an optional invalidation reason.

### MissionState

A value snapshot, not a mutable singleton. Holds the scenario id, the simulated time, the satellite id, the current battery, the current storage usage, the availability flag, the active event ids, the completed request ids, and a mission complete flag.

### ScheduledAction

Holds an id, a request id, a satellite id, a window id, a start time, an end time, a status, an expected energy cost, and an expected storage cost.

### MissionPlan

Holds an id, a scenario id, a version number, an optional parent plan id, a creation timestamp, a list of scheduled actions, a list of unscheduled request ids each with a reason code, the mission utility, a constraint violation count, and the planning time in milliseconds. Immutable after creation.

### MissionEvent

Holds an id, a scenario id, an event type, an event time, and a typed payload. `CLOUD_BLOCK` carries a request id and a window id. `BATTERY_DROP` carries a satellite id and a new battery value. `EMERGENCY_TASK` carries a complete observation request together with its explicit observation windows.

### Impact

Holds an id, the event id that produced it, the id of the plan it was evaluated against, the frozen action ids, the valid unfrozen action ids, the invalid unfrozen action ids, and the reason codes behind the invalid ones. Written at injection time, never recomputed.

### Violation

Holds a reason code, the offending request id, and a details object. Constraint checks return these rather than booleans.

### PlanDiffEntry

Holds a request id, a change type, an optional old start time, an optional new start time, and a reason code.

### MetricsResult

Holds a plan id, the mission utility, the completion rate, the violation count, the planning or replanning time, the battery and storage utilisation, the plan churn, the explanation coverage, the request pool size, and the request pool id set. Churn and coverage are nullable.

### DecisionTrace

Holds an id, a plan id, an optional event id, an optional request id, a reason code, an optional previous action, an optional new action, an optional constraint name, a generated message, and a metadata object.

### Enumerations

`RequestStatus` covers pending, scheduled, completed, dropped, and expired. Note the rename from the Implementation Guide's `TaskStatus`, since `CONTEXT.md` bans "task" as a domain term.

`ActionStatus` covers planned, started, and completed.

`EventType` covers `CLOUD_BLOCK`, `BATTERY_DROP`, and `EMERGENCY_TASK` for this build, with `COMMUNICATION_OUTAGE` and `SATELLITE_UNAVAILABLE` reserved. `EMERGENCY_TASK` keeps its name because it is a fixed wire value rather than a domain term.

`PlanChangeType` covers `UNCHANGED`, `MOVED`, `INSERTED`, `DROPPED`, and `COMPLETED`.

`ReasonCode` covers `WINDOW_INVALIDATED`, `INSUFFICIENT_BATTERY`, `INSUFFICIENT_STORAGE`, `DEADLINE_VIOLATION`, `TIME_OVERLAP`, `SATELLITE_UNAVAILABLE`, `DISPLACED_BY_COMPETING_REQUEST`, `ALTERNATIVE_WINDOW_AVAILABLE`, `NO_ALTERNATIVE_WINDOW`, and `REQUEST_UNCHANGED`.

Two reason codes are renamed from the SRD. `HIGHER_PRIORITY_TASK_INSERTED` becomes `DISPLACED_BY_COMPETING_REQUEST`, because priorities run 1 to 5 and an emergency request ties with any existing priority 5 request, winning on the deadline tiebreak rather than on priority. A code that says a request lost to higher priority would misstate the mechanism it exists to record. `TASK_UNCHANGED` becomes `REQUEST_UNCHANGED` to match the glossary.

`SATELLITE_UNAVAILABLE` stays in the vocabulary although no MVP event produces it. The availability check is one of the SRD's six required constraints, a unit test drives it directly against a hand built state, and it becomes reachable the moment the deferred event lands. This differs from `PLAN_INFEASIBLE`, which was removed because raising it would actively discard information.

## Interfaces

### MissionSession

The single test seam. One in process facade over the whole loop. Integration tests drive this and not HTTP. See ADR-0001.

Methods: load a scenario from a file or an object; generate windows; plan; step forward by a number of seconds; inject an event; read the last impact; replan given the expected parent plan id; compare two plan versions; read the traces for a plan; read the metrics for a plan; reset.

Every method returns domain objects or plain serialisable structures. None returns an ORM row, a framework specific type, or anything shaped for React.

The session holds no state between HTTP requests. Every endpoint rebuilds it from the repositories, acts, and writes back. With in memory repositories this costs nothing, and when Postgres lands, restart survival comes free rather than as a rewrite. It also makes the session a function of persisted state, which is what replay needs.

### Planner protocol

One method taking a scenario, a mission state, a set of requests, and a set of windows, and returning a mission plan.

A planner never reads UI state, performs HTTP requests, queries live services, writes React facing structures, or mutates a previous plan.

`GreedyPlanner` is the only implementation in this build. It sorts requests by priority descending, then deadline ascending, then duration ascending, then id ascending. The id tiebreak is what makes the output deterministic. For each request it sorts candidate windows by the stability rule below, takes the earliest candidate action that passes validation, and otherwise records the request as unscheduled with a reason code.

The stability rule: a request's previous window comes first if that window is still valid, then the remainder by earliest start. This is what keeps plan churn meaningful.

A CP-SAT planner is deferred, but when it arrives it must satisfy this protocol with no changes to simulation, replanning, or UI code.

### WindowProvider protocol

One method taking a scenario and a set of requests, and returning a list of observation windows. `SyntheticWindowProvider` is the only implementation in this build. An `OrbitalWindowProvider` built on Skyfield or SGP4, reading static TLE files held in the repository, replaces it later. The core loop never calls a live TLE service.

### Constraint engine

Six independently callable checks: window containment, deadline, overlap, projected battery, projected storage, and satellite availability. Plus one aggregate that validates a whole plan.

Every check returns violations carrying a reason code and the offending request id. This matters because the explanation layer generates its text from these codes, so a check returning only a boolean makes its own failure inexplicable.

Validation covers unfrozen actions only. See ADR-0003.

### Repository protocols

One protocol per aggregate: scenarios, plans, events, impacts, traces, and mission states. In memory implementations back the whole sprint, and SQLAlchemy implementations arrive later against the same protocols.

Generated ids come from a per scenario sequential counter, producing `PLAN-001`, `ACT-002`, `TRACE-007`. The repository recovers each counter from the persisted records rather than holding it in memory, because sessions rehydrate on every request and an in memory counter would reset on restart and collide.

### REST API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/scenarios` | Create scenario |
| GET | `/scenarios/{id}` | Get scenario |
| POST | `/scenarios/{id}/windows/generate` | Generate observation windows |
| POST | `/scenarios/{id}/plan` | Generate initial plan |
| GET | `/scenarios/{id}/state` | Current mission state |
| POST | `/scenarios/{id}/simulation/step` | Advance simulation |
| POST | `/scenarios/{id}/events` | Inject event |
| GET | `/scenarios/{id}/impact` | Stored impact of the latest event |
| POST | `/scenarios/{id}/replan` | Generate next plan version |
| GET | `/plans/{id}` | Retrieve plan |
| GET | `/plans/{id}/metrics` | Metrics for one plan |
| GET | `/plans/{old}/compare/{new}` | Plan comparison |
| GET | `/plans/{id}/traces` | Decision traces |

Routes are thin. They validate, call the facade, and return a schema. Scheduling logic in a route handler is a defect against ADR-0001.

The API enforces the loop's order. Windows must exist before planning, a plan must exist before stepping, and a plan must exist before injecting an event. A call out of order returns `SIMULATION_STATE_ERROR`. This makes the OpenAPI schema teach the loop, and it keeps the impact record's evaluated plan id non-null.

The replan request carries the id of the plan version the caller believes is current. A mismatch returns `409` with `PLAN_VERSION_CONFLICT`. Sessions rehydrate per request, so two concurrent replans would otherwise both read Plan v2 and both write a v3, and a double click on the Replan button is enough to cause it.

Errors return an envelope carrying a code, a message, and a details object. The codes: `INVALID_SCENARIO`, `INVALID_EVENT`, `CONSTRAINT_VIOLATION`, `RESOURCE_NOT_FOUND`, `SIMULATION_STATE_ERROR`, and `PLAN_VERSION_CONFLICT`.

`PLAN_INFEASIBLE` is deliberately absent, though the SRD lists it. Greedy always returns a plan. When nothing fits it returns an empty plan with every request unscheduled and a reason code each, which is a valid plan with a utility of zero rather than a failure. Raising an error would discard the per request reasons in exactly the case where they matter most.

The OpenAPI schema FastAPI generates is the source of truth for the frontend types.

### Frontend components

`ScenarioControls`, `MissionMap`, `MissionStatePanel`, `EventPanel`, `PlanTimeline`, `PlanComparison`, `DecisionTracePanel`, and `MetricsPanel`.

React, TypeScript, and Vite. React-Leaflet draws the 2D map, Recharts draws the metrics, date-fns formats the timeline, and fetch or Axios calls the API.

The dashboard refetches only when the user acts and does not poll, because every state change originates in a button the user pressed.

The event panel selects a cloud block target through a request dropdown followed by a window dropdown populated from that request. Each timeline carries an unscheduled list beneath it showing the request id, priority, and reason code.

## Implementation decisions

### Resource model

The planner projects resources forward along the plan in time order. Each scheduled action deducts its energy and adds its storage. Validating an action checks the projected values at that action's start time, not the values as they stand now. Validating against current state alone would let five actions costing 20 Wh each all pass with 25 Wh remaining.

Battery never recharges. Idle drain is zero. Storage never frees, because this build has no downlink. Both resources move in one direction only, so battery at any time is a function of the set of actions scheduled before it, with no recharge rate to tune and no clock arithmetic in validation.

Resource accounting floors at zero.

### Freeze boundary

An action is frozen when its start time is at or before the current simulated time. This includes an action that started before an event and has not yet finished. Such an action completes as planned and charges its resources in full, because starting means committing.

The source SRD says "actions wholly in the past", which leaves the in flight case undefined. This spec supersedes it.

### Replanning strategy

Freeze every started action. Apply the event's effects to state, windows, and requests. Rebuild every unfrozen action from scratch, drawing on every unexpired unfrozen request, including ones the previous plan dropped and ones an event introduced. Merge with the frozen actions. Validate the unfrozen part. Create plan version N plus 1. Compute the comparison, generate the traces, and calculate the metrics.

Rebuilding uses the stability rule described under the planner protocol. A plain rebuild would give every unaffected request a new start time purely from rerunning greedy, so churn would measure the planner's variability rather than the disruption. A separate repair path was rejected because it duplicates planner logic and interacts awkwardly with greedy ordering.

Replanning with no event injected is valid and produces a new version like any other. Given the stability rule, that version should match its parent apart from the version number and the timing measurement.

### Simulation lifecycle

`reset` returns the session to the moment of load, clearing plans, events, traces, and impacts along with the clock and resources. A partial reset would produce a state that no scenario and event log pair can reproduce.

The clock cannot advance past the scenario's end time. A step that would cross it clamps at the end, marks the mission complete, and rejects further steps with `SIMULATION_STATE_ERROR`.

### Request expiry

The simulation marks a request expired the moment the clock passes its deadline with no completed action. Expiry is permanent, and replanning excludes expired requests from the planning problem. Marking at step time keeps one truth in one place, and offering an expired request to the planner would produce a deadline violation for something already dead.

Expiry is visible through the request's own status. A decision trace for expiry is deferred, because `DecisionTrace` requires a plan id and an expiry happens during a step rather than during a replan.

### Event engine

Injecting an event changes domain state, records the event, and writes an impact record. It never triggers the replanner. Keeping the two operations apart is what makes the demo's cause and effect readable.

The emergency event carries its windows explicitly rather than calling the `WindowProvider` at injection time, so that the event log alone reconstructs the mission.

### Impact analysis

Two classes, valid and invalid. There is no third. The SRD proposes `AFFECTED` but never defines it apart from `INVALID`, and since replanning rebuilds every unfrozen action, a third class would drive no behaviour and earn no distinct reason code.

The system computes the impact at injection and stores it. Computing on demand would return different answers depending on when the user called it, because stepping and replanning both change the state it depends on.

### Metrics

Mission utility is the sum of priorities across the deduplicated set of requests a plan schedules or has already completed. A request counts once whether it is scheduled, completed, or both.

Plan churn counts unfrozen actions that changed between two plan versions, divided by the count of unfrozen actions in the earlier plan. Explanation coverage counts changed actions carrying a trace, divided by changed actions. Both denominators reach zero in reachable states, and both return null there. Returning 1.0 for a vacuous coverage would be defensible arithmetic and a misleading headline, since 1.0 is the exact number the demo quotes as evidence of explainability.

Every metrics result carries the request pool it was computed over. The comparison flags any comparison whose two sides used different pools, which is what makes the emergency request demo honest about why utility rose. Expired requests stay in the pool and count against the completion rate.

### Explanation

Reason codes are authoritative and text is presentation. Messages render from templates keyed by reason code and filled with trace data. No language model takes part, and the system must work with none present.

### Determinism

The build draws no random numbers. Windows come from scenario configuration, the constraint functions are pure, and greedy ordering ends in an id tiebreak. `AMIS_RANDOM_SEED` is removed from the environment, because a configuration value that controls nothing is worse than no value.

Deterministic sequential ids raise the reproducibility claim from "the same plan" to "the same output", so a test can diff two entire runs. Creation timestamps and timing measurements stay wall clock and real, and every equality assertion excludes them.

### World Monitor as a UI reference

Patterns only. No copied code and no copied assets. World Monitor is AGPL-3.0-only, and copying code would impose copyleft on the whole AMIS repository including the backend.

Adopted: one operational screen with no navigation; a panel registry so panels mount independently; a map with correlated side panels where selecting an entity highlights it elsewhere; a dense dark console theme; and a chronological event column, which becomes the decision trace panel.

Not adopted: the dual 3D and 2D map engines built on globe.gl, deck.gl, and Three.js; Tauri desktop packaging; multi variant site builds; multi tier Redis and CDN caching; the MCP, SDK, and CLI interfaces; and every live external feed.

World Monitor is cited as a product reference, not a research basis, and no part of the AMIS research claim depends on it.

### Team split

Member 1 takes domain, the simulator, windows, and the event engine. Member 2 takes constraints, the planner, the replanner, and metrics. Member 3 takes the React dashboard, timeline, map, and comparison UI. Member 4 takes FastAPI, PostgreSQL, Docker, and the integration tests.

The domain models and the API contract get agreed and frozen before parallel work starts. Without that, integration consumes the sprint.

### Infrastructure

Docker Compose with frontend and backend for the sprint. Postgres joins in the same commit that adds the repositories, because a database service nothing connects to invites an hour of investigation into whether persistence is wired.

No Kubernetes and no microservices. The environment holds `AMIS_ENV`, and `DATABASE_URL` arrives with postgres. Nothing needs an API key.

## Build phases and acceptance

Phases run in order. The loop must work from tests before the API exists, and from the API before the dashboard exists. If day 1 ends with no valid plan printing at the command line, frontend work does not start.

### Phase 1: domain models

Build every entity and enumeration in the data model section.

Acceptance: a test constructs a complete scenario, serialises it to JSON, deserialises it, and every value survives. No module outside persistence imports SQLAlchemy.

### Phase 2: mission state and simulation lifecycle

Build the clock, state advancement, resource accounting, the end of mission clamp, and reset.

Acceptance: the same scenario and step sequence produce an identical final state across repeated runs. Stepping past the scenario end clamps the clock, sets the mission complete flag, and a further step raises `SIMULATION_STATE_ERROR`. Reset returns every field to its loaded value.

### Phase 3: observation windows

Build the `WindowProvider` protocol and the synthetic implementation.

Acceptance: every demo request has at least one window, `OBS-B` has two, and two runs of the same scenario produce identical windows.

### Phase 4: constraint engine

Build the six checks and the plan aggregate.

Acceptance: one passing and one failing unit test exists for every check, written before the planner. Every failure returns a violation carrying a reason code and a request id. The aggregate skips frozen actions.

### Phase 5: greedy planner

Build the `Planner` protocol and `GreedyPlanner`, including the stability rule.

Acceptance: with five to ten requests, one satellite, multiple windows, and binding resource limits, the plan has no overlapping actions, every action sits inside a valid window, no deadline is violated, resource constraints hold, unscheduled requests carry reason codes, and two runs produce identical output. A scenario where nothing fits produces an empty plan with a reason code per request rather than an error.

### Phase 6: metrics

Build utility, completion rate, violation count, planning time, and resource utilisation.

Acceptance: metrics for a plan return a serialisable object with no UI dependency, carrying the request pool size and id set.

### Phase 7: demo script

Build one module run as `python -m amis.demo` that drives the canonical loop through the facade and prints the plan, the comparison, the traces, and the metrics. This is the day 1 exit artifact.

Acceptance: the command loads the scenario, generates windows, produces Plan v1, validates it, and prints the plan and its metrics.

### Phase 8: event engine

Build the three event types one at a time, starting with `CLOUD_BLOCK`.

Acceptance: each event changes domain state correctly, records itself in the event log, and does not invoke the replanner. The scenario object is unchanged after every event.

### Phase 9: impact analyzer

Build the two class split and the impact record.

Acceptance: for the cloud demo, only the action using the blocked window becomes invalid. Every impact record names the plan it was evaluated against. Frozen actions appear in the frozen list and nowhere else.

### Phase 10: adaptive replanner

Build freezing, rebuilding, merging, validation, and versioning.

Acceptance: the cloud demo produces `OBS-B` at 10:20 in Plan v1 and at 11:15 in Plan v2, or drops it with `NO_ALTERNATIVE_WINDOW` if no window fits. Frozen actions are byte identical between versions. A replan naming a stale parent returns `PLAN_VERSION_CONFLICT`. A replan with no event produces an identical plan as a new version.

### Phase 11: plan comparison

Build the per request classification.

Acceptance: the cloud example returns `MOVED` for `OBS-B` with both timestamps. Comparison works between non adjacent versions. Reordering a plan's action list does not change the comparison.

### Phase 12: decision trace

Build the trace records and the template rendering.

Acceptance: every `MOVED`, `INSERTED`, and `DROPPED` result has a trace, and explanation coverage is 1.0 for the demo. No language model is imported anywhere in the codebase.

### Phase 13: replanning metrics

Build replanning time, churn, coverage, pool tracking, and the before and after comparison.

Acceptance: a single comparison object serialises for the frontend. Churn is near zero for the cloud demo. Churn and coverage return null when their denominators are zero. A comparison across two different request pools is flagged.

### Phase 14: REST API

Build the routers over the facade.

Acceptance: the entire mission flow runs through httpx integration tests. Every route is thin. Out of order calls return `SIMULATION_STATE_ERROR`. The generated OpenAPI schema documents every error code.

### Phase 15: PostgreSQL

Build SQLAlchemy repositories and Alembic migrations, and add postgres to Docker Compose.

Acceptance: restart the backend and Plan v1, the event, Plan v2, the impact, and the traces remain retrievable. Id counters recover from persisted records. No ORM object reaches the planner.

### Phase 16: frontend

Build the dashboard in the order load scenario, generate plan, initial timeline, mission state, inject event, replan, revised timeline, plan changes, explanations, metrics, then map.

Acceptance: a reviewer runs the complete demo from the browser without opening a terminal or the API documentation. One command starts the whole stack.

## Testing decisions

### What makes a good test here

A good test drives the loop through `MissionSession`, or calls a pure function through its public signature, and asserts on what comes back. Which requests got scheduled, at what start times, with which reason codes, what the comparison classified, what the metrics computed. It does not assert on call counts, internal call order, private attributes, or the shape of intermediate data.

The specific trap: a test that asserts the greedy planner iterated in a particular order rather than that it produced a particular plan. The ordering rule is an implementation choice that serves determinism, and the plan is the behaviour. When the CP-SAT planner arrives, every behavioural test should still mean something, and every test coupled to the implementation would need rewriting.

Planning and replanning times and creation timestamps are excluded from every equality assertion.

### Test layers

Integration tests through `MissionSession` are the primary layer and the one that proves the deliverable. The canonical test runs the whole loop end to end, with three variants covering the cloud block, the battery drop, and the emergency request.

Unit tests cover the pure logic: the constraint functions, with one passing and one failing case per rule written before the planner exists; plan comparison classification; metric calculations; reason code rendering; and domain model JSON round tripping.

API contract tests run through httpx ASGI transport and confirm that each route validates its input, calls the facade, and returns the documented schema and error codes. They test the adapter, since the facade tests already cover the loop.

Determinism tests run the same scenario twice and diff the entire output with the wall clock and timing fields removed.

### Required cases

The fourteen SRD cases, all at the facade unless noted. The planner schedules a feasible request, and rejects overlaps, missed deadlines, insufficient battery, and insufficient storage, each also covered by a unit test. A cloud event invalidates the correct window and action. A battery drop invalidates the unfrozen actions that no longer fit. An emergency request enters the remaining problem. Replanning leaves frozen actions untouched and creates a new version. Plan comparison identifies moved, inserted, and dropped correctly. Every changed action receives a trace, asserted as explanation coverage of 1.0. The same scenario produces identical results. Plan v2 passes validation.

Cases added by this spec. An action in flight when an event fires stays frozen and completes. A frozen action that a battery drop made unaffordable does not fail validation, and the battery floors at zero. A request untouched by an event keeps its previous start time, giving a churn of 0.0. Projected battery rejects the fifth of five actions that individually fit the current charge. A metrics comparison across two different request pools is flagged. Replanning with no event produces a new version identical to its parent. A replan naming a stale parent is rejected. Stepping past a deadline expires the request and the next replan ignores it. Stepping past the scenario end clamps and completes the mission. Churn and coverage return null when their denominators are zero. An impact record names the plan it was evaluated against. The scenario object is unchanged after an emergency event. Reset clears plans, events, traces, and impacts. Two runs of the demo scenario produce identical JSON once the wall clock and timing fields are removed.

### Prior art

None. The repository is empty, so this spec sets the conventions rather than following them. The backend uses pytest with pytest-asyncio and httpx. Frontend testing stays minimal, because the dashboard is a thin client over a fully tested API and component tests would compete with the research core for time.

### Fixtures

One canonical `scenarios/demo.json` holding `SAT-001` and `OBS-A` at priority 5 through `OBS-E` at priority 1, with `OBS-B` at priority 4 holding windows at 10:20 and 11:15. Two variants: one where battery is tight enough to drop exactly one low priority request, and one that injects a priority 5 emergency request that displaces something.

This spec does not pin the durations, watt hours, megabytes, or deadlines. Solving for values that produce a specific greedy outcome is far easier with a working planner than on paper, and numbers fixed on paper produce a spec that looks authoritative and does not run.

The fixtures are instead constrained by assertions. Plan v1 schedules `OBS-B` at 10:20. A `CLOUD_BLOCK` on `WIN-B-1` moves it to 11:15 with reason `WINDOW_INVALIDATED`, and churn stays near zero because no other request moves. The battery variant drops exactly one request, the lowest priority one, with `INSUFFICIENT_BATTERY`. The emergency variant schedules the new request and displaces at least one existing one. A fixture failing any of these fails the build.

## Further notes

The completion bar. The project is not complete because a dashboard renders. It is complete when the closed loop runs end to end, repeatably, offline. Every scoping decision above resolves in favour of that loop.

The seam choice does real work. Putting the one seam at `MissionSession` rather than at HTTP is what lets days 1 and 2 be test driven at all, since the API does not exist until day 3. It also makes the SRD's planner independence rule enforceable rather than aspirational.

Determinism is a property the design pays for. The id tiebreak, the synthetic windows, the absence of randomness, the sequential ids, and the exclusion of timing fields from equality all buy one thing: the same scenario produces the same answer, and a reviewer can diff two saved runs.

Reason codes come before prose. The explanation layer is the project's stated novelty, and it holds up only because every message renders from a code that the constraint functions and the impact analyzer produced. This is why the constraint checks return violations rather than booleans, and why they get built before the planner. Reversing that order would make the explanations reverse engineered guesses.

Deviations from the source documents, in one place. `AFFECTED` is dropped from impact analysis. `PLAN_INFEASIBLE` is dropped from the error codes. `HIGHER_PRIORITY_TASK_INSERTED` and `TASK_UNCHANGED` are renamed. `TaskStatus` becomes `RequestStatus`. The freeze boundary covers in flight actions rather than only past ones. Validation skips frozen actions. Metrics move from the scenario to the plan. An impact endpoint is added. A plan version conflict code is added. `AMIS_RANDOM_SEED` is removed. Each deviation is argued where it appears above.

The AGPL boundary. World Monitor is AGPL-3.0-only. The decision is patterns only, with no code and no assets copied. If someone later wants to lift a component or a stylesheet, that is a licensing decision about the whole repository rather than a frontend convenience, and it needs an explicit call before the copy happens.

Research framing. AMIS is a student research prototype. Published ISRO mission operations material and NASA and JPL work on increasingly autonomous spacecraft inspired it. It is not an ISRO product and claims no operational readiness. The gap it addresses is the integration layer, combining event driven replanning, operator facing explanation, and reproducible benchmarking in one system, rather than any single algorithm.
