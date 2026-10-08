# 04: Report planned and achieved emergency response

**What to build:** An evaluator can compare planned and actual emergency imaging response through the plan-metrics API, dashboard, and mission timeline. Every eligible arrival remains visible, including unserved and expired requests, and actual acquisition history survives replans and reconstruction.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

## Planned response and dashboard

- [ ] Metrics include all accepted `EMERGENCY_TASK` arrivals belonging to the selected MissionPlan's RequestPool, including evidence-free manual arrivals, unscheduled arrivals, and permanently expired requests. Arrivals introduced after that plan are excluded.
- [ ] An `emergency_response` collection is ordered by arrival time then request identifier. Each row includes `request_id`, `event_id`, `arrival_time`, `request_status`, `planned_start_time`, `planned_latency_s`, and `planned_satellite_id`.
- [ ] Arrival time is the accepted MissionEvent's simulated time. Planned latency is the selected plan's imaging start minus arrival in seconds. Downlink actions never count.
- [ ] A selected plan with no imaging action for the request returns null planned acquisition fields. An expired, unserved request stays visible with expired status; absent service never becomes zero latency.
- [ ] Moving or dropping an unfrozen action updates planned start, latency, and satellite when measuring the corresponding plan. Historical-plan planned values remain tied to that selected plan.
- [ ] `time_to_first_acquisition_s` is the arithmetic mean of non-null planned latencies. `emergency_request_count` counts all eligible rows and `planned_emergency_request_count` counts non-null planned latencies. An empty denominator gives a null mean. No emergency arrivals gives an empty collection, zero counts, and a null mean.
- [ ] Negative latency rejects the inconsistent event/action association with a diagnostic; it is never clamped to zero.
- [ ] The existing plan-metrics endpoint, serialized domain result, reconstruction path, and frontend types expose these fields. `measured_at` retains its existing meaning of selected plan plus current authoritative MissionState.
- [ ] The dashboard displays a clearly labelled planned mean with served and total counts, per-request planned values and satellite attribution, and explicit no-acquisition and expired states. It does not present future imaging as achieved response.
- [ ] Dashboard values refresh from the backend after injection, replan, clock advancement, reset, and reload. Existing mission utility, plan churn, explanation coverage, and other metric meanings remain unchanged.

## Achieved response and reconstruction

- [ ] Each existing `emergency_response` row adds `achieved_start_time`, `achieved_latency_s`, and `achieved_satellite_id`. They are null until the request's imaging action has actually started at or before the measured simulated clock.
- [ ] Execution is established using authoritative executed/frozen action history from the session and recorded plans. Comparing the clock against an arbitrary historical plan's proposed start is insufficient and must not fabricate an acquisition.
- [ ] Achieved latency is actual imaging start minus accepted arrival time in seconds. Downlinks do not qualify. Negative latency fails with a diagnostic rather than becoming zero.
- [ ] Achieved start, latency, and satellite remain stable after imaging completes and across later replans. Serialization, persistence-compatible session reconstruction, and replay retain that stability.
- [ ] `achieved_time_to_first_acquisition_s` is the arithmetic mean of non-null achieved latencies, and `achieved_emergency_request_count` is its denominator. A zero denominator returns null, and achieved and planned values never share a mean.
- [ ] The total eligible emergency count remains independent of whether requests are planned or achieved. Unserved and expired rows remain visible with null achieved fields unless an actual imaging start exists.
- [ ] Selected-plan membership and `measured_at` semantics remain intact. A historical plan can have different planned attribution from current authoritative achieved attribution; both are labelled explicitly.
- [ ] The existing API and frontend metrics contract expose the complete planned/achieved collection, both means, and all three counts. Existing saved sessions and manual emergency events remain compatible.
- [ ] The dashboard shows planned and achieved means separately with their respective counts and the total count, and shows per-request achieved satellite attribution. The UI explains that acquisition means imaging has started, not finished or downlinked.
- [ ] Injection, replan, clock advancement, reset, and reload refresh backend values. The browser does not infer execution from proposed action times. Reset clears achieved response with the reset mission history.

## Mission timeline

- [ ] Each eligible emergency response uses its backend arrival time to draw an arrival-to-planned-imaging segment when a planned start exists. The segment identifies the request and planned satellite and is explicitly labelled planned.
- [ ] Once the backend reports actual imaging start, an achieved segment uses the achieved start and satellite and is explicitly labelled achieved. The timeline explains that acquisition begins at imaging start.
- [ ] If selected-plan planned values differ from current achieved values, the presentation distinguishes both instead of silently replacing one with the other or using a historical proposal as proof of execution.
- [ ] Unscheduled requests show an explicit unserved/no-acquisition state. Expired requests retain their status. Neither state appears as a zero-width successful response or zero latency. Planned-but-unstarted requests remain planned.
- [ ] Timeline request/event links agree with backend identifiers and per-request response rows. Manual emergency arrivals participate without requiring cue evidence.
- [ ] Injection, manual replan, clock advancement, reset, selected-plan changes, and reload refresh segments from backend metrics. The browser does not derive achieved state merely by comparing its clock with plan times.
- [ ] Started acquisitions retain the same achieved segment across later replans and reconstruction. Historical-plan views exclude later arrivals according to the backend's selected-plan RequestPool membership.
- [ ] Segments do not duplicate on rerender or reload and do not count downlink actions as acquisition. Existing timeline styling, mission controls, and plan visualization remain usable.
