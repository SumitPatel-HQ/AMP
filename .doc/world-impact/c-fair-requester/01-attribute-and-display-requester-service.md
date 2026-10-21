# 01: Attribute and display requester service

**What to build:** A scenario author attributes initial and emergency ObservationRequests to requesters, and an evaluator inspects each requester's demand, served utility, fulfillment, and fairness gap in API metrics and the dashboard without changing planning behavior.

**Blocked by:** None (can start immediately from the delivered A1+B baseline).

**Status:** ready-for-agent

**Governing specification:** [Fair multi-requester tasking](spec.md).

**Branch independence:** Implement on the C feature branch without A3, E, or D. Extend the existing USGS/manual authoring and imaging-profile contracts directly; do not require CEMS support. Archive-satisfaction status or metrics are not a prerequisite.

- [ ] Record the requester metric definition and its limits in the feature ADR: acquisition utility is unique served request priority; the proposed gap is maximum minus minimum identified-requester served utility.
- [ ] Add optional `requester_id` consistently through ObservationRequest creation, Scenario/API inputs, manual emergency arrivals, developer imaging profiles, generated inputs, persisted request snapshots, and frontend types. Omit it when absent and preserve older inputs/artifacts.
- [ ] Require a nonempty identity without surrounding whitespace, preserve case distinctions, and do not infer requester identity from coordinates or Cue source. Expose attribution in existing authoring/inspection flows.
- [ ] Metrics return stable requester rows with request count, demand utility, served count/utility, service share, and fulfillment ratio for the selected plan's RequestPool membership.
- [ ] Count completed, frozen, and currently planned imaging once per request according to existing mission-utility semantics. Downlinks add no requester utility; later arrivals must not leak into historical demand membership.
- [ ] Keep expired/infeasible demand and zero-service requesters visible. Report unattributed demand/service separately; include it in total-service shares but exclude it from the identified-requester fairness gap.
- [ ] Return null gap with fewer than two identified requesters, null service shares with no served utility, and a zero-service indicator when a zero gap accompanies no service. Show denominators and the current `measured_at` convention explicitly.
- [ ] Dashboard presentation shows demand, served utility, share, fulfillment, unattributed totals, and fairness scope/limitations together, refreshing after arrival, replan, clock advance, historical-plan selection, reset, and reload.
- [ ] Persistence/reconstruction and serialization preserve attribution and selected-plan snapshots. Existing default Greedy/CP-SAT planning, mission utility, churn, and B response semantics remain unchanged.
- [ ] Verify the confirmed MissionSession metrics/lifecycle seam with unequal demand, no service, infeasible/expired requests, unattributed work, completed/frozen deduplication, historical membership, and persistence; add focused API/dashboard contract checks.

**Delivery boundary:** Completes useful requester attribution and measurement. Objective changes, policy selection, and fairness-specific causal traces belong to C-02.
