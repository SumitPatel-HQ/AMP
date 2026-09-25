# AMIS full scope spec: real scenarios to multi-satellite operations

Source: `AMIS_Real_Scenario_Research.md` (repo root), verified against commit `3fe5208`.
This spec covers everything the research found, ordered in waves. Each wave is implementable and testable on its own, and earlier waves keep working as later waves land. The file-level change map lives in research section 19 and is not repeated here.

## Problem Statement

AMIS runs only fixed demo scenarios with synthetic observation windows. An operator cannot define a real mission from a real orbit and real targets, cannot compare planners, cannot model downlink or weather, and cannot fly more than one satellite. Examiners see a scripted demo instead of a growing mission planning simulator.

## Solution

Build the full arc in waves: real mission creation on orbit-derived windows through the unchanged adaptive loop, then proof of plan quality (second planner, evaluation suite), then richer spacecraft and ground models (payload events, derived costs, settling time, placement, slew, recharge), then downlink operations, then weather-driven events, then multiple satellites. The demos survive throughout as an Examples mode.

## User Stories

### Wave 1: real missions on real windows

1. As a mission operator, I want to name a mission and set its start and end time, so that the mission covers the period I care about.
2. As a mission operator, I want to pick a satellite from a bundled catalogue showing name, NORAD id, and element epoch, so that I use a real orbit without hunting for data files.
3. As a mission operator, I want to paste a TLE pair as an alternative to the catalogue, so that I can fly an orbit not in the bundle.
4. As a mission operator, I want to set battery capacity, charge, storage capacity, usage, and availability, so that resource planning reflects my spacecraft assumptions.
5. As a mission operator, I want to add observation requests through a table with working defaults, so that building a target list is fast.
6. As a mission operator, I want to click the map to add a target, so that coordinates come from geography instead of typing.
7. As a mission operator, I want to set priority, duration, deadline, energy cost, and storage cost per request, so that each request carries real planning inputs.
8. As a mission operator, I want to choose the window source for the mission (synthetic, canonical demo, or orbital), so that testing and real missions use the right generator.
9. As a mission operator, I want to set the maximum off-nadir angle and minimum sun elevation for orbital windows, so that windows match my sensor assumptions.
10. As a mission operator, I want a pre-creation check showing errors, warnings, and a per-target window count, so that I fix problems before committing.
11. As a mission operator, I want a warning when the mission sits far from the element epoch, so that I do not trust stale orbits.
12. As a mission operator, I want a warning when a duration exceeds what the geometry allows, so that I do not plan unobservable requests.
13. As a mission operator, I want to import and export a mission as JSON, so that missions are portable and reviewable.
14. As a mission operator, I want to list saved missions, so that I can return to earlier work.
15. As a mission operator, I want to reopen a mission with its full plan history, so that prior versions and comparisons survive a restart.
16. As a mission operator, I want an Examples entry holding the three demos, so that deterministic scenarios stay one click away.
17. As a mission operator, I want loading an example to create a copy with a fresh id, so that the originals never change.
18. As a mission operator, I want orbit-derived windows with peak elevation, off-nadir, and sun values shown, so that I can see why each window exists.
19. As a mission operator, I want requests with no window reported honestly with their own reason, so that an empty result reads as physics rather than a bug.
20. As a mission operator, I want the unchanged loop (plan, step, cloud block, battery drop, emergency arrival, impact, replan, compare, traces, metrics) on orbital windows, so that adaptability is proven on real geometry.
21. As a mission operator, I want an emergency arrival without typed windows to get computed windows in orbital mode, so that urgent tasking works like the rest of the mission.
22. As a mission operator, I want the map to draw the ground track and the true satellite position, so that the display agrees with the windows.
23. As an examiner, I want the same inputs to reproduce the same windows and plans, so that results are checkable.
24. As an examiner, I want each window to record how it was made (provider, library versions, element hash, policy values), so that provenance is visible.
25. As a developer, I want a fetch script that writes dated element snapshots with checksums, so that catalogue updates stay policy compliant and reviewable.
26. As a developer, I want every existing demo test to keep passing, so that later waves never break the working system.

### Wave 2: proof of quality

27. As an examiner, I want a second planner based on constraint programming, so that the greedy plan can be judged against near-optimal plans.
28. As an examiner, I want a comparison table (utility, scheduled counts, violations, planning time, churn, resource use, optimality gap) over shared missions, so that the planners are judged on numbers.
29. As a mission operator, I want to choose the planner per run with the choice recorded in the plan, so that comparisons are traceable.
30. As a developer, I want deterministic solver settings (single worker, fixed seed, work-based time limit), so that comparisons reproduce exactly.
31. As a developer, I want a one-command evaluation run over case files (smoke, constraint, event-response, orbital-window, explanation, planner-comparison, determinism) with blocking gates and a printed report, so that regressions are caught mechanically.
32. As a developer, I want results persisted with data origin and library versions, so that reports stay comparable across months.
33. As an examiner, I want the report to state plainly that results come from a simulator, so that nothing reads as operational certification.

### Wave 3: richer spacecraft model

34. As a mission operator, I want payload outage events over an interval, so that instrument downtime reshapes the plan like any other disruption.
35. As a mission operator, I want energy and storage defaults derived from power, data rate, and duration in the builder, so that costs start from engineering numbers instead of guesses.
36. As a mission operator, I want a fixed settling time between observations enforced by the overlap rule, so that back-to-back plans stay feasible.
37. As a mission operator, I want actions placed near window culmination for image quality as an option, so that planning can trade geometry quality against packing density.

### Wave 4: ground stations and downlink

38. As a mission operator, I want a station catalogue with coordinates, so that contacts are computed from real geography.
39. As a mission operator, I want contact windows per station drawn on the timeline and map, so that downlink opportunity is visible even before downlink actions exist.
40. As a mission operator, I want downlink actions scheduled inside contact windows that free storage by rate times duration, so that long missions with heavy imaging stay feasible.
41. As a mission operator, I want communication outage events, so that lost contacts reshape downlink planning like cloud reshapes imaging.
42. As an examiner, I want storage shown rising on imaging and falling on downlink across the mission, so that the resource story reads end to end.

### Wave 5: weather-driven events

43. As a mission operator, I want archived cloud data ingested offline into recorded cloud-block events carrying source, coverage, and threshold, so that weather replaces hand-injected blocks without any live call.
44. As a developer, I want raw weather responses stored with retrieval time and hash, so that event evidence is auditable and replays need no network.

### Wave 6: advanced dynamics

45. As a mission operator, I want time-dependent slew between consecutive targets enforced in planning, so that agile maneuvering limits are respected.
46. As a mission operator, I want sunlight recharge modeled from orbit geometry, so that battery planning spans multi-day missions honestly.

### Wave 7: multiple satellites

47. As a mission operator, I want several satellites per mission, each with its own orbit and resources, so that constellation planning is possible.
48. As a mission operator, I want requests assigned across satellites by the planner, so that coverage and load sharing emerge from optimization rather than manual splitting.
49. As a mission operator, I want per-satellite overlap, resources, and ground tracks alongside mission totals, so that each spacecraft stays feasible on its own.
50. As a mission operator, I want events, impacts, diffs, traces, and metrics to keep working per request across satellites, so that the explanation story survives the constellation jump.

## Implementation Decisions

Seam: `MissionSession` is the single test seam and application facade. The `WindowProvider` and `Planner` protocols are the extension points. Multi-satellite is the only wave allowed to widen these interfaces, and it does so behind new ADRs.

### Wave 1: real missions

1. Window source is chosen per mission by a stored policy, not by request id. Missions without a policy keep the current dispatch so existing tests and saved missions behave identically.
2. The domain gains two frozen value objects: orbital elements (NORAD id, name, international designator, epoch, canonical OMM fields, original TLE lines when supplied, source, retrieval time, hash) and a window policy (provider kind, max off-nadir angle defaulting to 30 degrees, minimum sun elevation defaulting to 10 degrees with null meaning a sensor that needs no daylight).
3. The satellite keeps its local id. Orbital identity lives inside the new elements object, so plan ids, event payloads, and stored records keep their shape.
4. OMM is the canonical stored form. A pasted TLE pair is parsed, validated for line length and epoch, and its lines are kept verbatim next to the normalized fields.
5. Element snapshots ship as dated files with a manifest holding source URL, retrieval time, and a hash per record. A developer script refreshes them. The server and planner never fetch over the network.
6. Propagation uses Skyfield pinned to an exact version over the pinned `sgp4` package. Only the orbital modules may import it. The planner, constraints, and session stay free of orbital libraries.
7. Sun positions come from a small committed ephemeris excerpt covering the snapshot period, with its hash recorded alongside the windows.
8. The orbital provider builds one propagator per mission, converts the off-nadir limit to a target elevation threshold, finds rise and set events per target across the mission horizon, pairs them into intervals (including windows open at either edge and repeated culminations), filters by sun elevation for optical requests, rounds edges inward to whole seconds, and drops windows shorter than the request duration.
9. Window ids follow the existing per-request numbering. New optional geometry fields (peak elevation and its time, minimum off-nadir, sun elevation, source string) default to absent so existing serialized output stays byte identical.
10. A request with zero candidate windows gets a new reason code meaning no observation window exists for its target in the mission, with trace sentence, constraint name, and frontend label.
11. Emergency arrivals in orbital missions may omit windows. A new session helper computes them through the mission provider before the event is recorded, so the stored event still carries the windows and replay needs no provider call.
12. A validation operation returns errors (unparseable elements, epoch too far, bad policy values, horizon too long), warnings (aging elements, oversize durations, zero-window requests, deadline outside horizon, unaffordable single costs), and a per-request window preview, all without persisting anything.
13. New read operations: mission list summaries, all plan versions of a mission, the element catalogue with epochs, and ground-track samples for a time range. The existing demo scenario route stays as an alias of the cloud example.
14. Persistence adds nullable columns for orbit, policy, target name, and window geometry plus provenance. The migration also handles databases created from the edited-in-place initial migration. No new tables are needed.
15. The frontend gains a mission builder panel (mission, satellite picker, target table with map click, policy, live validation preview), a load-mission list, and an Examples entry. The map uses the ground-track position when present and falls back to the current plan-derived placement for synthetic missions.
16. The demonstration mission spans three to five days over six to eight real targets plus one target outside the field of regard, so the honest no-window path appears on screen.

### Wave 2: proof of quality

17. The second planner implements the existing `Planner` protocol with no changes to simulation, replanning, or UI. Time is modeled in integer seconds from mission start, each request-window pair gets a presence literal with an optional fixed-size interval, one no-overlap constraint covers all intervals plus frozen actions, one-way battery and storage stay linear sums under the locked resource model, and the objective maximizes priority sum with a smaller stability term mirroring the greedy stability rule. Unscheduled reasons come from running the existing constraint checks against the solution afterward.
18. Solver determinism uses a single worker, a fixed seed, and a work-based time limit. Solver status and objective bound are recorded so the comparison reports an optimality gap.
19. The comparison runs both planners over the three examples plus generated orbital missions at several request counts, with and without events, reporting utility, scheduled and completed counts, violations (zero required), planning time medians, churn, resource use, and gap, persisted with data origin and library versions.
20. The evaluation suite stores cases as data files (mission or example id, provider, step and event script, expectations written independently of planner output) in categories: smoke, constraint (one per reason code), event-response, orbital-window geometry, explanation, planner-comparison, determinism. Blocking gates (zero violations, frozen actions identical across versions, replay equality, byte-identical reruns) can never be offset by quality scores. The runner drives `MissionSession` only, names the failing stage, and prints data origin, versions, the simulator disclaimer, and failures. A socket-blocking test guards the offline rule.

### Wave 3: richer spacecraft model

21. Payload outages arrive as events over an interval using the reserved unavailability event type, toggling the satellite flag for that span. Validation rejects actions inside the span. No provider change.
22. Derived cost defaults live in the builder only (power times duration for energy, data rate times duration for storage). Stored costs keep their current meaning, so the planner and constraints do not change.
23. Settling time is a single per-mission gap value checked by extending the overlap rule. The window-meaning ADR records whether durations include it.
24. Culmination placement is a per-mission option that starts actions at the stored peak time minus half the duration instead of the window start. The stability rule interaction is covered by dedicated replan tests before acceptance.

### Wave 4: ground stations and downlink

25. Stations are catalogue entries with coordinates. Contact windows come from the same event-search call used for targets, evaluated at each station with a 5 to 10 degree mask, and render on the timeline and map as information first.
26. Downlink reopens the one-way resource rule behind a new ADR. Actions gain a kind distinguishing imaging from downlink, with downlink actions carrying a station and contact reference instead of a request. Storage falls by rate times duration floored at zero. Plan diff, churn, traces, and metrics define explicitly how request-less actions are treated, since today everything keys by request id. The resource projection switches from monotone sums to a timeline walk, which also prepares Wave 6.
27. Communication outages arrive as events that invalidate the overlapping contacts, flowing through the existing impact and replan path.

### Wave 5: weather-driven events

28. A developer script ingests archived cloud fields offline, storing raw responses with retrieval time and hash plus normalized coverage samples per target and time. A threshold rule converts samples into cloud-block events whose payloads carry source, coverage, and threshold. The planner never sees weather. Replays read recorded values only.

### Wave 6: advanced dynamics

29. Slew is a pairwise setup time between consecutive actions enforced at placement and validation, starting from a simplified angle-rate model the ADR documents as approximate.
30. Recharge adds sunlight-dependent battery gain computed from orbit geometry over each action interval, using the timeline-walk projection from Wave 4. The frozen-action exemption and impact path stay unchanged.

### Wave 7: multiple satellites

31. The mission holds several satellites, each with its own orbit, resources, and availability. Requests either name a satellite or leave assignment to the planner. Windows are computed per request and satellite pair. Overlap and resources are enforced per satellite. State tracks per-satellite battery, storage, availability, and completed sets with mission totals alongside. Events name their satellite. Diff, traces, and metrics keep request keying and add per-satellite views. Ground tracks render per satellite. This wave reopens the singular-satellite assumptions behind dedicated ADRs, which is why it lands last.

### Docs and data discipline every wave

32. Each wave updates the glossary and adds or amends ADRs (window meaning and provenance, offline snapshots, downlink resource rule, multi-satellite assumptions, ADR-0006 transaction text fix). Element and station catalogues carry manifests with hashes. Solver, propagation, and ephemeris versions are pinned and recorded in outputs.

## Testing Decisions

A good test here drives `MissionSession` and asserts on plans, windows, events, impacts, diffs, traces, and metrics. Tests never assert on propagator, solver, or component internals. Prior art: the canonical replan demo test and the production wiring test.

- Wave 1: geometry units without Skyfield, provider ordering and filtering, sampler agreement within two seconds, golden fixture with versions recorded, double-run determinism, socket-blocked generation and planning, full orbital loop with zero violations and full explanation coverage, builder validation cases, listing and history, emergency replay equality, all existing tests unchanged.
- Wave 2: both planners return zero violations on every case, CP-SAT utility at least equal to greedy everywhere, determinism across reruns, comparison report over the case set, each evaluation gate failing on a crafted bad plan, runner stage errors naming the stage.
- Wave 3: outage events invalidate exactly the actions in span, derived defaults match hand-computed values, settling violations caught, culmination placement matches peak-centered starts and keeps stability behavior under replan tests.
- Wave 4: contacts match the sampler within tolerance, downlink math floors storage at zero, outage events invalidate the right contacts, request-less actions render in diff and metrics per the ADR with no keying crashes.
- Wave 5: threshold rule maps samples to the expected events, replay without network reproduces plans, raw archive hashes verify.
- Wave 6: slew violations caught at placement and validation, recharge math matches hand-computed sunlight intervals, multi-day battery stays within bounds.
- Wave 7: per-satellite overlap and resources enforced independently, assignment covers all requests exactly once, single-satellite missions produce identical plans to Wave 1 behavior.

## Out of Scope

Only what the research explicitly rejects: live element refresh inside the running application, browser-side propagation and telemetry simulation, polling the server for positions, SkyOps drone-specific concepts (airspace, GPS, crowd, flight control), and Space-Track integration while CelesTrak covers the catalogue need. Everything else the research found is in the waves above.

## Further Notes

- Open questions: whether duration includes settling time (window-meaning ADR), the 10 degree sun default stays a stated assumption, OMM canonical with TLE lines kept when supplied, exact NORAD ids confirmed at first fetch, downlink scheduling policy (planner-owned intervals versus post-pass insertion, decided in the downlink ADR).
- Risks in order: sparse short windows need multi-day demo horizons; Skyfield on both local and Docker Pythons before Wave 1 provider acceptance; old PostgreSQL volumes and the edited-in-place migration; solver time growth on large orbital cases; request-less actions rippling through diff and metrics code; multi-satellite widening the session interface, contained by landing it last.
- Wave 1 alone is the Presentation 2 floor. Waves 1 plus 2 are the examiner story: real input, adaptive behavior, measured quality. Waves 3 and 4 deepen realism. Waves 5 through 7 are final-presentation material.
