# 01: Attribute and display requester service

**What to build:** A scenario author attributes initial and emergency ObservationRequests to requesters, and an evaluator inspects each requester's demand, served utility, fulfillment, and fairness gap in API metrics and the dashboard without changing planning behavior.

**Blocked by:** None (can start immediately from the delivered A1+B baseline).

**Status:** implemented

**Governing specification:** [Fair multi-requester tasking](spec.md).

**Branch independence:** Implement on the C feature branch without A3, E, or D. Extend the existing USGS/manual authoring and imaging-profile contracts directly; do not require CEMS support. Archive-satisfaction status or metrics are not a prerequisite.

- [x] Record the requester metric definition and its limits in the feature ADR: acquisition utility is unique served request priority; the proposed gap is maximum minus minimum identified-requester served utility.
- [x] Add optional `requester_id` consistently through ObservationRequest creation, Scenario/API inputs, manual emergency arrivals, developer imaging profiles, generated inputs, persisted request snapshots, and frontend types. Omit it when absent and preserve older inputs/artifacts.
- [x] Require a nonempty identity without surrounding whitespace, preserve case distinctions, and do not infer requester identity from coordinates or Cue source. Expose attribution in existing authoring/inspection flows.
- [x] Metrics return stable requester rows with request count, demand utility, served count/utility, service share, and fulfillment ratio for the selected plan's RequestPool membership.
- [x] Count completed, frozen, and currently planned imaging once per request according to existing mission-utility semantics. Downlinks add no requester utility; later arrivals must not leak into historical demand membership.
- [x] Keep expired/infeasible demand and zero-service requesters visible. Report unattributed demand/service separately; include it in total-service shares but exclude it from the identified-requester fairness gap.
- [x] Return null gap with fewer than two identified requesters, null service shares with no served utility, and a zero-service indicator when a zero gap accompanies no service. Show denominators and the current `measured_at` convention explicitly.
- [x] Dashboard presentation shows demand, served utility, share, fulfillment, unattributed totals, and fairness scope/limitations together, refreshing after arrival, replan, clock advance, historical-plan selection, reset, and reload.
- [x] Persistence/reconstruction and serialization preserve attribution and selected-plan snapshots. Existing default Greedy/CP-SAT planning, mission utility, churn, and B response semantics remain unchanged.
- [x] Verify the confirmed MissionSession metrics/lifecycle seam with unequal demand, no service, infeasible/expired requests, unattributed work, completed/frozen deduplication, historical membership, and persistence; add focused API/dashboard contract checks.

**Delivery boundary:** Completes useful requester attribution and measurement. Objective changes, policy selection, and fairness-specific causal traces belong to C-02.

## Validation

- Backend: `.venv/Scripts/python.exe -m pytest -q` - 485 passed.
- Frontend: `npm test` - 202 passed; `npm run build:bundle` passed.
- TypeScript: `npx tsc -b` passed. Python mypy reports 30 existing errors
  versus 32 at the starting commit; no new errors. Frontend lint has three
  existing warnings and no errors.
- SQLite migration 0005 to 0006 and back passed; attributed initial and emergency
  requests and historical requester metrics survived SQL reconstruction.
- Separate standards and C-01 specification reviews returned no findings.

The fairness planning policy and causal traces remain ticket C-02 work.
