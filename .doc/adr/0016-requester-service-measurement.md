# Requester attribution and acquisition utility

Ticket C-01 introduced measurement. Ticket C-02 adds selectable fairness-aware
planning while preserving existing utility-first defaults.

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

## Objective order and ADR-0009 interaction (Ticket C-02)

Planning policy selection is opt-in per run (`utility` or CP-SAT-only
`utility_then_fairness`). `utility` remains the default for both Greedy and
CP-SAT. Unsupported policy combinations with Greedy are rejected explicitly.
`MissionPlan` records `planning_policy` and `policy_version` (`requester-utility-v1`),
which survive session persistence and reconstruction; legacy plans without
metadata default to ordinary `utility`.

CP-SAT executes deterministic solve stages with `num_search_workers = 1`,
fixed seed `random_seed = 0`, stable candidate ordering, and a fixed total
deterministic work budget (`max_deterministic_time`) allocated across stages:

1. **Stage 1 (Primary utility):** Maximize total priority utility under all
   established feasibility, geometry, and frozen-action rules.
2. **Stage 2 (Fairness balancing):** Start balancing only when the primary
   utility optimum is proven (`OPTIMAL`). Hold primary utility fixed as an exact
   equality constraint. Minimize the identified-requester utility gap (`max_u - min_u`),
   counting completed and frozen imaging as constants without double-counting.
   Identified requesters with infeasible demand remain in the population. If
   fewer than two identified requesters exist, skip balancing explicitly.
3. **Stage 3 (Stability preference):** Fix the proven or feasible gap from
   Stage 2 and maximize the existing stability preference (preserving previous
   action windows and penalizing off-peak culmination).

If primary optimality is unproven or fewer than two identified requesters exist,
balancing is skipped with an explicit reason, retaining the validated Stage 1
result. If a later stage fails, the last validated result is retained. The
Greedy utility floor guarantee from ADR-0009 is strictly preserved; bounded
feasible or fallback plans are never labelled as proven fairness optima.

Solver details record policy, version, fairness population, stage statuses,
stage objectives/bounds with separate labelled units (`priority_utility`,
`priority_utility_gap`, `retained_window_count`), budget allocation, achieved
gap, stability result, and skip/fallback reasons.

Decision traces assign `ReasonCode.REBALANCED_FOR_REQUESTER_SHARE` only where
retained pre-fairness versus final placements establish causal rebalancing for
requester share at equal utility. Unrelated changes retain their ordinary
constraint or displacement reasons.
