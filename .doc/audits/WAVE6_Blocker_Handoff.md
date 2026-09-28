# Wave 6 handoff: blockers and prerequisites

> **Status (2026-09-28): resolved.** Every blocker below is fixed on
> `main`: CP-SAT pairwise slew and recharge/downlink-aware budgets (ADR-0013),
> slew fails closed with a read-only target map, one shared resource walk,
> a content-keyed recharge cache, and split API validators. Kept as a
> historical record only.

**Context:** Waves 1–5 are implemented on `main` (Wave 5 = commit `f9ae134`,
"Implement Wave 5 weather-driven events (ADR-0012)"). Wave 6 is **advanced
dynamics** per `.doc/specs/AMIS_Phase2_Spec.md`: story 45 (time-dependent slew
enforced in planning) and story 46 (sunlight recharge from orbit geometry),
plus spec decisions 29–30 and the Wave 6 test bullets (slew violations at
placement + validation; recharge math vs hand-computed sunlight intervals;
multi-day battery in bounds).

## Blocker 1 (resolved)

Wave 5 was uncommitted — now committed as `f9ae134`. Build Wave 6 on top of it.

## Blocker 2: red baseline — fix or explicitly accept before implementing

Verified pre-existing via `git stash` on the pristine tree (not caused by Wave 5):

- **Backend (1 failure):**
  `tests/test_rest_api.py::test_demo_scenario_route_returns_the_canonical_scenario_without_persisting_it`.
  `examples.cloud_example()` now carries a `canonical_demo` window policy; the
  test compares against the policy-less `build_canonical_replan_scenario()`.
  Suggested fix: compare against `cloud_example()` instead.
- **Frontend (46 failures):** `src/App.test.tsx` (44) +
  `src/panels/MissionMapPanel.test.tsx` (2). Mocks still expect pre-Wave-4
  example names (e.g. "Cloud block replanning demo"). Wave 6 touches no
  frontend, but a red suite hides regressions.
- **mypy (30 baseline errors):** Wave 4 `str | None` downlink debt, mostly
  `amis/session.py`. New code must add zero (Wave 5 added zero — verify the
  same way).

## Design decisions to lock first (one ADR, ADR-0012 style)

1. **Slew reason code:** reuse `TIME_OVERLAP` or add a new code (e.g.
   `SLEW_CONFLICT`)? Drives traces + `frontend/src/state/planComparison.ts`
   labels.
2. **CP-SAT treatment:** sequence-dependent setup times don't fit its linear
   sum model (`amis/planning/cp_sat.py:104-109`). Recommended: keep CP-SAT
   conservative and document it (same caveat pattern as ADR-0012/ADR-0011),
   relying on the greedy-fallback safety net.
3. **Recharge fallback for non-orbital missions:** synthetic missions have no
   orbit — define it (recommended: zero gain, documented) so behavior stays
   honest.

## Prerequisites already in place (don't rebuild)

- `amis/constraints/resources.py` — timeline-walk `ResourceProjection`, the
  exact extension point for recharge gains.
- `amis/constraints/overlap.py` — already takes `min_gap_s` and skips
  downlinks; generalize to pairwise slew gaps.
- Sun geometry + bundled ephemeris (2026-09-20 → 10-14) from the orbital
  provider; empty `amis/dynamics/` dir is the intended home for slew/recharge
  models.
- Conventions to follow: pure offline models, planner-blind inputs, event log
  stays the replay record (ADR-0002), fail-closed validation (GAP-07 backstop
  pattern in `amis/session.py`), update glossary + ADR every wave.

## Acceptance bar for Wave 6

New tests proving: slew violations caught at placement **and** validation;
recharge math matching hand-computed sunlight intervals; multi-day battery
staying in bounds; full backend suite green except the explicitly accepted
baseline items above.
