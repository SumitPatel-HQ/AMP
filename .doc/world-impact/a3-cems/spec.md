# A3: Copernicus EMS activation replay

Status: local specification; implementation pending.
Source: AMIS world-impact feature research, sections A3 and 4. Builds on delivered A1+B and ADR-0015.
The requester asked for this specification in the local world-impact folder. No external issue is created. Detailed defaults below are specification proposals, not operational Copernicus policy or previously approved implementation choices. Verification seams were confirmed by the requester.

## Problem Statement

A disaster-management trainee can replay an earthquake Cue, but cannot introduce a real Copernicus EMS activation with its original activation time and inspectable evidence. Activations describe areas, while AMIS ObservationRequests describe points. Without an explicit conversion policy, the dashboard could imply that observing one coordinate covers an entire disaster area.

## Solution

Extend the developer-operated, archive-first Cue pipeline to public Copernicus EMS activations. Convert one selected activation into one centroid-based ObservationRequest, inject it at its recorded activation time, and reuse the existing impact, explicit replan, PlanDiff, DecisionTrace, and emergency-response displays. Bundle one independently verifiable, dated Example with an honest explanation of the point-target approximation.

## User Stories

1. As a developer, I want to archive a selected activation's original public responses, so that conversion has reproducible evidence.
2. As an auditor, I want source URLs, retrieval times, and checksums, so that I can identify exactly which source snapshot was used.
3. As a scenario author, I want checksums verified before parsing, so that damaged archives cannot generate ObservationRequests.
4. As a scenario author, I want public-status checks, so that sensitive activations are excluded.
5. As a scenario author, I want activation identity, category, event time, activation time, and centroid normalized, so that the source has one consistent interpretation.
6. As a scenario author, I want invalid or missing required values rejected, so that the builder does not invent disaster facts.
7. As a trainee, I want the activation centroid visibly labelled, so that I understand the ObservationRequest does not cover the whole area.
8. As a scenario author, I want an explicit imaging profile, so that source severity does not invent Satellite capabilities or resource costs.
9. As a scenario author, I want a versioned urgency policy, so that AMIS assumptions remain separate from source evidence.
10. As a scenario author, I want deterministic identifiers and duplicate handling, so that repeated records cannot create duplicate arrivals.
11. As a trainee, I want a baseline MissionPlan before activation, so that I can see the effect of the new ObservationRequest.
12. As a trainee, I want injection at the exact activation instant, so that response latency starts from a faithful timestamp.
13. As a trainee, I want impact inspection before choosing to replan, so that the established lifecycle stays visible.
14. As an auditor, I want source evidence and accepted ObservationWindows persisted, so that replay needs neither the archive nor the network.
15. As a dashboard user, I want activation evidence on the event and map, so that the coordinate and source identity agree.
16. As an evaluator, I want planned, achieved, and unserved response reported through B, so that CEMS arrivals receive the same treatment as USGS arrivals.
17. As a maintainer, I want manual and USGS emergency arrivals to remain compatible, so that adding CEMS does not change older serialized payloads.
18. As a trainee, I want a bundled briefing and source attribution, so that I can distinguish historical facts from simulator assumptions.

## Implementation Decisions

### Existing boundaries and archive contract

- Extend the existing cues archive, normalization, and offline input-generation modules. Share integrity checks, identifier generation, and imaging-profile validation; keep source-specific parsing and policy separate.
- Only an explicit developer fetch operation contacts the source. Application startup, Example loading, conversion, injection, and replay remain offline under ADR-0008, ADR-0012, and ADR-0015.
- Archive original bytes for every response needed to establish the selected activation, with source name, exact requested URL, timezone-aware retrieval time, response filename, and SHA-256. Refuse silent overwrites. Verify all selected inputs before atomically publishing generated output.
- The research records public activation-summary and detail endpoints. Confirm their current contracts, public/sensitive flags, timestamp conventions, coordinate reference system, attribution notice, and redistribution terms before selecting an implementation fixture. Do not treat the research's example activation code as a preserved archive.
- Include only explicitly public, non-sensitive activations. If visibility cannot be established, fail that selection rather than assuming public status. Never commit credentials or sensitive response content.

### Normalization, identity, and point conversion

- Normalize source identity as `cems`, activation code, descriptive name, category, event UTC time, activation UTC time, and the source-provided activation centroid. Require nonempty identifiers and names, timezone-aware timestamps, finite coordinates, and valid geographic bounds.
- Interpret source WKT using its documented coordinate system and longitude/latitude axis order. Require a valid point centroid. Missing, malformed, unsupported, or ambiguous centroid geometry fails the selected record; do not silently compute a new centroid from polygons.
- One activation creates one ObservationRequest. AOI polygons and product lists do not create additional requests. The UI and briefing say “activation centroid; point approximation,” including that no area-coverage guarantee is modeled.
- Injection time is activation time, not disaster event time or archive retrieval time. Preserve event time separately when supplied; reject contradictory event-after-activation timestamps for the selected historical replay rather than silently repairing them.
- Use the existing source/id-derived Cue request identity with activation code as source event id. Equal normalized duplicates collapse; conflicting records with the same identity fail conversion. Revisions are not additional arrivals in this slice.
- Sort generated arrivals by activation time, source, and activation code. Require each selected arrival inside the half-open Scenario interval. Never move source dates to fit a Scenario.

### Simulation policy and event evidence

- Proposed policy `cems-centroid-v1`: priority 5 and deadline 24 hours after activation for every selected activation. Category is descriptive evidence, not an invented severity ranking. Record this as an AMIS assumption in a new or extended Cue ADR before implementation is accepted.
- Require explicit duration, energy cost, storage cost, and optional Satellite assignment through the existing imaging profile. Keep the policy deadline even when Scenario end provides a tighter usable horizon.
- Reuse `EMERGENCY_TASK`. The existing core evidence group uses source `cems`, source event id equal to activation code, and alert level `unknown`, because the adapter does not establish a source alert level. Do not invent a red alert or populate earthquake magnitude/significance.
- Add optional CEMS-specific evidence for activation category, source event time when available, activation time, public source URL, and point-conversion policy version. Specify one validated group across the domain payload, API schema, serialization, persistence, and frontend types. CEMS source requires its activation-time and centroid-policy evidence; reject contradictory evidence groups before generating windows or mutating state.
- Omit new evidence keys from older manual and USGS payloads. Source identity does not alter Planner inputs or resource rules.
- Generated developer inputs carry intended injection time and policy/profile metadata. MissionSession assigns accepted event identity and time, computes missing orbital ObservationWindows, and records those windows, including an empty result. A runner advances to the exact activation instant and checks it before injection. Replanning remains explicit.

### Delivery and observable acceptance

- Bundle one actual public activation with archived bytes, manifest, deterministic input artifact, matching stored orbital inputs, dated Scenario, briefing, and documented replay command. Choose the activation during implementation from verifiable evidence; do not fabricate a historical example.
- Show CEMS identity, category, timestamps, point approximation, policy notice, and the required source credit beside evidence. Reuse event inspection and Cue markers; loading or rerendering must not duplicate markers.
- B reports latency from accepted activation arrival to imaging start, including unscheduled and expired requests. No second latency implementation is introduced.
- Acceptance requires deterministic offline conversion, exact-time injection, explicit impact/replan behavior, complete persisted evidence, replay from pristine Scenario plus accepted events, and dashboard agreement after reload/reset. An activation with no suitable ObservationWindow remains a legitimate unserved arrival.

## Testing Decisions

- Use the requester-confirmed MissionSession lifecycle/replay seam for injection, impact, explicit replan, response metrics, duplicate rejection, immutable Scenario behavior, and persistence reconstruction. Assert observable results rather than private helper calls.
- Use the existing developer archive-builder seam for checksum failures, visibility exclusions, WKT axis order, timestamp validation, duplicate conflicts, explicit profiles, and byte-stable output. Clearly label synthetic malformed fixtures; only real archived evidence may support the bundled historical Example.
- Follow existing USGS Cue, emergency-arrival, bundled-Example, and weather offline-replay checks as prior art. Prove replay with network access forbidden and the source archive unavailable.
- Keep API checks to schema/validation behavior and dashboard checks to evidence, attribution, centroid labels, markers, and B results through lifecycle changes. No test writing or execution is part of delivering this specification.

## Out of Scope

- Area coverage, AOI tiling, polygon ObservationRequests, multiple requests per activation, sensor modeling, live polling, activation updates, automatic replan, or operational response promises.
- New latency definitions, resource-aware feasibility, other Cue sources, conjunctions, fairness, archive satisfaction, and a new training engine.

## Further Notes

- A3 is the next planned slice after A1+B and can reuse their delivered contracts. It does not depend on E, C, or D.
- Source endpoint and licensing details in the research are historical observations, not a current integration guarantee. Revalidation and selection of the actual activation are bounded implementation tasks.
- The centroid approach was already accepted as the direction for A3. The uniform priority/deadline and detailed evidence group here are proposed defaults, to be recorded visibly rather than represented as Copernicus recommendations.
