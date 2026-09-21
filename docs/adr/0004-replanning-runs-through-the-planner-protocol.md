# Replanning runs through the planner protocol

Replanning is the same `Planner.plan` call with the previous plan passed in, rather than a separate repair component. The build spec describes the protocol as taking a scenario, a mission state, a set of requests, and a set of windows. Those four still describe the planning problem. The previous plan and the two generated ids are additional arguments describing which plan record is being written, and they default so that an initial plan is the call with no previous version.

The planner needs the previous plan for two things it cannot derive from anything else. Frozen actions have to be carried forward unchanged and still occupy time against the rebuilt ones, and the stability rule needs each request's previous window so that it sorts first while it stays valid.

## Considered options

A separate repair path that patches only the affected actions was rejected. It duplicates the placement logic, and it interacts awkwardly with greedy ordering: repairing one request in isolation cannot see the contention its new placement creates.

Rebuilding without the stability rule was also rejected. Every unaffected request would take a new start time purely from rerunning greedy, so plan churn would measure the planner's variability rather than the disruption, and churn is one of the numbers the research claim rests on.

Leaving id generation inside the planner was rejected because a replan would restart the action counter and collide with the frozen actions it just carried over. Ids come from `amis/ids.py`, recovered from the records already stored, so they survive a session being rebuilt per request.

## Consequences

A CP-SAT planner still satisfies one protocol and needs no separate replanning implementation, which is what the deferred second planner was promised.

Because only frozen actions keep their ids across a version boundary, an earlier action missing from the later version is exactly one replanning rebuilt. `rebuilt_actions` reads the churn denominator that way rather than from the current simulated time, so a churn figure stays fixed once measured. Read against the live clock, the same pair of versions would report a shrinking churn as the mission ran on, and eventually report zero for a replan that demonstrably moved something. Id minting is therefore load-bearing: a planner that reused an unfrozen action's id in the next version would silently break the metric.

The frozen set is defined by start time, following `CONTEXT.md`, while a frozen action's cost is only charged to mission state once it has started. A replan issued at the exact instant an action begins therefore has a frozen action whose cost nothing has charged yet, and the planner commits that action to its resource projection rather than assuming mission state already covers it. Dropping that case overstates the remaining battery by the cost of the in-flight observation.
