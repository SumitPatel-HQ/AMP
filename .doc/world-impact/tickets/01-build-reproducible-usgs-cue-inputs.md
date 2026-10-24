# 01: Build reproducible USGS cue inputs

**What to build:** A developer can explicitly archive a USGS GeoJSON response, then use an offline builder to turn selected earthquakes into reproducible emergency-arrival inputs for a Scenario. The output distinguishes archived facts from the AMIS imaging and response policy.

**Blocked by:** None (can start immediately).

**Status:** implemented

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

- [x] An explicit developer fetch stores the original response bytes with source name, exact source URL, timezone-aware retrieval time, file identifier, and SHA-256 checksum. Existing archives are never silently overwritten. No other operation fetches source data.
- [x] Offline loading verifies integrity before parsing. Missing manifest entries, missing responses, and checksum mismatches produce actionable diagnostics.
- [x] Selected GeoJSON points normalize longitude before latitude, ignore depth as an imaging coordinate, require finite longitude in [-180, 180] and latitude in [-90, 90], require a nonempty source event identifier, and convert valid epoch-millisecond event times to timezone-aware UTC.
- [x] Accepted alert levels are red, orange, yellow, and green. Missing or null alerts become the explicit evidence value `unknown`. Other alert strings fail validation. Optional magnitude and significance are finite numeric evidence and remain absent when missing.
- [x] Request identifiers derive deterministically from source and source event identifier. Exact duplicate normalized records collapse; conflicting records sharing an identifier fail with a diagnostic. No source-update event semantics are introduced.
- [x] Policy maps red to priority 5 and a 12-hour deadline, orange to 4 and 24 hours, yellow to 3 and 48 hours, and green or unknown to 2 and 48 hours. Deadlines are offsets from earthquake time. Magnitude at least 6 raises priority to 5 without changing the alert-based deadline. Significance has no policy effect.
- [x] Every request uses an explicit author-supplied imaging profile for duration, energy cost, storage cost, and optional satellite assignment. Existing ObservationRequest validation applies. Missing values are not guessed; severity never determines resource costs. A descriptive target name is nonempty and is not the request identifier.
- [x] The generated artifact stores the imaging profile and policy version. Each input carries the intended earthquake UTC injection time and the complete source evidence group, plus optional magnitude/significance. It is clearly a developer input, not an accepted MissionEvent with session-assigned identity or recorded windows.
- [x] Selected cue times must lie at or after Scenario start and strictly before Scenario end. Out-of-range selections fail instead of shifting or clamping time. Authors can explicitly select a smaller set before building.
- [x] Output ordering is event time, source, then source event identifier. Fixed archived bytes, selections, Scenario, and profile/policy produce identical output bytes. Fetch timestamps are recorded separately from deterministic conversion.
- [x] Any invalid selected record fails the build before output publication. Failure leaves no partially generated event script.
- [x] One selected earthquake creates one ObservationRequest. There is no clustering, tiling, new EventType, new Planner input, or runtime archive dependency.
- [x] One cue-replay ADR records the policy table as AMIS assumptions, policy versioning, evidence and offline replay boundaries, and planned/achieved latency and window-only feasibility semantics. It respects ADR-0001, ADR-0002, ADR-0008, ADR-0012, and ADR-0014. A3 centroid conversion is a future note only.
