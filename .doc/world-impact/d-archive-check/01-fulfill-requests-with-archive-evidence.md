# 01: Fulfill requests through recorded archive evidence

**What to build:** An operator records that suitable existing imagery fulfills an ObservationRequest, inspects its evidence and distinct terminal outcome, and explicitly replans to release unfrozen future imaging while acquisition and archive fulfillment remain separately measured.

**Blocked by:** None (can start immediately from the delivered A1+B baseline).

**Status:** implemented

**Governing specification:** [Archive-first imagery satisfaction](spec.md).

**Branch independence:** Implement on the D feature branch without A3, E, or C. Deliver mission-wide archive/fulfillment totals without requiring `requester_id`, requester panels, or fairness code. Any later per-requester archive reporting is optional additive integration, not a delivery blocker.

- [x] Record the state-transition/accounting ADR: distinct `REQUEST_SATISFIED_BY_ARCHIVE` event and `SATISFIED_BY_ARCHIVE` terminal RequestStatus; archive fulfillment does not count as simulated acquisition or existing mission utility.
- [x] MissionSession and the event API accept complete evidence containing request identity, catalogue/collection/item identity, source link/digest, acquisition times, target/coverage evidence, measured quality values, explicit suitability profile, and policy version.
- [x] Validate evidence completeness, finite values, threshold consistency, target identity, acquisition/availability timing, membership, and allowed transition before mutation. Runtime handling is offline and never queries a catalogue or opens a remote image product.
- [x] Accept only pending/scheduled, unexpired requests without authoritative started/completed imaging. Reject unknown, expired, completed, frozen, or already archive-satisfied requests atomically, with no recorded event or consumed identifiers.
- [x] Provide a documented reproducible way to submit a valid evidence-bearing event. A clearly labelled synthetic catalogue fixture is sufficient here; the real catalogue workflow belongs to D-02.
- [x] Injection records satisfaction and exposes impact without automatically replanning. The dashboard identifies the old active MissionPlan as affected; clock advancement cannot execute its obsolete unfrozen imaging action and provides a clear replan-required diagnostic.
- [x] Explicit replan excludes the terminal request from imaging choices, preserves its RequestPool identity/evidence and pristine Scenario, and releases only future unfrozen work. Never refund consumed resources or alter frozen actions.
- [x] PlanDiff and DecisionTrace identify archive satisfaction distinctly, including an explanation when an unscheduled request is fulfilled. Do not misclassify fulfillment as imaging completion or an ordinary drop.
- [x] Keep existing acquisition utility/completion/resource metrics unchanged. Add archive-satisfied counts/utility and clearly labelled union-based fulfilled counts/utility, without duplicate request credit or future-event leakage into historical plan membership.
- [x] B retains archive-satisfied emergency arrivals with distinct status and no invented achieved latency/Satellite. Planned acquisition becomes null after replan; missing service is never represented as zero acquisition latency.
- [x] Dashboard request/event/map/timeline inspection displays the distinct outcome, source item, quality/profile thresholds, approximation notice, source credit, and separate acquisition/fulfillment results.
- [x] Serialization, persistence/reconstruction, status filters, Planner eligibility, validators, reset, and replay support the additive terminal outcome across backend/frontend. Legacy events and statuses retain their meaning.
- [x] Verify the confirmed MissionSession lifecycle seam for transition rejection, execution history, affected-plan clock behavior, explicit replan, metrics, explanations, historical membership, and persisted offline replay; keep API/dashboard checks focused on public behavior.

**Delivery boundary:** Completes usable archive-evidence fulfillment end to end. STAC search archiving, scene qualification, and the real capacity-release Example belong to D-02.

Implementation: [ADR-0017](../../adr/0017-archive-fulfillment-is-not-acquisition.md).
Reproduce the synthetic lifecycle with `python -m scripts.archive_fulfillment_demo`;
see `amis/data/examples/archive-synthetic-fulfillment/README.md`.
