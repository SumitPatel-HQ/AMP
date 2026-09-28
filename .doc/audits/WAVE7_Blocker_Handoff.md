# Wave 7 handoff: blockers and prerequisites

> **Status (2026-09-28): resolved.** Every blocker below is fixed on
> `main`: CP-SAT pairwise slew and recharge/downlink-aware budgets (ADR-0013),
> slew fails closed with a read-only target map, one shared resource walk,
> a content-keyed recharge cache, and split API validators. Kept as a
> historical record only.

**Context:** Waves 1-6 are implemented on `main` (Wave 6 = commit `0880b9d`,
"Implement Wave 6 slew and sunlight recharge (ADR-0013)"). Wave 7 is **multiple
satellites** per `.doc/specs/AMIS_Phase2_Spec.md`: decision 31 plus stories
47-50 and the Wave 7 test bullets (per-satellite overlap and resources enforced
independently; assignment covers all requests exactly once; single-satellite
missions produce identical plans to Wave 1 behavior).

Backend baseline at write time: `.venv` pytest reports 209 passed.
`WAVE6_Blocker_Handoff.md` is still untracked.
`.doc/status/feature-implementation-status.md` is stale (dated 2026-09-25,
says 136 backend tests, lists CP-SAT and orbital provider as absent).

## Blocker 1: Wave 6 review debt — fix or explicitly accept before widening

From the Wave 6 review of `8eff22d...0880b9d`, still present on `main`:

- **CP-SAT slew is not pairwise:** `amis/planning/cp_sat.py:58` pads every
  interval with `slew.max_gap_s`. Safe but wastes time when gaps vary.
  Spec decision 29 asks pairwise setup enforced at placement and validation.
- **CP-SAT recharge is not in the solve:** `amis/planning/cp_sat.py:112-121`
  leaves recharge out of the linear battery sum. Only `_with_downlinks`
  and `_explain` use `ResourceProjection.for_mission`. A plan that recharge
  would make feasible can be rejected by the solver. The greedy fallback
  hides the loss.
- **Slew fail-open on unknown targets:** `amis/dynamics/slew.py:58-64`
  returns `0.0` when either target id is missing. A bad id degrades to
  settling-only instead of failing closed.
- **Recharge walk copied three times:** `amis/constraints/resources.py:120,171`
  in `available_at` and `check_commit`, plus `charge_until` in
  `amis/session.py:618-624`. Same `_charged` plus clock logic in each place.
- **Frozen type holds mutable state:** `amis/dynamics/slew.py:34-41`
  `SlewModel` is frozen but holds `targets: dict`.
- **Cache keying is brittle:** `amis/dynamics/recharge.py:57-71` `_OrbitKey`
  hashes only `sha256` and the `lru_cache` keys on exact `start` and `end`.
- **Validator name is stale:** `amis/api_schemas.py:64`
  `validate_ground_stations` now also gates slew and recharge.

Copying these to N satellites multiplies the faults. Either fix them first
or record acceptance in the Wave 7 ADR.

## Blocker 2: singular-satellite assumptions — needs dedicated ADRs first

Spec decision 31 says this wave reopens the singular assumptions behind
dedicated ADRs. Current shape on `main`:

- `amis/domain/scenario.py:103` `Scenario.satellite` is one `Satellite`.
- `amis/domain/state.py:13-22` `MissionState` holds one `satellite_id`,
  one battery, one storage, one availability flag.
- Planners read `scenario.satellite` (`amis/planning/greedy.py:175,184`,
  `amis/planning/cp_sat.py:113,150,209`), as do `amis/constraints/resources.py:95`,
  `amis/constraints/plan_validation.py:103`, `amis/session.py:618,658,917`,
  `amis/metrics.py:53,57,85`, `amis/dynamics/slew.py:46`,
  `amis/dynamics/recharge.py:46`.
- Already per-action: `amis/domain/plan.py:22` `ScheduledAction.satellite_id`,
  `amis/domain/window.py:14` `ObservationWindow.satellite_id`. These help
  but do not fix scenario, state, or persistence.
- Persistence has no multi-sat shape: `migrations/versions/0001-0004` assume
  one satellite per scenario. Needs a `0005` plan with backwards compat for
  existing missions.
- Events partly name a satellite (`BatteryDropPayload`, `SatelliteOutagePayload`)
  but cloud, emergency, and communication outage handling still assume one
  satellite in session, impact, and validation paths.

## Design decisions to lock first (one ADR, ADR-0013 style)

1. **Assignment model:** request names a satellite vs planner assigns it.
   Field shape on `ObservationRequest`, validation rules, and default for
   legacy single-sat scenarios.
2. **State shape:** per-satellite battery, storage, availability, and
   completed sets plus mission totals. `MissionState.initial` and
   `to_dict` and `from_dict` contract, and replay from scenario plus event log.
3. **Windows:** computed per request and satellite pair. Id convention,
   `satellite_id` on windows, provider protocol change or new multi provider.
4. **Constraints per satellite:** overlap plus slew gap, resources plus
   recharge, and downlink contacts evaluated independently per satellite.
   `WindowProvider` and `Planner` protocol changes fenced behind the ADR
   (spec seam note: only Wave 7 may widen these interfaces).
5. **Events, impact, diff, traces, metrics:** events name their satellite;
   diff and traces keep request keying and add per-satellite views; metrics
   adds per-satellite plus mission totals. Single-sat parity rule: existing
   missions produce byte-identical plans.
6. **API and frontend:** scenario schemas accept a satellite list; plan
   history, ground tracks, and map render per satellite; Examples and Load
   Mission stay compatible.

## Prerequisites already in place (don't rebuild)

- `amis/constraints/resources.py` timeline-walk projection, the per-satellite
  walk extension point.
- `amis/constraints/overlap.py` pairwise gap hook via `SlewModel`.
- `amis/dynamics/slew.py` angle-rate model and `amis/dynamics/recharge.py`
  sunlit-interval model, both offline and deterministic.
- `WindowProvider` and `Planner` protocols as the extension seam
  (`amis/windows/protocol.py:15-18`, `amis/planning/protocol.py:21-31`).
- Conventions to follow: `MissionSession` stays the test seam (ADR-0001),
  scenario immutable and event log stays the replay record (ADR-0002),
  frozen-action exemption unchanged (ADR-0003), fail-closed validation,
  update glossary plus ADR every wave.

## Baseline hygiene before implementing

- Commit or remove `WAVE6_Blocker_Handoff.md` (currently untracked) and this file
  once consumed, so the tree is clean.
- Refresh `.doc/status/feature-implementation-status.md` (counts, CP-SAT and
  orbital rows, Wave 5-6 coverage).
- Re-verify frontend tests and mypy after Wave 6. Wave 6 fixed one backend
  test (`tests/test_rest_api.py` now compares `cloud_example()`) and touched
  no frontend. A red suite hides Wave 7 regressions.

## Acceptance bar for Wave 7

New tests proving: per-satellite overlap and resources enforced independently;
assignment covers all requests exactly once with no double booking; single-sat
missions give identical plans to pre-Wave-7 behavior; events, impacts, diffs,
traces, and metrics work per request across satellites; full backend suite
green except explicitly accepted baseline items above.
