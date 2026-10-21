# Requester attribution and acquisition utility

Ticket C-01 introduces measurement only. Greedy and CP-SAT objectives,
mission utility, churn, and emergency-response semantics remain unchanged.
The optional fairness objective in C-02 requires a subsequent decision.

`requester_id` is an author's case-sensitive label, not an authenticated
identity or entitlement. It must be nonempty without surrounding whitespace.
Missing or null labels mean unattributed, and absent attribution is omitted
from request serialization. Geography and Cue source never supply identity.
Explicit developer imaging profiles propagate the label to generated requests.

Metric version `requester-utility-v1` counts each request's priority once if
it has imaging in the selected plan (including frozen actions), or appears
in the current mission state's completed set. Downlinks add no utility.
The selected plan's recorded RequestPool membership restricts both demand
and service, including when later arrivals have completed. Existing request
objects are immutable; status changes preserve attribution. Scenario and
accepted-event JSON preserve it through persistence and reconstruction.

Each identified requester remains visible, even with expired or infeasible
demand. Demand is summed priority; fulfillment is served utility / demand
utility. Service share is served utility / total served utility, including
unattributed service. Empty denominators yield null. The unattributed row is
separate and excluded from the gap, never merged with a literal label.

The proposed gap is maximum minus minimum identified-requester served utility,
null with fewer than two identified requesters. Zero gap with no service is
accompanied by a no-service flag and the count of identified requesters with
zero service. Absolute balance does not normalize demand, capability, or
entitlement and is not a universal ethical score. Planned acquisition utility
does not prove imagery was acquired or delivered.

`measured_at` remains the current simulated mission-state instant, even for a
historical plan: selected-plan membership and planned imaging are combined
with current completed work restricted to that membership. API and dashboard
disclose this convention, denominators, and limitations together.
