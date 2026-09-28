# AMIS

AMIS is a local simulator for Earth observation mission planning. It schedules observation work under timing and resource constraints, disrupts the mission with controlled events, rebuilds the schedule, and explains every change.

## Language

### Mission inputs

**Scenario**:
A complete, reproducible mission definition. It holds one or more satellites, a simulation start and end time, initial resources, and a set of observation requests.
_Avoid_: Mission, config, setup

**Satellite**:
One spacecraft in a scenario. A scenario may hold several, each with its own battery and storage resources, availability flag, and orbital elements.
_Avoid_: Spacecraft, asset, vehicle

**OrbitalElements**:
A dated description of one satellite's orbit, including its catalogue identity, normalized element fields, source, and checksum. A scenario stores its own copy.
_Avoid_: Live orbit, telemetry, current position

**WindowPolicy**:
The scenario's choice of window source and, for an orbital source, its pointing and daylight limits. It also carries the fixed settling time between observations, whether actions start at window culmination, the slew rate, and the sunlight recharge rate.
_Avoid_: Mode, generator settings

**Example**:
A reusable scenario template that creates a new scenario when loaded.
_Avoid_: Original mission, shared demo

**ObservationRequest**:
Something the user wants observed. It has a target coordinate, a priority from 1 to 5, a duration, a deadline, and resource costs. It never carries a start time. It may name a satellite, or leave assignment to the planner.
_Avoid_: Task, job, observation, target, req

**RequestPool**:
The set of observation requests under consideration at one simulated instant. It is the scenario's requests plus every request an applied event introduced. Expired requests stay in the pool.
_Avoid_: Backlog, queue, task list, workload

**Expired**:
The property of an observation request whose deadline has passed in simulated time with no completed action. Expiry is permanent and no later plan may schedule the request.
_Avoid_: Missed, stale, timed out, lapsed

**ObservationWindow**:
A span in which a request's target is observable under the scenario's window policy. It is computed per request and satellite pair and names its satellite. An orbital window is a visible time window that can hold an observation action; it may carry peak geometry and provenance.
_Avoid_: Opportunity, slot, pass, visibility

**Ground station**:
A catalogue entry with coordinates and an elevation mask (5 to 10 degrees) where the satellite can downlink. A mission opts in by listing station ids in its window policy.
_Avoid_: Antenna, gateway, ground site

**Contact window**:
A span in which one satellite is above a ground station's elevation mask, computed per satellite from its stored orbit with the same pass search as observation windows. Contacts are derived, never persisted; a communication outage marks overlapping contacts invalid.
_Avoid_: Pass, downlink window, visibility

### Planning

**ScheduledAction**:
One observation request placed into one observation window at a concrete start time (an imaging action), or one downlink action. A planner produces these; `kind` tells them apart.
_Avoid_: Task, activity, booking, assignment

**Downlink action**:
A request-less scheduled action spanning one contact window. It frees storage by downlink rate times duration when the contact ends, floored at zero. Downlinks are reservations re-derived on every plan, so plan diff, traces, and churn ignore them (ADR-0011).
_Avoid_: Dump, transmission task, playback

**Slew gap**:
The minimum time between two consecutive imaging actions: settling time plus the slew angle between their targets divided by the slew rate. It is pairwise, so it depends on which two targets are adjacent. The angle model is approximate (ADR-0013).
_Avoid_: Turn time, repointing delay

**Sunlight recharge**:
Battery energy gained at the recharge rate while the satellite is outside Earth's shadow, computed offline from the stored orbit and bundled ephemeris. The resource walk and the simulation clock both add it, capped at battery capacity. Missions without an orbit gain nothing (ADR-0013).
_Avoid_: Solar charging, power generation

**MissionPlan**:
An immutable, versioned set of scheduled actions for one scenario. Each plan after the first names its parent.
_Avoid_: Schedule, timeline, plan version, itinerary

**Planner**:
A component that takes a scenario, a mission state, a set of requests, and a set of windows, and returns a mission plan. `GreedyPlanner` and `CpSatPlanner` both implement it; a mission picks one per run by name (`select_planner`), and the choice is recorded on the plan as `planner_name`.
_Avoid_: Solver, optimizer, scheduler

**Solver details**:
The `solver_details` field a CP-SAT-backed plan carries: solver status, objective value and bound, optimality gap, whether the run fell back to the greedy baseline, and the library version and deterministic settings (single worker, fixed seed, time limit) it ran under. Absent on a greedy plan.
_Avoid_: Solver metadata, solve stats, debug info

**Violation**:
A structured record that one scheduled action breaks one constraint. It carries a reason code and the offending action's subject key: the request id for imaging, the action id for downlink.
_Avoid_: Error, failure, conflict, breach

### Mission execution

**MissionState**:
A snapshot of the mission at one simulated instant. It holds the clock, per-satellite battery, storage, availability, and completed sets with mission totals alongside, plus active event ids.
_Avoid_: Status, world state, context, snapshot

**MissionEvent**:
A disruption injected into a running mission at a chosen simulated time. The mission supports a cloud block, a battery drop, an emergency request arrival, a payload outage over an interval, and a communication outage that loses one station's contacts over an interval. A cloud block derived offline from archived weather carries its source, coverage, and threshold.
_Avoid_: Incident, disturbance, trigger, anomaly

**Weather archive**:
Committed raw hourly cloud responses with retrieval time and per-location checksums. The application never fetches weather; a developer script refreshes the archive and an offline threshold rule converts it into recorded cloud-block events.
_Avoid_: Live weather, forecast feed, nowcast

**Cloud sample**:
One normalized cloud-coverage fraction for one target at one time, derived from the weather archive. Samples inform the threshold rule only; the planner never sees them.
_Avoid_: Forecast point, weather reading

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
