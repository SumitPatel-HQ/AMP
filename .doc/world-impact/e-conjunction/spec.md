# E: Conjunction-derived Satellite outages

Status: local specification; implementation pending.
Source: AMIS world-impact feature research, section E.
The requester asked for this specification in the local world-impact folder. No external issue is created. Detailed defaults below are specification proposals, not operational collision-avoidance instructions. Verification seams were confirmed by the requester.

## Problem Statement

A trainee can simulate a Satellite payload outage but cannot connect it to archived evidence of a close approach. Consequently, they cannot explain which imaging actions were affected by a space-safety constraint or distinguish a source prediction from an AMIS assumption about instrument unavailability.

## Solution

Archive public SOCRATES conjunction reports through an explicit developer operation. Convert selected qualifying conjunctions into evidence-bearing `SATELLITE_UNAVAILABLE` MissionEvents, using an explicit simulated outage interval around closest approach. Reuse MissionSession impact and explicit replanning, and show the conjunction evidence with the affected Satellite and DecisionTrace.

## User Stories

1. As a developer, I want a preserved conjunction report with provenance, so that the same prediction can be replayed later.
2. As a developer, I want fetches to respect the provider's current usage policy, so that archiving does not repeatedly query an unchanged report.
3. As an auditor, I want checksums validated before conversion, so that modified report bytes cannot silently alter outages.
4. As a scenario author, I want both catalogue identities and closest-approach values normalized, so that matching does not depend on object names.
5. As a scenario author, I want matching through stored OrbitalElements, so that the outage applies to the correct Scenario Satellite.
6. As a scenario author, I want explicit selection where orbital identities are reused, so that hypothetical Satellites do not receive ambiguous outages.
7. As a scenario author, I want an explicit probability threshold, so that I can see why a prediction generated an outage.
8. As a scenario author, I want configurable outage padding and injection time, so that simulator assumptions remain visible.
9. As a scenario author, I want date mismatches rejected, so that unrelated historical reports cannot be presented as matched evidence.
10. As a trainee, I want evidence beside an outage, so that I can inspect the other object, closest approach, and policy.
11. As a trainee, I want impact inspection before replanning, so that I can understand the disruption before accepting a new MissionPlan.
12. As a trainee, I want conjunction-specific trace wording, so that affected imaging actions have an intelligible cause.
13. As an auditor, I want manual outages to remain compatible, so that old event logs still reconstruct.
14. As an auditor, I want accepted evidence preserved in recorded events, so that replay needs no original report or network.
15. As an evaluator, I want multiple conjunctions handled deterministically, so that ordering and overlap do not change results between runs.
16. As a trainee, I want frozen imaging actions preserved, so that an injected prediction cannot rewrite execution history.
17. As a trainee, I want a dated Example, so that I can reproduce a space-safety disruption offline.
18. As a trainee, I want the maneuver simplification stated, so that I do not mistake a payload outage for an orbit-change simulation.

## Implementation Decisions

### Archive and source interpretation

- Add a conjunction archive, normalizer, and pure outage-input builder. Reuse existing archive integrity and deterministic-publication patterns without coupling conjunction policy to Cue emergency-arrival policy.
- Only an explicit developer fetch operation contacts SOCRATES. Store original bytes, exact source URL, retrieval time, report generation/coverage metadata when established by the source, response filename, and SHA-256. Do not invent publication time from retrieval time.
- Revalidate the current report format, units, probability representation, access terms, attribution, and request interval against provider documentation before implementation. Fail on HTTP errors and respect retry guidance; no automatic tight retries or startup refreshes.
- Record the provider's applicable next-allowed-fetch time in developer archive metadata, and refuse an early refresh. The research's update interval is historical context, not a hard-coded claim about current policy.
- Normalize both NORAD catalogue ids, source object names when supplied, UTC time of closest approach (TCA), miss distance in kilometers, and source maximum probability. Require finite, nonnegative distance and probability in [0, 1] after documented source conversion. Missing/unsupported probability values do not qualify and must produce explicit diagnostics, not zeroes.
- Validate the selected report and rows before publishing outputs. Equal normalized duplicate encounters collapse; conflicting rows for the same object-pair/TCA identity fail selection. Canonicalize object-pair order for identity while retaining source orientation as evidence.

### Satellite matching and simulation policy

- Match Scenario Satellites using their stored OrbitalElements NORAD id against either encounter object. Do not match by display name. Unmatched rows are excluded with a summary. An explicitly selected Satellite without a matching stored identity fails conversion.
- If several Scenario Satellites reuse one NORAD id, require an explicit author mapping. If both encounter objects are represented, emit one outage per selected matching Satellite, each with the counterpart identity.
- Proposed policy `socrates-outage-v1` qualifies encounters with maximum probability greater than or equal to 0.0001. This is a simulation selection threshold, not a declaration that a real maneuver occurred or was necessary.
- Require the author to provide positive pre-TCA and post-TCA outage durations and a timezone-aware injection instant per selected encounter. Do not invent maneuver duration, maneuver time, or advance warning from TCA or retrieval time.
- The outage interval is TCA minus pre-padding through TCA plus post-padding. Require start before end, injection no later than outage start, injection within the Scenario interval, and the full outage inside the Scenario horizon. Reject mismatches rather than clipping or shifting evidence.
- A real dated Example must use report evidence available by its injection instant and orbital snapshots valid for its horizon. If source publication cannot be established, require retrieval no later than injection and explain that conservative bound. Historical predictions must not be injected before they were available.
- Generated artifacts record encounter identity, threshold, padding, injection instant, selected Satellite mapping, and policy version. Stable input and policy produce stable output ordered by injection time, Satellite id, and encounter identity.

### Event, explanation, and compatibility contracts

- Reuse `SATELLITE_UNAVAILABLE` and its existing Satellite-specific outage interval. No new Planner input or runtime report lookup is introduced.
- Extend SatelliteOutagePayload with optional conjunction evidence: source, stable encounter id, matched NORAD id, counterpart NORAD id, TCA, miss distance, maximum probability, threshold, policy version, and policy padding. Treat required conjunction evidence as one validated group; omit it completely for existing manual outages.
- Validate finite values, identities, interval derivation, and evidence completeness before mutation. Duplicate derived encounters for the same Satellite must fail without recording another event or changing mission identifiers/state. Preserve existing manual-outage acceptance rules.
- MissionSession records accepted event identity and time. The runner advances to and checks the intended injection instant. Injection exposes impact; creating a new MissionPlan remains a separate explicit operation.
- Distinct qualifying encounters remain distinct evidence records, even when their outage intervals overlap. Existing outage application should give union-of-interval behavior; deduplicate affected imaging-action identifiers in impact reporting rather than counting an action twice.
- Add `COLLISION_AVOIDANCE_OUTAGE` as a ReasonCode for changes actually caused by conjunction-derived unavailability, with counterpart identity and evidence links. Do not apply it to unrelated resource failures or claim causal certainty from an arbitrary plan difference. Ordinary outages retain existing reasons.
- Preserve frozen actions under ADR-0003. If an outage conflicts with an action already started, report the conflict through established impact/validation behavior without moving, dropping, or recosting that action.
- Extend serialization, API payload validation, persistence/reconstruction, event inspection, Satellite outage display, and trace rendering together. Replay uses pristine Scenario plus recorded events, with no report access.

### Observable acceptance

- Deliver a bundled, independently verifiable conjunction Example with matching report dates and stored orbital inputs, a briefing, and a replay operation showing impact plus a separate replan.
- Show the source prediction, policy threshold, counterpart, TCA, assumed outage interval, and source credit. State that no maneuver confirmation, fuel use, delta-v, or orbital trajectory change is modeled.
- Acceptance requires deterministic conversion/matching, complete event evidence, unchanged evidence-free wire shapes, overlap behavior, frozen-history preservation, conjunction-specific explanations where justified, and offline persisted replay.

## Testing Decisions

- Use the confirmed MissionSession lifecycle/replay seam for derived/manual outages, Satellite isolation, overlapping intervals, explicit replans, frozen actions, impact, traces, persistence, and failure atomicity.
- Use developer archive-builder checks for checksum integrity, source units, malformed probabilities, threshold boundaries, duplicate/conflicting rows, both-object matching, ambiguous NORAD reuse, historical availability, and horizon mismatch.
- Prior art is the existing Satellite-outage flow, weather archive/offline replay, USGS Cue builder, multi-Satellite lifecycle, and DecisionTrace checks. Assert public outcomes rather than normalizer call structure.
- Keep API checks focused on evidence validation/serialization and dashboard checks on evidence and causal trace labels. Prove replay without report files or network access. No tests are written or run to deliver this document.

## Out of Scope

- Collision prediction, operational maneuver advice, orbit propagation changes caused by a maneuver, fuel accounting, automatic evasive actions, live warning services, Space-Track restricted CDMs, and a new Planner.
- Treating maximum source probability as a measured collision outcome or treating absence from SOCRATES as proof of safety.
- Other world-impact features and changes to B's window-only feasibility exclusions.

## Further Notes

- E is independent of A3, C, and D. Its implementation requires an ADR recording the probability interpretation, assumed interval, provenance boundary, and trace semantics.
- Selecting a real report and a dated orbital Scenario is an implementation deliverable. If no compatible historical evidence is available, report that gap rather than inventing a conjunction or shifting its dates.
