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
  The ephemeris checksum is verified first. Results are cached per element
  checksum and span.
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

Slew is a sequence-dependent setup time, which the no-overlap interval model
cannot express. CP-SAT pads every interval with the largest pairwise slew
gap among the requests it considers. That is conservative: it can never
produce a slew violation, but it can leave time unused. CP-SAT also leaves
recharge out of its linear battery sum, which is conservative too. The
greedy-baseline fallback (ADR-0009) keeps both gains when CP-SAT would do
worse.

## Consequences

- Plans with slew enabled respect the approximate agility limit, and
  validation fails closed on any plan that does not.
- Multi-day missions can schedule more energy-hungry work than the one-way
  battery rule allowed, while battery stays within zero and capacity.
- CP-SAT is weaker than greedy when slew gaps vary widely; the fallback hides
  this from utility but not from `solver_details.fallback`.
- A future attitude model can replace `slew_angle_deg` without touching the
  constraint callers.
