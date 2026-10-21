# 01: Inject and inspect CEMS arrivals

**What to build:** A trainee introduces a CEMS activation as an evidence-bearing emergency arrival, inspects its centroid and source facts, explicitly replans, and sees the existing emergency-response results. The arrival survives persistence and offline replay.

**Blocked by:** None (can start immediately from the delivered A1+B baseline).

**Status:** implemented (2026-10-21)

**Governing specification:** [A3 CEMS activation replay](spec.md).

**Branch independence:** Implement on the A3 feature branch without E, C, or D. Requester attribution is not required. Extend existing emergency contracts additively; preserve manual and USGS payload shapes and behavior. Keep any preparatory refactoring local to this delivery.

- [x] Record the CEMS centroid policy in an ADR: one activation becomes one point ObservationRequest; proposed priority 5 and deadline 24 hours after activation are AMIS assumptions, not Copernicus recommendations.
- [x] Accept a CEMS arrival through MissionSession and the existing event API with source `cems`, activation code as source event id, alert level `unknown`, activation time, category, public source URL, source event time when available, and centroid-policy version. Do not populate earthquake magnitude/significance.
- [x] Validate the required CEMS evidence group, UTC timestamps, coordinate bounds, explicit imaging profile, and activation/injection-time agreement before computing windows or changing state. Reject partial, contradictory, duplicate, or malformed arrivals without partial mutation.
- [x] Provide a documented reproducible way to submit a valid arrival through the existing lifecycle controls/API; a clearly labelled synthetic fixture is sufficient for this ticket and must not be presented as historical evidence.
- [x] Advance to the exact activation instant before injection. Record accepted event identity, simulated time, and generated orbital ObservationWindows, including an empty result. Keep the pristine Scenario unchanged.
- [x] Injection exposes impact and leaves replanning explicit. Replanning produces ordinary PlanDiff/DecisionTrace behavior, preserves frozen actions, and permits a legitimate unserved outcome.
- [x] Event inspection and the map display activation identity, category, source/event times, attribution, policy notice, and “activation centroid; point approximation.” Markers link to the accepted event/request and do not duplicate on reload.
- [x] Existing B metrics and timeline display planned, achieved, expired, and unserved response from the accepted arrival time; no source-specific latency implementation is introduced.
- [x] CEMS evidence and windows round-trip through domain/API serialization and persistence. Replay uses only pristine Scenario plus accepted ordered events, with archive files absent and network access forbidden.
- [x] Verify observable behavior at the confirmed MissionSession lifecycle/replay seam, with focused API validation and dashboard checks for evidence, markers, response values, reset, and reload. Keep manual and USGS compatibility covered.

**Delivery boundary:** This ticket completes usable CEMS event handling across backend and dashboard. Live fetching, archive conversion, and the real historical Example belong to A3-02.

## Delivery evidence

- Feature branch: `t3/inject-inspect-cems-arrivals` in its dedicated T3 worktree.
- Policy: [ADR-0016](../../adr/0016-cems-centroid-arrivals.md).
- Reproducible lifecycle/API walkthrough: [synthetic replay](synthetic-replay.md).
- Verification: 501 backend tests and 200 frontend tests pass; TypeScript typecheck,
  production build and frontend lint pass (lint has warnings in unchanged files).
  Python mypy reports the same 34 errors in the same 8 files as the starting commit;
  no new type errors. Existing Skyfield/NumPy deprecation warnings remain.
- Browser checks: HTTP injection, evidence/credit/policy inspection, explicit replan,
  ordinary unserved response and timeline, reload/reselection, and reset. Marker
  identity and deduplication are covered by dashboard model tests. SQLite restart
  and network-forbidden replay cover both generated windows and an empty result.
- Independent Standards and Spec reviews completed. Public-host validation and
  numeric loopback aliases, domain-owned request validation, and provider error
  compatibility findings were addressed; final reviews have no remaining findings.
- Historical archive acquisition, conversion, and the real Example remain A3-02.
