# D: Archive-first imagery satisfaction

[Feature specification](spec.md).

Status: D-01 and D-02 implemented and verified; tickets are local.

1. [01: Fulfill requests through recorded archive evidence](01-fulfill-requests-with-archive-evidence.md) — no blockers beyond the delivered A1+B baseline.
2. [02: Find suitable catalogue imagery offline](02-find-suitable-catalogue-imagery.md) — delivered after D-01.

## Independent branch contract

- Start a dedicated feature branch from a common baseline containing the delivered A1+B behavior and these planning documents. Complete 01 before 02 on that branch; merge the feature without waiting for any other world-impact feature.
- There are no cross-feature blockers or shared prerequisite-refactor tickets. The complete pair must work and be verifiable while the other three features are absent.
- Make shared domain, API, serialization, and frontend changes additive. Preserve existing optional-field omission, manual-event compatibility, immutable Scenario replay, frozen actions, and explicit replanning.
- Avoid broad shared-code rewrites, renames, formatting passes, or an extensibility framework introduced solely for another feature. Keep source adapters, policies, fixtures, and Examples within this feature's scope.
- Shared files may still produce merge conflicts. Resolve them by preserving both additive behaviors and regenerate derived API contracts from the merged backend rather than dropping one branch's additions. Independent functionality does not guarantee conflict-free textual merges.
- Conditional interoperability mentioned in the specification is not a dependency: no requester attribution, archive outcome, source adapter, or reason code from another pending feature is required for this pair to pass acceptance. Integrate optional reporting only when the relevant feature is already present; do not silently widen this feature's scope.
- Use the confirmed MissionSession lifecycle/replay seam, developer archive-builder checks where relevant, and focused API/dashboard checks. Verification belongs with each behavioral ticket; there is no standalone test or integration ticket.

## Scope and completion

The specification governs detailed behavior; these tickets assign delivery ownership. Together, 01 and 02 cover the complete feature, including compatibility, persistence, explanations, frontend behavior, verification, policy ADRs, and a demonstrable Example. Ticket creation does not implement the feature or run tests.


Run the real metadata Example with `python -m scripts.run_archive_athens_replay --replan`.
See [primary-source verification](source-verification.md) and
`amis/data/examples/archive-athens-2026-10-26/README.md` for rebuild, persistence
and dashboard inspection instructions.
