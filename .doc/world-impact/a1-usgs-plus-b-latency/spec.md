# A1 USGS cue replay plus B response latency and feasibility

Status: five-ticket breakdown approved. Tickets 01-04 are implemented; ticket 05 remains pending.
Source research: `.doc/reference/amis-world-impact-research.md`, sections A1 and B.
Scope confirmation: the requester approved A1+B first, A3 next, the priority/deadline policy, evidence-bearing emergency arrivals, and the full frontend/backend slice.

This is a local specification for `/to-tickets`. It has not been published to an external issue tracker. No application code or tests were written or run while refining it.

## Problem Statement

AMIS can introduce emergency requests and explain a replan, but it cannot replay a real earthquake alert with inspectable source evidence. It also cannot show how long an emergency request waits for imaging or answer which satellite has the earliest suitable observation window without changing the mission.

A disaster-management trainee needs to distinguish the real archived alert from AMIS assumptions about its priority, deadline, and imaging costs. An evaluator needs to distinguish planned response from response that has actually begun, including emergency requests that are never served.

## Solution

Add a developer-operated USGS archive pipeline that produces reproducible emergency-arrival inputs. A bundled Example uses a pinned earthquake, stored orbital inputs, a dated Scenario, and a recorded event script. The application runs offline and uses its existing injection, impact, replan, PlanDiff, DecisionTrace, and metrics loop.

Expose per-emergency-request response latency and clearly labelled aggregate metrics. Add a read-only query listing the earliest suitable observation window for each satellite. Show cue evidence, attribution, and planned versus achieved response in the dashboard.

## User Stories

1. As a developer, I want to archive a USGS GeoJSON response with its source URL, retrieval time, and checksum, so that the Example has reproducible evidence.
2. As a developer, I want archive integrity checked before normalization, so that corrupted data cannot produce mission inputs.
3. As a scenario author, I want earthquake longitude, latitude, event identifier, UTC event time, alert level, magnitude, and significance normalized, so that source data has one consistent interpretation.
4. As a scenario author, I want missing alert levels handled explicitly, so that an unset USGS value does not become invented source evidence.
5. As a scenario author, I want malformed coordinates, times, and alert levels rejected with a useful diagnostic, so that invalid inputs never enter the mission.
6. As a scenario author, I want repeated source identifiers handled deterministically, so that one earthquake cannot silently introduce duplicate requests.
7. As a scenario author, I want a visible priority/deadline policy, so that I can distinguish AMIS assumptions from USGS facts.
8. As a scenario author, I want to supply imaging duration and resource costs explicitly, so that earthquake severity does not invent satellite capabilities.
9. As a scenario author, I want cues checked against the Scenario time range, so that replay never silently changes a historical event's time.
10. As a trainee, I want a bundled earthquake Example with a briefing and matching dates, so that I can replay a real event offline.
11. As a trainee, I want to advance to the cue's exact simulated time and inject it, so that response latency has a faithful starting instant.
12. As a trainee, I want orbital windows recorded with the emergency arrival, so that replay does not regenerate them.
13. As a trainee, I want to inspect impact before choosing to replan, so that the existing injection/replan distinction remains visible.
14. As a trainee, I want the resulting PlanDiff and DecisionTrace, so that I can understand how the emergency request changed the MissionPlan.
15. As an auditor, I want manual emergency arrivals without evidence to keep working, so that existing scenarios and event logs remain compatible.
16. As an auditor, I want evidence preserved through serialization and persistence, so that a restarted application still explains the same source event.
17. As an auditor, I want replay to need only the pristine Scenario and recorded events, so that it does not depend on the original archive or network.
18. As a duty officer, I want one earliest suitable window per satellite, so that I can compare imaging times before submitting a request.
19. As a duty officer, I want satellites with no suitable window listed too, so that absence is not mistaken for an omitted satellite.
20. As a duty officer, I want feasibility clearly labelled as window-only, so that I do not mistake it for a reserved or resource-feasible action.
21. As a duty officer, I want invalid feasibility inputs rejected, so that an invalid candidate cannot produce misleading results.
22. As an evaluator, I want planned latency and satellite attribution for each emergency request, so that I can compare intended response.
23. As an evaluator, I want achieved latency only after imaging actually starts, so that future actions are not reported as real acquisitions.
24. As an evaluator, I want unserved and expired emergency requests retained in the results, so that successful requests do not hide poor service.
25. As an evaluator, I want separate planned and achieved means with their denominators, so that mixed or incomplete results remain interpretable.
26. As an evaluator, I want latency to update when an unfrozen action moves, so that metrics follow the selected MissionPlan.
27. As an evaluator, I want achieved latency to remain stable across later replans, so that an acquisition already begun cannot be rewritten.
28. As a map viewer, I want a cue marker linked to its request and event, so that I can inspect the alert's coordinates and evidence.
29. As a timeline viewer, I want an arrival-to-acquisition marker with a planned or achieved label, so that I can see response duration.
30. As a dashboard user, I want an explicit no-acquisition state rather than zero latency, so that unavailable service is not shown as immediate service.
31. As a dashboard user, I want the USGS credit and simulator-policy notice beside cue evidence, so that attribution and assumptions are visible.
32. As a maintainer, I want the existing Planner interfaces and ReasonCode-based explanations preserved, so that cue replay fits the established domain model.

## Implementation Decisions

### Architectural boundaries

- Respect ADR-0001's MissionSession facade, ADR-0002's immutable Scenario and recorded-event replay, ADR-0008's stored orbital inputs, ADR-0012's archive-then-replay boundary, and ADR-0014's per-satellite behavior.
- A Cue enters as the existing `EMERGENCY_TASK` wire event. No new EventType or Planner input is added.
- Network access belongs only in an explicit developer fetch operation. Normalization, event building, application startup, Example loading, and replay are offline.
- Add a cues module with archive loading, USGS normalization, and pure request/event-input generation. Use the existing weather pipeline as prior art without coupling the two domains' policy rules.
- Extend emergency payload serialization, validation, API schemas, and frontend types together. Extend metrics computation and persistence-compatible session reconstruction together.
- Add a read-only request-window method to MissionSession. The current emergency path calls its provider inline; a public request-window method does not yet exist. Share the provider behavior rather than calling the HTTP injection route for feasibility.
- Preserve the current explicit replan operation. Injecting a cue does not automatically create a new MissionPlan.

### Archive and normalization contract

- Store raw USGS response bytes with a manifest containing the source name, source URL, timezone-aware retrieval time, file identifier, and SHA-256 checksum. Do not rewrite an existing archive silently.
- Verify checksums before parsing. A missing manifest entry, missing raw response, or checksum mismatch fails the build operation with an actionable diagnostic.
- Normalize GeoJSON point coordinates as longitude then latitude. Depth is not an imaging coordinate. Require finite latitude in [-90, 90], longitude in [-180, 180], a nonempty source event identifier, and a valid epoch-millisecond event time converted to UTC.
- Accept USGS alert values red, orange, yellow, and green. Normalize an absent or null alert to the explicit evidence value `unknown`. Reject other alert strings rather than silently treating them as green.
- Magnitude and significance are optional finite numeric evidence. Missing magnitude does not apply the magnitude priority floor. Missing significance does not affect priority or deadline.
- Request identifiers are deterministic from source plus source event identifier. Exact duplicate normalized records collapse to one cue; conflicting records with the same identifier fail the build with a diagnostic. Source updates are not a new event type in this slice.
- Emit events in ascending event time with source and source event identifier as deterministic tie-breakers. Fixed input bytes and fixed policy produce the same output bytes, apart from a separately recorded fetch timestamp.
- Invalid selected records fail the build before output publication. A failed build does not leave a partially generated event script.

### Cue-to-request policy

| Normalized alert | Base priority | Deadline offset from earthquake time |
| --- | --- | --- |
| red | 5 | 12 hours |
| orange | 4 | 24 hours |
| yellow | 3 | 48 hours |
| green | 2 | 48 hours |
| unknown | 2 | 48 hours |

- Magnitude at least 6 raises priority to 5. It does not shorten the alert-based deadline.
- These values are AMIS simulation policy, not USGS recommendations or operational imaging commitments. Record the policy version in the generated artifact's metadata and describe the table in the cue-replay ADR.
- Request target coordinates come from the earthquake point. Request duration, energy cost, storage cost, and optional satellite assignment come from an explicit author-supplied imaging profile. The builder must not guess missing profile values.
- The profile uses existing ObservationRequest validation and is stored in the generated artifact. A nonempty descriptive target name may use source place text; it is not an identifier.
- One selected earthquake creates one request. No clustering, area tiling, or severity-driven resource-cost estimation is included.

### Event evidence and replay timing

- Evidence-bearing emergency payloads contain nonempty `source`, nonempty `source_event_id`, and normalized `alert_level` as an all-or-nothing group. Optional `mag` and `sig` are omitted when absent and require the core evidence group when present.
- An ordinary manual emergency payload may omit every evidence key. Its serialized shape remains unchanged. Partial evidence fails existing event validation with an actionable message.
- Generated cue inputs carry the earthquake UTC time as their intended injection time. MissionSession currently stamps events with its current simulated time. The Example runner must therefore advance to the exact cue instant before injection; it must not overwrite recorded time or silently inject late.
- Accept selected event times in the half-open Scenario interval from simulation start through, but excluding, simulation end. Reject out-of-range selections rather than clamping or shifting them. The author may explicitly select a smaller set before building.
- Orbital injection without supplied windows computes windows using the existing provider and records them in the accepted event. Persisted replay uses those recorded windows, including an empty set when there is no window.
- A generated developer input is not yet a persisted MissionEvent. Stable session-assigned event identifiers and recorded windows are produced on accepted injection.
- Re-injection of an already introduced request identifier fails using the existing duplicate-request validation. It must not add an event or alter resources, the RequestPool, or plan state.
- Frozen actions, permanent expiry, impact storage, and ordinary replan validation remain governed by existing behavior. A cue with no feasible action is a legitimate emergency arrival, not a pipeline failure.

### Response-latency contract

- Include all accepted `EMERGENCY_TASK` arrivals, including manual arrivals without cue evidence. Include only emergency request identifiers belonging to the selected plan's RequestPool; later arrivals must not leak into earlier-plan results.
- Use the accepted MissionEvent's simulated time as the arrival time. Latency is imaging start minus arrival in seconds; downlink actions never count.
- Add an `emergency_response` collection ordered by arrival time and request identifier. Each entry contains `request_id`, `event_id`, `arrival_time`, `request_status`, `planned_start_time`, `planned_latency_s`, `planned_satellite_id`, `achieved_start_time`, `achieved_latency_s`, and `achieved_satellite_id`.
- Planned fields come from the request's imaging action in the selected MissionPlan. They are null when that plan does not schedule it. Moving or dropping an unfrozen action changes these fields accordingly.
- Achieved fields are populated when the simulation has actually started the imaging action, at start time less than or equal to the measured clock. They remain populated after completion. Use authoritative executed/frozen action history from the session and recorded plans; do not infer execution merely by comparing the clock with an arbitrary historical plan's proposed start.
- Achieved start and satellite remain stable across replans. Acquiring an image here means imaging has started, not that it has finished or been downlinked. Label that meaning in the UI.
- `time_to_first_acquisition_s` is the arithmetic mean of non-null planned latencies. `achieved_time_to_first_acquisition_s` is the arithmetic mean of non-null achieved latencies. Each returns null when its own denominator is zero. Do not substitute zero for unscheduled or unstarted requests and do not mix planned and achieved values in one mean.
- Add `emergency_request_count`, `planned_emergency_request_count`, and `achieved_emergency_request_count`. Show denominators with means so that a fast mean over one served request cannot hide many unserved requests.
- No emergency arrivals yields an empty collection, zero counts, and null means. An expired, unserved request stays in the collection with null acquisition fields and its expired status.
- Preserve `measured_at` semantics: metrics combine the selected plan with current authoritative MissionState, as existing metrics do. Historical-plan planned values may differ from current achieved values; the response and UI must distinguish both.
- Negative latency is an inconsistent event/action association and must not be clamped into a valid-looking zero. Reject the inconsistent calculation with a diagnostic.
- Expose these fields through the existing plan-metrics endpoint and frontend metrics types. Existing metric meanings remain unchanged.

### Read-only feasibility contract

- Add `GET /scenarios/{scenario_id}/feasibility` with required query inputs `lat`, `lon`, `duration`, and `deadline`; duration is positive seconds and deadline is timezone-aware. An optional `satellite_id` restricts the query to that satellite.
- Use scenario-wide observation-window suitability. The search starts at the Scenario's simulation start, independently of the current mission clock. Echo the search interval and return `scope: window_only` so that the query's time basis and limits are explicit.
- Validate finite coordinates, positive finite duration, a deadline after Scenario start, and optional satellite membership. Unknown scenarios use the existing not-found response; malformed inputs use the existing API validation convention. Do not publish inconsistent bespoke error envelopes.
- Support orbital policies in this slice. Unsupported non-orbital policies return a clear domain error rather than fabricated candidate windows.
- Generate candidate windows without introducing a request into the RequestPool or recording events. Use an internal ephemeral request identity that cannot consume session identifiers.
- For each included satellite, return one result with `satellite_id`, `window_id`, `window_start`, `window_end`, `earliest_start`, and `latest_finish`. Acquisition fields are null and `reason` is `no_suitable_window` when none can contain the duration before the deadline. A satellite unavailable in the Scenario returns `reason: satellite_unavailable`.
- Derive the action start using the Scenario's WindowPolicy, including its culmination-start setting. A window that cannot hold the complete action under that setting is unsuitable. Clip the usable horizon to the Scenario end and candidate deadline.
- `window_start` and `window_end` describe the returned window; `earliest_start` is the policy-compatible proposed start, and `latest_finish` is the usable finish boundary, the minimum of window end, Scenario end, and candidate deadline. The proposed start plus duration must not exceed that boundary.
- Sort suitable results by earliest start then satellite identifier; put unsuitable results after them, ordered by satellite identifier. Return a nullable `earliest_satellite_id`, using the same deterministic tie-breaker.
- Feasibility accounts for stored orbital geometry, daylight/pointing policy, duration, deadline, and Scenario availability. It does not account for the current MissionPlan, current resources, pairwise slew, active outages, or reservations. It is not a promise that the Planner will schedule the candidate.
- Repeated queries must not change Scenario data, MissionState, RequestPool, events, windows held by the active session, plans, traces, impacts, or identifier counters. The route does not save a modified session.

### Example, frontend, and attribution

- Bundle one real earthquake with raw evidence, manifest, explicit imaging profile, stored orbital inputs, and matching Scenario dates. Start the Scenario before the cue to permit a baseline plan, and leave enough horizon to demonstrate a response.
- The research describes a September 28 probe but does not identify a particular USGS event or preserve its response in this specification. Do not invent one or claim that the probe is an archive. During implementation, select an independently verifiable event, record its exact source event identifier and archived evidence, and document its selection. Prefer a preserved probe event only if that evidence can actually be found.
- The Example briefing names the real event and distinguishes the earthquake facts from hypothetical satellite capabilities, imaging costs, and response policy. Example loading makes no network call.
- Reuse the existing mission lifecycle controls. Supply a documented event script that advances to the cue and injects it; a new exercise engine is not required. Injection and manual replan remain separate.
- Event evidence shows source, source event identifier, alert level, optional magnitude/significance, and the policy notice. Cue markers link to the same event and request; do not duplicate markers on rerender or reload.
- Show a timeline segment from arrival to planned imaging start, changing its label to achieved only when execution has begun. For an unscheduled request show an explicit unserved state, not a zero-width successful response.
- Show planned and achieved means with counts, plus per-request satellite attribution. Refresh after injection, replan, clock advancement, reset, and reload using backend values rather than browser-derived execution logic.
- The feasibility view displays its window-only scope and returns no action-submission or reservation side effect.
- Add the USGS notice to the existing third-party-notices documentation and display `U.S. Geological Survey` beside evidence. Use existing dashboard styling and access patterns.
- Record the cue policy and replay boundary in one ADR with a response-latency/window-only feasibility note. A3 centroid-only intent is a future-slice note, not an A3 implementation requirement.

## Testing Decisions

The requester asked for no test work during this planning phase. No tests are required to be written or run to complete this document or decompose it into tickets. Do not create standalone testing tickets from this spec without a later request.

The acceptance criteria below describe observable delivery behavior, not a request to start a test suite. When implementation begins, any verification plan must respect the requester's instructions. Existing prior art includes the MissionSession lifecycle/replay boundary, weather archive validation, emergency event validation, API contract behavior, and dashboard metrics presentation.

## Acceptance criteria

1. The archive builder rejects corrupted or invalid selected input before publishing generated outputs and produces deterministic requests from unchanged evidence and policy.
2. Red, orange, yellow, green, unknown, and magnitude-floor cases obey the documented priority/deadline table. All times are timezone-aware UTC.
3. The generated request contains an explicit imaging profile; no missing resource or duration input is silently invented.
4. The bundled Example identifies an actual archived earthquake and documents its dates, stored orbital inputs, hypothetical capabilities, and source credit.
5. The cue is injected at its exact simulated time. The recorded emergency event contains complete evidence and generated observation windows, without changing the pristine Scenario.
6. Manual evidence-free arrivals remain compatible. Partial evidence, invalid selected records, and duplicate request injection produce clear diagnostics without partial state changes.
7. After a manual replan, the emergency request is either scheduled with ordinary PlanDiff/DecisionTrace behavior or remains unserved with existing reasons. Frozen actions remain unchanged.
8. Replaying the pristine Scenario and accepted ordered event log reproduces the functional plan, request, evidence, and explanation outputs without archive or network access. Existing wall-clock timing metrics are excluded from equality.
9. Latency distinguishes planned, achieved, unscheduled, and expired requests, counts every eligible emergency arrival, and never treats missing service as zero latency.
10. Achieved latency appears at actual imaging start, survives completion and later replans, and is preserved after session reconstruction.
11. Historical-plan metrics exclude emergency requests introduced after that plan while retaining existing `measured_at` semantics.
12. Feasibility includes every queried satellite, deterministic ordering, duration/deadline containment, and explicit window-only limitations, without changing session state or reserving resources.
13. Dashboard evidence, cue markers, latency segments, counts, and attribution agree with backend results after lifecycle changes and reload.
14. Existing Planner interfaces, mission utility, plan churn, explanation coverage, and offline application behavior retain their established meanings.

## Out of Scope

- A3 CEMS ingestion. Centroid-only conversion is approved direction for its next specification; this slice does not implement polygons or tiling.
- E conjunction outages, C requester fairness, D archive satisfaction, F campaigns, G training packs, and I benchmark imports.
- H cloud-probability-aware planning is rejected for now because it reopens the existing weather/planning boundary.
- Other USGS adapters, GDACS, FIRMS, methane, vessel, and forest-loss feeds; source-update event semantics; live alert polling.
- New sensor types, area requests, moving targets, operational disaster-response guarantees, and imaging-product processing.
- Resource-aware feasibility, new optimization objectives, automatic replan, request submission/reservation through feasibility, and full OGC SPS adoption.
- New standalone exercise infrastructure and mandatory test-suite work during specification or ticket decomposition.

## Further Notes

- Research claims were checked on September 28, 2026. Implementation must not assume that mutable feeds still contain those records. Exact archive selection is a bounded implementation task, not an invitation to invent evidence.
- The table and broad-scope decisions were confirmed during grilling. Detailed edge-case and response contracts in this refinement are explicit implementation defaults added to remove ambiguity. They should travel with tickets; any material deviation must be called out rather than silently chosen by an implementer.
- `/to-tickets` should produce dependency-linked vertical slices that together deliver this specification. Preserve the no-test-work instruction and do not include deferred features as blockers.
- The natural dependency order is archive/normalization and policy, evidence-compatible injection and offline Example, latency reporting, read-only feasibility, and dashboard integration. Cross-cutting serialization/persistence changes belong with the behavior they enable, not an isolated cleanup ticket.
- A ticket selecting the Example must finish by naming the actual earthquake identifier and artifact, because the research probe alone is insufficient evidence. Duration and resource values belong to that Example's explicit profile rather than global defaults.
