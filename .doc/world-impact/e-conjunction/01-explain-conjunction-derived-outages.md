# 01: Explain conjunction-derived outages

**What to build:** A trainee introduces an evidence-bearing conjunction outage for a Satellite, inspects affected imaging actions, explicitly replans, and reads conjunction-specific explanations. The evidence and behavior survive persistence and offline replay.

**Blocked by:** None (can start immediately from the delivered A1+B baseline).

**Status:** implemented (2026-10-26)

**Governing specification:** [Conjunction-derived Satellite outages](spec.md).

**Branch independence:** Implement on the E feature branch without A3, C, or D. Reuse the existing Satellite outage event and lifecycle. Do not introduce a shared refactor that requires another feature branch to merge first.

- [x] Record an ADR for conjunction evidence, source-probability interpretation, assumed outage intervals, and causal trace semantics. The proposed threshold 0.0001 is a simulation policy and does not prove that a real maneuver occurred.
- [x] Extend `SATELLITE_UNAVAILABLE` additively with a complete optional conjunction evidence group: source, encounter identity, matched/counterpart NORAD ids, TCA, miss distance, probability, threshold, policy version, and padding.
- [x] MissionSession and the event API validate evidence, Satellite identity, finite/ranged values, interval derivation, and injection timing before mutation. Existing evidence-free manual outage shapes and validation remain compatible.
- [x] Reject duplicate encounter/Satellite arrivals and malformed evidence without recording events, consuming identifiers, or partially changing state.
- [x] Supply a documented way to inject a valid evidence-bearing outage; a clearly labelled synthetic fixture is sufficient here, without claiming real historical provenance.
- [x] Injection exposes impact; explicit replanning applies only the selected Satellite's outage and preserves frozen actions. Conflicts with already-started imaging remain visible without rewriting execution history.
- [x] Distinct overlapping encounters retain separate evidence, apply union-of-interval unavailability, and do not double-count affected imaging actions.
- [x] Add `COLLISION_AVOIDANCE_OUTAGE` and trace wording only where conjunction-derived unavailability caused the change. Keep ordinary constraint reasons for unrelated failures and ordinary manual outages.
- [x] Dashboard event/Satellite inspection and traces display counterpart identity, TCA, distance, probability/threshold, assumed outage interval, policy notice, and attribution. State that orbit change, fuel use, and maneuver confirmation are not modeled.
- [x] Accepted evidence round-trips through API/domain serialization and persistence. Replay reproduces impact and explanations from pristine Scenario plus recorded events with source reports unavailable and network forbidden.
- [x] Verify these outcomes through the confirmed MissionSession lifecycle/replay seam, plus focused API evidence validation and dashboard rendering/lifecycle checks.

**Delivery boundary:** Completes usable evidence-bearing conjunction outages. SOCRATES archiving, normalization, report-based selection, and the real Example belong to E-02.

## Delivery and verification

- ADR: [0018](../../adr/0018-conjunction-outages-are-simulation-assumptions.md).
- Runnable injection and offline replay: [synthetic training guide](synthetic-replay.md).
- Full backend suite: 655 passed. Full frontend suite: 218 passed across 22 files.
- Frontend TypeScript/production build passed; lint passed with three existing warnings.
- Python mypy reports 31 existing errors, matching a clean export of the starting commit `a7ecec3d2b15a68e798b33970ac155ce1ba008c4`; no new diagnostics remain.
- Two-axis review: standards and spec findings were corrected, including datetime overflow validation and full evidence rendering beside comparison traces.

SOCRATES archive integrity, source normalization/selection, and the real dated Example remain assigned to E-02.
