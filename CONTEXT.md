# AMIS

AMIS is a local simulator for Earth observation mission planning. It schedules observation work under timing and resource constraints, disrupts the mission with controlled events, rebuilds the schedule, and explains every change.

## Language

### Mission inputs

**Scenario**:
A complete, reproducible mission definition. It holds one satellite, a simulation start and end time, initial resources, and a set of observation requests.
_Avoid_: Mission, config, setup

**Satellite**:
The single spacecraft in a scenario. It carries a battery capacity and charge, a storage capacity and usage, and an availability flag.
_Avoid_: Spacecraft, asset, vehicle

**ObservationRequest**:
Something the user wants observed. It has a target coordinate, a priority from 1 to 5, a duration, a deadline, and resource costs. It never carries a start time.
_Avoid_: Task, job, observation, target, req

**RequestPool**:
The set of observation requests under consideration at one simulated instant. It is the scenario's requests plus every request an applied event introduced. Expired requests stay in the pool.
_Avoid_: Backlog, queue, task list, workload

**Expired**:
The property of an observation request whose deadline has passed in simulated time with no completed action. Expiry is permanent and no later plan may schedule the request.
_Avoid_: Missed, stale, timed out, lapsed

**ObservationWindow**:
A span of time during which the satellite could observe one request's target. A request may have several. A window carries a validity flag and, when invalid, the reason.
_Avoid_: Opportunity, slot, pass, visibility

### Planning

**ScheduledAction**:
One observation request placed into one observation window at a concrete start time. A planner produces these.
_Avoid_: Task, activity, booking, assignment

**MissionPlan**:
An immutable, versioned set of scheduled actions for one scenario. Each plan after the first names its parent.
_Avoid_: Schedule, timeline, plan version, itinerary

**Planner**:
A component that takes a scenario, a mission state, a set of requests, and a set of windows, and returns a mission plan. `GreedyPlanner` is the only one in the MVP.
_Avoid_: Solver, optimizer, scheduler

**Violation**:
A structured record that one scheduled action breaks one constraint. It carries a reason code and the offending request's id.
_Avoid_: Error, failure, conflict, breach

### Mission execution

**MissionState**:
A snapshot of the mission at one simulated instant. It holds the clock, battery, storage, satellite availability, active event ids, and completed request ids.
_Avoid_: Status, world state, context, snapshot

**MissionEvent**:
A disruption injected into a running mission at a chosen simulated time. The MVP supports a cloud block, a battery drop, and an emergency request arrival.
_Avoid_: Incident, disturbance, trigger, anomaly

**Frozen**:
The property of a scheduled action that has already started. Replanning may never move, drop, or recost a frozen action. An action is frozen when its start time is at or before the current simulated time.
_Avoid_: Locked, committed, past, historical

**Replan**:
The operation that takes the current plan and mission state, rebuilds every unfrozen action, and produces the next plan version.
_Avoid_: Reschedule, recompute, adapt, repair

**Impact**:
A stored record, written when an event is injected, naming the plan it was evaluated against and splitting that plan's unfrozen actions into valid and invalid.
_Avoid_: Damage, fallout, effect, consequence

### Explanation and measurement

**ReasonCode**:
A fixed identifier for why a planning decision came out the way it did. Reason codes are the authoritative record. Human readable text is generated from them.
_Avoid_: Cause, error code, tag, label

**DecisionTrace**:
A record linking one plan change to the event that caused it, the constraint it broke, the previous action, the new action, and a generated sentence.
_Avoid_: Log entry, audit record, history, explanation

**PlanDiff**:
A comparison of two mission plans, keyed by request id, classifying each request as unchanged, moved, inserted, dropped, or completed.
_Avoid_: Delta, comparison, changeset

**Mission utility**:
The sum of priorities across the deduplicated set of requests that a plan either schedules or has already completed.
_Avoid_: Score, reward, value, fitness

**Plan churn**:
The count of unfrozen actions that changed between two plan versions, divided by the count of unfrozen actions in the earlier plan.
_Avoid_: Instability, drift, volatility

**Explanation coverage**:
The count of changed actions carrying a decision trace, divided by the count of changed actions.
_Avoid_: Traceability, explainability score
