# Slew and sunlight recharge

Status: accepted (Wave 6, spec decisions 29 and 30)

## Context

Until Wave 6 two consecutive observations only had to be apart by a fixed
settling time, whatever their targets, and the battery only ever drained.
Both limits understate a real agile imager: repointing between distant
targets takes time, and a multi-day mission recharges in sunlight. Planning
must enforce both without breaking the offline, deterministic, planner-blind
rules from earlier waves.

## Decision

### Slew

- `WindowPolicy.slew_rate_deg_s` (default 0, disabled) sets a constant
  attitude slew rate.
- `amis/dynamics/slew.py` computes the slew angle between two targets as
  the angle their surface chord subtends at orbit altitude above the chord
  midpoint: `2 * atan(chord / (2 * altitude))`. Altitude is the mean
  altitude from the stored elements. The model is approximate: it ignores
  the satellite's motion between looks, acceleration and settling profiles,
  and Earth curvature under the chord.
- The slew gap between two imaging actions is settling time plus angle over
  rate. It is pairwise and symmetric.
- `check_overlap` takes a `SlewModel` and uses the pairwise gap. Greedy
  placement, CP-SAT explanation, and `validate_plan` all pass the same model,
  so a violation is caught at placement and again at validation.
- A slew conflict reuses `TIME_OVERLAP`, with `required_gap_s` in the
  violation details. A new reason code would ripple through traces and the
  frontend labels for no new operator action: the fix is the same as for an
  overlap.
- Downlink actions still skip overlap (ADR-0011), so they have no slew.
- A mission without an orbit has no altitude, so its slew is zero and only
  settling time applies. The API rejects a non-zero slew rate or recharge
  rate on a non-orbital provider.

### Sunlight recharge

- `WindowPolicy.recharge_rate_w` (default 0, disabled) sets the charge power
  while sunlit.
- `amis/dynamics/recharge.py` finds sunlit intervals over the mission span
  from the stored orbit and the bundled DE421 ephemeris (Skyfield
  `is_sunlit`), sampled every 30 s and refined to the second by bisection.
  The ephemeris checksum is verified first. Results are cached per
  canonical OMM content and span.
- Gain over an interval is rate times sunlit hours in it.
- `ResourceProjection` walks from the mission state's simulated time and adds
  the gain before each step, capped at battery capacity.
  `ResourceProjection.for_mission` builds that projection; the planners and
  `validate_plan` use it.
- `MissionSession.step` adds the same gain between action starts and up to
  the new clock, so the state the next replan reads matches what the
  planner projected.
- The frozen-action exemption (ADR-0003) and the impact path are unchanged.

### CP-SAT

Slew is a sequence-dependent setup time. Each pair of actions on one
satellite (with a non-zero gap) gets an order literal, and the pair's own
gap is enforced in whichever order the solver picks, so CP-SAT matches the
pairwise rule `check_overlap` validates.

With recharge enabled, CP-SAT models the battery as a chain of levels over
short buckets (every sunlit edge, and at least every 10 minutes). Spend in a
bucket must fit its opening level; the next level is at most both
`level + gain - spend` and `capacity - spend`. That is a sound lower bound
on the capped timeline walk: no in-bucket gain is credited before a spend,
and gain and capacity are floored. Frozen actions stay exempt (ADR-0003): a
bucket only has to fit when a candidate lands in it. Without recharge the
Wave 1 linear sum is unchanged.

Downlink reservations do not depend on the imaging choice (ADR-0011), so
their storage releases are known before the solve. With any release, CP-SAT
models storage as a chain of upper-bound levels between releases: charges
in a bucket must fit on top of its opening level, and the next level is at
least `max(0, level + charge - release)`, matching the floored walk.

## Consequences

- Plans with slew enabled respect the approximate agility limit, and
  validation fails closed on any plan that does not.
- Multi-day missions can schedule more energy-hungry work than the one-way
  battery rule allowed, while battery stays within zero and capacity.
- CP-SAT's bucketed bounds are slightly conservative (no in-bucket recharge
  credit); the greedy-baseline fallback (ADR-0009) still guards utility and
  shows in `solver_details.fallback`.
- A future attitude model can replace `slew_angle_deg` without touching the
  constraint callers.
