# 05: Compare window-only feasibility

**What to build:** A duty officer can enter a point, imaging duration, deadline, and optional satellite in the dashboard and compare the earliest suitable observation window for every included satellite without submitting a request or changing the running mission.

**Blocked by:** None (can start immediately).

**Status:** implemented

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

- [x] A read-only MissionSession request-window operation shares existing orbital-provider behavior. `GET /scenarios/{scenario_id}/feasibility` accepts required `lat`, `lon`, `duration`, and `deadline` query inputs and optional `satellite_id`.
- [x] Validate finite coordinates within geographic bounds, finite positive duration in seconds, timezone-aware deadline after Scenario start, and optional satellite membership. Unknown scenarios use the existing not-found response; malformed inputs use existing API validation conventions. Unsupported non-orbital policies return a clear domain error.
- [x] Search begins at Scenario simulation start regardless of the current clock. Echo the search interval and return `scope: window_only`. The usable horizon ends at the earlier of Scenario end and candidate deadline.
- [x] Candidate generation uses stored Scenario orbital geometry, daylight and pointing policy, duration, deadline, and Scenario satellite availability. An internal ephemeral request identity cannot consume session identifiers.
- [x] Return one row per included satellite with `satellite_id`, `window_id`, `window_start`, `window_end`, `earliest_start`, and `latest_finish`. Optional satellite filtering returns only that satellite's row.
- [x] Select the earliest window that can contain the complete action under the Scenario's WindowPolicy, including culmination-start behavior. `earliest_start` is the policy-compatible start. `latest_finish` is the minimum of window end, Scenario end, and deadline. Proposed start plus duration cannot exceed it.
- [x] Returned window boundaries describe the selected window. A window that is long enough in total but cannot contain the action under culmination-start policy is unsuitable.
- [x] With no suitable window, all window/acquisition fields are null and `reason` is `no_suitable_window`. A satellite unavailable in the Scenario returns null fields and `reason: satellite_unavailable`. Satellites are never silently omitted for these conditions.
- [x] Suitable rows sort by earliest start then satellite identifier. Unsuitable rows follow, sorted by satellite identifier. Nullable `earliest_satellite_id` uses the same tie-breaker and is null when none is suitable.
- [x] Repeated queries preserve Scenario, MissionState, RequestPool, events, active-session windows, plans, traces, impacts, and identifier counters. The route does not save a changed session or reserve resources.
- [x] API schemas, frontend types, client access, and the dashboard candidate form support the complete response. The dashboard shows each satellite, earliest result, time basis, no-window/unavailable states, and existing validation errors.
- [x] The view explains that this is window-only feasibility. It excludes current plans and resources, pairwise slew, active outages, and reservations. It promises neither Planner selection nor resource-feasible action, and has no submit/reserve side effect.
- [x] Candidate results remain independent of mission-clock advancement and replan for an unchanged Scenario and input. Scenario changes, reset, and reload cannot leave another Scenario's result displayed as current.

## Verification

`tests/test_feasibility.py` covers the MissionSession and HTTP contracts, including a real offline orbital query, policy-compatible containment, deterministic ordering, availability, validation, and read-only behavior across clock advancement and replan. `frontend/src/panels/FeasibilityDialog.test.tsx` covers the dashboard through the real client with a mocked HTTP boundary, including filtering, validation errors, UTC seconds, and stale replies after candidate or Scenario changes.

The full backend suite passed 467 tests and the full frontend suite passed 191 tests. Frontend typechecking, production bundle build, and lint passed. The live dashboard returned an orbital comparison without creating a plan or submitting a request. Python typechecking still reports the same 47 errors as baseline commit `4a65837`, with no added errors.
