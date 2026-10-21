# D: Archive-first imagery satisfaction

Status: local specification; implementation pending.
Source: AMIS world-impact feature research, section D; archive-first boundaries follow ADR-0012.
The requester asked for this specification in the local world-impact folder. No external issue is created. Satisfaction and accounting policies below are proposed defaults requiring an ADR during implementation. Verification seams were confirmed by the requester.

## Problem Statement

An operator may schedule new imaging even when suitable existing imagery already meets an ObservationRequest's need. AMIS cannot represent that outcome or explain why capacity was released. Treating archive fulfillment as an ordinary drop or simulated acquisition would misrepresent both service and Satellite resource use.

## Solution

Provide an explicit developer operation to archive catalogue search results and a pure offline rule to assess them against author-supplied suitability requirements. Record an evidence-bearing archive-satisfaction MissionEvent for a qualifying pending ObservationRequest. Preserve the original request, give it a distinct terminal outcome, release only its unfrozen future imaging during explicit replanning, and report archive fulfillment separately from new acquisition.

## User Stories

1. As an operator, I want to check existing imagery before new tasking, so that Satellite capacity can serve unmet needs.
2. As a scenario author, I want explicit recency, cloud, resolution, and collection requirements, so that suitability reflects the intended use.
3. As a developer, I want archived catalogue responses and provenance, so that changing search results do not change replay.
4. As an auditor, I want checksum verification before selection, so that damaged evidence cannot fulfill a request.
5. As a scenario author, I want coverage checked against the target coordinate, so that a nearby scene is not assumed to contain the point.
6. As a scenario author, I want missing required metadata rejected, so that unknown quality is not silently accepted.
7. As an auditor, I want image acquisition time distinguished from catalogue availability, so that future imagery cannot satisfy an earlier request.
8. As an operator, I want deterministic selection among qualifying scenes, so that repeated conversion produces the same decision.
9. As a trainee, I want a recorded satisfaction event, so that I can inspect the evidence and its timing.
10. As a trainee, I want impact inspection and explicit replanning, so that released capacity remains explainable.
11. As an auditor, I want archive satisfaction distinct from completion by imaging, so that mission utility is not inflated.
12. As an operator, I want already-started imaging protected, so that an archive decision cannot undo execution.
13. As an evaluator, I want new-acquisition and archive-fulfillment totals separated, so that comparisons remain meaningful.
14. As an evaluator, I want emergency response to remain unacquired when only archive imagery is used, so that B does not invent a Satellite response.
15. As a dashboard user, I want the item identity, quality checks, and policy visible, so that I can audit why the request no longer needs new imaging.
16. As an auditor, I want persisted replay without the catalogue or archive, so that reconstruction is deterministic.
17. As an operator, I want invalid, duplicate, expired, or already fulfilled transitions rejected, so that the RequestPool cannot enter contradictory states.
18. As a trainee, I want a bundled before/after Example, so that I can see another request use the released capacity.
19. As a maintainer, I want legacy Scenarios and events to retain their behavior, so that the new terminal outcome is additive.
20. As an evaluator, I want historical plans to retain their original outcomes, so that later satisfaction events do not rewrite earlier reports.

## Implementation Decisions

### Archive and author requirements

- Add an archive-check module with archive loading, catalogue normalization, and a pure suitability rule, plus explicit developer fetch/build operations. Use Copernicus Data Space STAC as the first catalogue integration.
- Network access belongs only to developer fetching. Catalogue search and paging must finish successfully before the archive is published; store original pages, request parameters, URLs, retrieval times, checksums, and pagination completion metadata. Do not interpret a partial/failed search as no coverage.
- Revalidate the current catalogue endpoints, collection identifiers, filter/pagination contracts, geometry conventions, metadata units, and redistribution/attribution requirements during implementation. The research records historical probes, not a current API guarantee.
- Require a per-request suitability profile identifying allowed collections, an inclusive acquisition-time interval, maximum cloud-cover percentage, maximum ground-sample distance in meters, and any required viewing limits. Require an explicit statement that the selected collection meets the desired sensor/product need; AMIS has no general sensor-matching model.
- Keep this profile as developer conversion input and record its version and thresholds in generated and accepted evidence. Do not infer acceptable image quality from request priority or generic Scenario geometry policy.
- Support point targets only. A scene footprint must contain or cover the target point, including its boundary, using documented geographic geometry semantics. Bounding-box overlap alone is insufficient. Fail unsupported/invalid geometry with a clear diagnostic rather than assuming coverage.

### Suitability and time semantics

- Normalize collection id, item id, item acquisition instant or interval, footprint, cloud percentage, ground-sample distance, required view metadata, and source link. Require finite values in documented units. Missing metadata fails any criterion that requires it; do not substitute favorable defaults.
- Cloud cover is catalogue-reported scene quality, not a guarantee of cloud-free pixels at the target. State this approximation in the evidence view and Example. Collection resolution is not proof that a particular user need is satisfied without the explicit author profile.
- Every acquisition instant/interval must fall wholly within the allowed profile interval and no later than the proposed satisfaction instant. For interval items, use the interval end for recency ranking and retain both endpoints as evidence.
- Prevent historical look-ahead: the selected item must be demonstrably available by satisfaction time. For the initial implementation, require that the archived search was retrieved no later than satisfaction time; do not infer historical availability solely from acquisition time or a mutable catalogue update field. Choose a compatible dated Scenario accordingly.
- All applicable requirements must pass. Sort qualifying candidates by newest acquisition interval end, then lower cloud percentage, then collection id and item id. Select one item per request. Exact repeated catalogue identities collapse; conflicting selected identities fail conversion.
- Require an explicit satisfaction/injection instant within the half-open Scenario interval and after the ObservationRequest has entered the RequestPool. Reject date mismatches without clipping or shifting. No match produces a documented no-match result and no MissionEvent.
- Version the selection policy as `archive-point-v1`. Publish deterministic generated event inputs atomically only after every selected request validates.

### Domain transition and recording

- Add `REQUEST_SATISFIED_BY_ARCHIVE` as a MissionEvent type and `SATISFIED_BY_ARCHIVE` as a distinct terminal RequestStatus. An ADR must define its transition/accounting semantics before implementation is complete. Do not reuse `COMPLETED` or conceal the outcome under `DROPPED`.
- Accepted payloads contain request id, catalogue source, collection/item ids, source link, acquisition times, footprint/target-match evidence, required measured quality values, satisfaction profile, policy version, and source-response digest. Preserve enough normalized evidence to explain the checks without loading the original archive.
- MissionSession validates evidence structure, threshold consistency, target identity, item timing, request membership, and allowed state transition before any mutation. A developer rule determines catalogue suitability; the runtime never queries STAC or verifies a remote product.
- Accept only a pending or scheduled, unexpired request with no authoritative started/completed imaging action. Reject unknown, expired, completed, already archive-satisfied, or frozen/started requests without recording an event or changing identifiers/state. Check execution history, not only the selected historical MissionPlan.
- Event injection records the satisfaction outcome and impact; replanning stays explicit. Until replan, show the active MissionPlan as affected rather than pretending its old future action has already disappeared. The simulation must not execute an affected, unfrozen imaging action for an archive-satisfied request; require replan before advancing through that action.
- On replan, exclude the terminal request from new imaging choices, preserve its RequestPool identity and evidence, and release its unfrozen future action. Do not refund already consumed resources or modify frozen actions. Scenario inputs remain pristine under ADR-0002.
- Extend event serialization, API schemas, persistence reconstruction, reset/replay, request-status filters, validators, Planner eligibility, metrics, PlanDiff, DecisionTrace, and frontend types consistently. Legacy absent fields/statuses retain existing meaning.
- Add `SATISFIED_BY_ARCHIVE` as a ReasonCode. Use an additive archive-satisfied PlanChangeType where an action disappears; also produce a status explanation for an unscheduled request that becomes satisfied. Do not call the transition imaging completion. Replay must reproduce these explanations from accepted events.

### Accounting and presentation

- Preserve existing mission utility and imaging completion metrics: archive fulfillment contributes neither simulated imaging utility, completed imaging count, nor resource consumption. Add separate archive-satisfied count and utility, plus a labelled total-fulfilled count/utility based on the union of imaging-served and archive-satisfied request ids, counted once.
- Under C, retain acquisition-based requester utility/fairness and report archive fulfillment separately by requester. D must work without C; attribution is optional when that feature is available.
- Under B, keep archive-satisfied emergency arrivals in the response collection with their terminal status. Planned acquisition becomes null after replan; achieved acquisition remains null because the transition is rejected once imaging has started. Do not manufacture a responding Satellite or zero acquisition latency.
- Use accepted event time as archive fulfillment time. Historical-plan metrics exclude later satisfaction transitions while preserving established current-state measurement semantics where applicable; label planned service and current fulfillment separately rather than borrowing a later RequestPool snapshot.
- Show a distinct status badge, evidence, suitability thresholds, scene-quality approximation, item link, and required attribution. Mark the event on the timeline and distinguish catalogue imagery from simulated Satellite imaging on the map/request inspection view.
- Deliver an independently verifiable Example with archived search results, explicit suitability profile, dated inputs, baseline action, satisfaction event, and separate replan showing released capacity used by another request. No real image download is necessary to demonstrate metadata-based selection; explain that no product-content verification occurs.
- Acceptance requires deterministic conservative selection, atomic rejected transitions, correct terminal eligibility, explicit replan behavior, unchanged legacy metrics, separate fulfillment accounting, complete evidence, and replay without network or archive files.

## Testing Decisions

- Use the confirmed MissionSession seam for accepted/rejected transitions, already-started actions, expiry, affected-plan clock behavior, explicit replans, resource accounting, PlanDiff/DecisionTrace, B compatibility, historical membership, persistence, reset, and offline replay.
- Use the developer archive-builder seam for checksum/pagination failures, point coverage and boundary cases, time intervals, historical availability, missing quality metadata, policy boundaries, deterministic ties, duplicate/conflicting items, and no-match outputs. Test observable qualification results rather than private geometry implementation.
- Prior art is weather archive/replay, Cue builder atomicity, emergency evidence validation, immutable Scenario and terminal-expiry behavior, plan metrics, and existing persistence reconstruction checks.
- Keep API checks to new event/status contracts and dashboard checks to distinct fulfillment labels, provenance, attribution, null acquisition values, and lifecycle refresh. No tests are written or run as part of this specification task.

## Out of Scope

- Image download, processing, visual cloud detection, pixel-quality guarantees, mosaics, area coverage, task submission to a real provider, live catalogue lookup, or automatic event injection/replanning.
- General sensor/capability modeling, sub-meter suitability inferred from coarse imagery, replacement of already executed acquisitions, or archive credit inside the existing mission-utility objective.
- Historical catalogue availability inferred from acquisition date alone and resource-aware feasibility changes.

## Further Notes

- D does not require A3, E, or C, but its new terminal state has the widest lifecycle impact of these slices. Review enum exhaustiveness and eligibility/status handling across backend and frontend during implementation.
- The research leaves archive utility accounting open. This proposal preserves existing acquisition metrics and adds explicit fulfillment metrics so archived service is visible without rewriting prior comparisons.
- A metadata match is a simulated satisfaction decision under an explicit profile. It does not establish that the actual image product meets operational needs. Select a real dated fixture during implementation; do not invent item ids or reinterpret a historical probe as an archive.
