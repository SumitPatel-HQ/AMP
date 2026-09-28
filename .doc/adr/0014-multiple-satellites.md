# Multiple satellites per mission

Status: accepted (Wave 7, spec decision 31, stories 47-50)

## Context

Until Wave 7 a mission holds one satellite: `Scenario.satellite` is a
single `Satellite`, `MissionState` holds one battery, one storage, one
availability flag, and overlap plus resources are evaluated over the
whole plan. `ScheduledAction.satellite_id` and
`ObservationWindow.satellite_id` already name a satellite per record,
but the scenario, the state, the planners, and persistence do not.
Spec decision 31 reopens these singular assumptions behind a dedicated
ADR, which is why this wave lands last. The Wave 7 handoff also records
Wave 6 review debt that copying to N satellites would multiply.

## Decision

### Assignment model

- `ObservationRequest.satellite_id` (`None` by default) pins a request
  to one satellite. `None` means the planner assigns whichever
  satellite can serve it; a name means only that satellite is tried.
- The planner decides assignment, there is no separate assignment
  stage. Greedy tries candidate satellites in id order and places on
  the first feasible one. CP-SAT sums "at most one window chosen"
  across every candidate window of a request on any candidate
  satellite, so the assignment falls out of the same constraint.
- A request appears at most once in a plan, on at most one satellite.
  Validation rejects an emergency window whose satellite is unknown or
  disagrees with a pinned request.

### Scenario and state

- `Scenario.satellites` is the canonical tuple (non-empty, unique ids).
  `Scenario(satellite=...)` stays as the single-satellite shorthand and
  wins over an implicit `satellites` tuple so `dataclasses.replace`
  keeps working. `scenario.satellite` returns the first satellite for
  single-satellite readers. `to_dict` writes `satellites` always and
  repeats the only satellite under the legacy `satellite` key when
  there is exactly one; `from_dict` prefers `satellites` and accepts
  the legacy key.
- `MissionState.satellites` holds one `SatelliteState` per scenario
  satellite (battery, storage, availability, completed set).
  `completed_request_ids` stays a mission-total union because a request
  completes on exactly one satellite. Legacy single-satellite
  construction (`satellite_id=`, `battery_wh=`, ...) and readers
  (`state.satellite_id`, `state.battery_wh`, `state.storage_usage_mb`,
  `state.available`) target the first satellite. `to_dict` writes
  `satellites` always and repeats the legacy top-level fields when
  there is exactly one; `from_dict` prefers `satellites`.
- `MissionState.initial` seeds every satellite from its own
  `Satellite` resources. `for_satellite` / `with_satellite` scope all
  reads and writes. `step` walks each satellite's own actions, its own
  sunlight recharge from its own orbit, and its own battery/storage.

### Windows and contacts

- Windows are computed per request and satellite pair. A pinned
  request gets candidates only on its satellite; an unassigned request
  gets one candidate per satellite from the synthetic, canonical-demo,
  and orbital providers.
- A single-satellite mission keeps the pre-Wave-7 window id exactly
  (`WIN-{request}-{n}`) and contact id exactly (`CON-{station}-{n}`),
  so old plans stay byte identical. Multi-satellite missions suffix
  the satellite id (`WIN-{request}-{sat}-{n}`,
  `CON-{station}-{sat}-{n}`).
- The orbital provider propagates each satellite against its own
  orbit; validation requires every satellite to carry a valid orbit.
  Contacts are derived per satellite per station from the same pass
  search. `GET /scenarios/{id}/ground-track` takes an optional
  `satellite_id` and defaults to the first satellite.

### Constraints, planners, and resources

- Overlap (with the pairwise slew gap), battery, storage, availability,
  and downlink contacts are enforced independently per satellite. Each
  satellite gets its own placed-action list, its own
  `ResourceProjection.for_mission(scenario, state, satellite)`, its own
  `SlewModel.from_scenario(scenario, satellite, requests)`, and its own
  `recharge_model(scenario, satellite)`.
- `SlewModel.from_scenario(scenario, requests)`,
  `recharge_model(scenario)`, and
  `ResourceProjection.for_mission(scenario, state)` stay as
  single-satellite shorthands defaulting to the first satellite.
- Outage intervals carry their satellite
  (`(satellite_id, start, end)`) through planners, `validate_plan`,
  impact, and the session. Battery drops and payload outages name
  their satellite; cloud blocks name a request and window (which names
  its satellite); communication outages invalidate contacts on every
  satellite at that station.
- CP-SAT scopes every no-overlap group and every resource budget to
  one satellite. The Wave 6 caveats are unchanged and now per
  satellite: slew is the largest pairwise gap as a conservative fixed
  gap, recharge stays out of the linear battery sum, and the
  greedy-baseline fallback keeps both gains.

### Explanation and measurement

- Diff, traces, and impact keep request keying, so the explanation
  story survives the constellation jump unchanged. A move across
  satellites reads as a move (same request, new start and satellite).
- Metrics keep mission totals request-keyed and add
  `per_satellite` (`SatelliteMetrics`: battery/storage utilisation,
  downlink count and volume). Mission-wide battery/storage utilisation
  are the mean across satellites, which equals the single satellite's
  own number when there is one. Downlink volume is the sum across
  satellites.

### API and persistence

- `ScenarioSchema` accepts `satellites` (canonical) or legacy
  `satellite`; `ObservationRequestSchema` accepts optional
  `satellite_id` naming a mission satellite; `MissionStateSchema`
  returns `satellites` plus legacy top-level fields for single-sat
  missions; `MetricsSchema` returns `per_satellite`.
- Migration `0005` keys `satellites` like `observation_requests`
  (`scenario_id, id`, `seq` for load order), adds nullable
  `observation_requests.satellite_id`, and replaces the
  single-satellite `mission_states` scalar columns with one JSON
  `satellites` list. `from_dict` on scenario and state reads both the
  new and the pre-Wave-7 shapes.

### Protocols

- This is the only wave allowed to widen `WindowProvider` and
  `Planner` inputs, and it does so by adding a satellite to data that
  already carried one (windows, actions, contacts, outage intervals)
  rather than by changing the protocol methods themselves. The
  `MissionSession` test seam, immutable scenario plus event-log replay
  (ADR-0002), and the frozen-action exemption (ADR-0003) are unchanged.

## Consequences

- Each satellite stays feasible on its own: one satellite's
  contention or budget can never bleed into another's.
- Single-satellite missions produce identical window ids, placements,
  and plans to pre-Wave-7 behavior; the only new output is the
  `per_satellite` breakdown and the repeated legacy keys.
- The Wave 6 review items are explicitly accepted, not fixed here:
  CP-SAT slew is the max gap (safe, wastes time when gaps vary),
  CP-SAT recharge stays out of the solve (conservative, fallback
  hides the loss), unknown targets fail open to settling-only in
  `SlewModel`, the recharge walk is copied across projection and
  session, `SlewModel` is frozen but holds a dict, the recharge cache
  keys on checksum plus exact span, and the API validator keeps its
  `validate_ground_stations` name while also gating slew/recharge.
  Copying them per satellite does not make them worse; a future wave
  may fix them once.
