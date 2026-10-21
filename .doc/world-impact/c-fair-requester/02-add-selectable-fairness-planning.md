# 02: Add selectable fairness-aware planning

**What to build:** An operator explicitly selects utility-first fairness planning, compares its service distribution with ordinary planning, and sees reliable solver-stage reporting and explanations of changes actually caused by balancing.

**Blocked by:** C-01 — Attribute and display requester service.

**Status:** ready-for-agent

**Governing specification:** [Fair multi-requester tasking](spec.md).

**Branch independence:** Continue the C branch after C-01. No A3, E, or D code, fixture, event, or merge is required. Fairness measures acquisition service only; future archive fulfillment must remain a separate additive measure.

- [ ] Extend the feature ADR with explicit objective order and ADR-0009 interaction: proposed maximum total priority utility, then minimum requester utility gap at that proven optimum, then existing stability preference.
- [ ] Expose `utility` and CP-SAT-only `utility_then_fairness` through MissionSession planning selection, thin API adapters, and dashboard controls. Default to existing utility behavior; reject unsupported Greedy combinations explicitly.
- [ ] Preserve the Planner protocol where practical through configured selection. Record effective policy/version on MissionPlans and retain selection through persistence/reconstruction; legacy missing metadata means ordinary utility policy.
- [ ] Use deterministic solve stages with one worker, fixed seed, stable ordering, and a fixed total deterministic work budget allocated across stages. Preserve resource/geometry constraints and frozen-action rules.
- [ ] Start balancing only after the primary utility optimum is proven. Hold that utility fixed during later stages. Otherwise retain the validated utility/baseline result and report the reason fairness was skipped.
- [ ] Include completed/frozen service as requester constants without double-counting; retain identified requesters with infeasible demand. Skip balancing explicitly when fewer than two identified requesters exist.
- [ ] Preserve the validated Greedy utility floor. If a later stage fails, use the last validated result; never describe fallback or bounded feasible results as proven fairness optima.
- [ ] Solver details identify policy/version, fairness population, stage statuses/objectives/bounds, budget allocation, achieved gap, stability result, and skip/fallback reasons with correctly labelled units.
- [ ] Add `REBALANCED_FOR_REQUESTER_SHARE` only where the retained pre-fairness versus final solution establishes causality. Persist sufficient attribution for stable DecisionTrace reconstruction; unrelated changes keep their ordinary reasons.
- [ ] Dashboard policy and result views show fairness limits, stage/fallback status, requester metrics, churn, and B response values. Preserve frozen history across replan and reload.
- [ ] Bundle small comparison Examples with equal utility but different attainable balance, and a case where utility-first policy cannot improve fairness. Verify deterministic reruns, fallback paths, historical behavior, and persistence through MissionSession, with focused API/dashboard checks.

**Delivery boundary:** Completes C. Excludes fairness through sacrificed utility, weighted entitlements, rolling quotas, cross-Scenario accounting, Greedy fairness heuristics, and hidden policy defaults.
