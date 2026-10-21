# C: Fair multi-requester tasking

Status: local specification; implementation pending.
Source: AMIS world-impact feature research, section C; current Planner selection and deterministic solving follow ADR-0009.
The requester asked for this specification in the local world-impact folder. No external issue is created. The fairness definition and objective ordering below are proposed defaults, not previously approved stakeholder policy. Verification seams were confirmed by the requester.

## Problem Statement

Operators sharing Satellite capacity cannot identify how mission service is distributed between requesters. A total-priority objective can favor the requester submitting the most high-priority ObservationRequests, and current explanations cannot distinguish a deliberate sharing decision from a timing or resource failure.

## Solution

Identify requesters explicitly, show their demand and served utility, and offer an opt-in CP-SAT fairness policy. Keep ordinary planning as the default. The proposed first policy balances requester utility among solutions with the same best proven mission utility, while preserving executed actions and explaining any fairness-driven changes. Display the chosen policy, its limits, and its effect alongside existing utility, churn, and response metrics.

## User Stories

1. As a scenario author, I want an optional requester identity on an ObservationRequest, so that shared capacity can be attributed.
2. As a scenario author, I want emergency arrivals to carry the same identity, so that later demand remains attributable.
3. As a maintainer, I want absent requester fields omitted from serialization, so that old Scenarios and events remain compatible.
4. As an operator, I want requested and served utility per requester, so that unequal demand is visible alongside unequal service.
5. As an operator, I want an explicit unattributed category, so that missing identities are not silently assigned to an organization.
6. As an evaluator, I want a documented fairness measure, so that the reported number has a precise meaning.
7. As an evaluator, I want zero-service requesters included, so that fairness does not hide excluded participants.
8. As an evaluator, I want frozen and completed work counted once, so that replanning does not erase previously delivered service.
9. As an operator, I want fairness selectable, so that the simulator does not silently change what a good MissionPlan means.
10. As an operator, I want ordinary Greedy and CP-SAT behavior preserved by default, so that existing comparisons remain interpretable.
11. As an operator, I want mission utility protected before balancing, so that the first policy has a clear tradeoff boundary.
12. As an evaluator, I want solve-stage status and fallback recorded, so that bounded search is not presented as proven fairness.
13. As a trainee, I want fairness-driven changes explained by a specific ReasonCode, so that I can understand why a request moved or lost service.
14. As an operator, I want frozen actions preserved, so that sharing policy cannot rewrite execution history.
15. As an evaluator, I want historical-plan membership respected, so that future arrivals cannot change earlier demand totals.
16. As a dashboard user, I want utility, service share, demand, and policy displayed together, so that a balanced-looking chart is not misleading.
17. As a scenario author, I want cases with unequal request sizes and infeasible demand, so that fairness limitations are observable.
18. As an auditor, I want policy configuration preserved after restart, so that plan reconstruction does not silently revert objectives.
19. As an evaluator, I want deterministic reruns, so that differences reflect policy rather than random search.
20. As a trainee, I want fairness and emergency-response results side by side, so that I can see whether balancing affects urgent service.

## Implementation Decisions

### Request identity and attribution

- Add optional `requester_id` to ObservationRequest, scenario/API input schemas, emergency-arrival schemas, persisted request snapshots, and frontend types. Omit it when absent. When supplied, require a nonempty string without leading/trailing whitespace; do not silently merge case-distinct identities.
- Identity is a Scenario author's attribution label, not authentication, authorization, billing, nationality inference, or a guarantee of equal entitlement. Do not infer requester identity from geography or Cue source.
- Manual and generated emergency arrivals can carry requester identity through their explicit author profile. Existing Cue artifacts without it retain their meaning. Coordinate with A3's profile extension if both slices are in progress.
- Keep attribution on ObservationRequests and immutable plan RequestPool snapshots. Do not retrofit historical plans using the current live RequestPool.

### Metrics policy

- Proposed metric version `requester-utility-v1`: utility is the sum of each uniquely served ObservationRequest's priority, following the existing mission-utility imaging/completion semantics. Count each request once across completed, frozen, and currently planned imaging. Downlink actions contribute no requester utility.
- For each identified requester in the selected plan's RequestPool, report request count, demand utility, served request count, served utility, service share of all served utility, and fulfillment ratio of served utility to demand utility. Preserve the existing plan/current-state `measured_at` convention and disclose it.
- Demand includes expired and currently infeasible requests in that plan's membership; do not improve reported fairness by dropping them from denominators. A requester with no service remains a row with zero served utility.
- Report unattributed demand and service separately. Include unattributed service in the all-requester service-share denominator, but exclude the unattributed category from fairness optimization and the identified-requester fairness gap. State this scope in the response and dashboard.
- Fairness gap is maximum identified-requester served utility minus minimum identified-requester served utility. Return null with fewer than two identified requesters. With two or more and zero service, return gap zero accompanied by zero-service counts; never label that as successful equitable service.
- Service shares are null when total served utility is zero. Fulfillment ratios use positive demand utility. Sort rows by requester id and keep numeric counts/units explicit.
- Absolute utility balance does not normalize by demand, capability, or entitlement. Show demand and fulfillment ratios to expose that limitation. No fairness metric is presented as a universal ethical score.

### Opt-in planning policy and determinism

- Add explicit policy selection through the existing MissionSession planning-selection boundary and thin API/UI adapters. Proposed modes are `utility` (existing default) and `utility_then_fairness` (CP-SAT only). Reject unsupported combinations with Greedy rather than silently ignoring policy.
- Preserve the Planner protocol where practical by configuring the selected Planner instance. Record the chosen policy and version on each MissionPlan and retain the effective selection across session persistence/reconstruction. Older stored plans without policy metadata mean existing utility behavior.
- An ADR must approve the new objective order and its interaction with ADR-0009 before implementation is considered complete. Proposed order: maximize total priority utility; among solutions with that proven maximum, minimize the requester utility gap; among equally fair solutions, prefer the existing stability objective. Keep all existing feasibility/resource constraints and frozen-action rules.
- Solve in deterministic stages with the existing single worker, fixed seed, deterministic work budget, and documented candidate ordering. Allocate a fixed total deterministic budget across stages rather than giving each stage an unbounded new allowance.
- Begin fairness optimization only when the primary utility optimum is proven. Otherwise retain the validated utility-stage/baseline result and report fairness as not optimized because primary optimality was unproven. A later stage must never reduce the fixed primary utility.
- Count authoritative completed and frozen request utility as constants in each requester's balance. Do not double-count frozen actions as new choices. Identified requesters with infeasible demand remain in the objective population, even if this limits improvement.
- If no meaningful comparison exists (fewer than two identified requesters), skip the fairness stage with an explicit reason. If no secondary solution is found, retain the last validated plan and disclose the stage failure. Never label a utility fallback as fairness-optimal.
- Retain the existing guarantee against utility below the validated Greedy baseline. Extend solver details with policy version, stage objectives/status/bounds, budget allocation, fairness population, achieved gap, stability result, and fallback/skip reason. Bounds and gaps must identify their objective and must not mix utility and fairness units.
- Fairness can change more actions than utility-only planning because stability is a later objective. Make this visible in PlanDiff and churn rather than silently imposing an undocumented churn cap.

### Explanation, frontend, and acceptance

- Add `REBALANCED_FOR_REQUESTER_SHARE` with a clear DecisionTrace template naming the affected requester and the policy tradeoff.
- Derive fairness causality from the retained pre-fairness solution versus the final solution within the staged solve. Persist sufficient attribution to reproduce the trace. A fairness-enabled plan alone is not proof that every changed request moved for fairness; retain ordinary constraint reasons where they apply.
- Show per-requester demand, served utility, service share, fulfillment, zero-service state, and unattributed totals. Display policy and solve-stage limitations beside the fairness gap. Refresh on replan, clock advance, reset, historical-plan selection, and reload using backend metrics.
- Add a documented comparison Example where equal-total-utility solutions have different requester balance, plus a case where utility-first policy cannot improve balance. Compare against ordinary modes using unchanged mission utility, churn, and B response definitions.
- Acceptance requires compatible optional identity serialization, exact metric denominators, correct frozen/completed accounting, deterministic opt-in policy, honest stage/fallback reporting, causal traces, and persisted policy selection. Ordinary mode must retain its established behavior.

## Testing Decisions

- Use the confirmed MissionSession seam for planning-mode selection, emergency attribution, request snapshots, frozen/completed work, metrics, staged results, traces, persistence, and deterministic replay/reruns.
- Prefer externally visible comparisons: equal utility with different gap, unequal demands, impossible demand, unattributed work, no service, fewer than two requesters, expired requests, historical-plan isolation, and solver fallback. Do not assert private variable or constraint construction.
- Prior art is existing planner-comparison evaluation, CP-SAT determinism/fallback checks, frozen-action replan checks, plan metrics, and emergency persistence tests. A small bounded fixture should distinguish the policies without relying on wall-clock timing.
- API checks cover policy/requester validation and metadata compatibility; dashboard checks cover denominator labels, zero/null states, policy limits, and lifecycle refresh. No test work is performed as part of writing this specification.

## Out of Scope

- Utility sacrifice to obtain fairness, configurable entitlements/weights, demand-normalized optimization, rolling quotas, cross-Scenario accounting, authentication, billing, or requester-specific reservations.
- Greedy fairness heuristics, hidden fairness defaults, a universal fairness score, and changes to emergency priority or latency definitions.
- Other world-impact features. If D later adds archive fulfillment, it must keep new-acquisition utility separate from archive fulfillment in these metrics.

## Further Notes

- C can be implemented independently of A3, E, and D. It requires an ADR because it changes the meaning of the selected planning objective.
- The utility-first policy intentionally improves balance only within maximum-utility solutions. It does not resolve every concern raised by the research; broader efficiency/fairness tradeoffs require a separate, explicit policy proposal.
- Policy selection must be captured wherever the existing application stores per-run planning choices. Do not claim that event-only replay can reconstruct a new objective unless its configuration is also retained through the established Scenario/run reconstruction contract.
