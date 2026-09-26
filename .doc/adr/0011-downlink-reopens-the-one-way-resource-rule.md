# Downlink reopens the one-way resource rule

Status: accepted (Wave 4, spec decision 26)

## Context

The MVP locked resources to move one way: battery only falls, storage only rises.
Several places depend on that: `ResourceProjection` summed costs in any order,
CP-SAT expresses storage as one linear sum, `validate_plan` and `MissionSession.step`
charge at action start, and every `ScheduledAction` carries a `request_id` that plan
diff, traces, churn, impact, and metrics key by. Wave 4 adds ground-station contacts
and downlink actions that free storage, so each of those assumptions needs an
explicit rule.

## Decision

### Stations and contacts

- Stations are catalogue entries (`amis/data/stations/stations.json`, hashed in
  `manifest.json`). Each carries coordinates and an elevation mask of 5 to 10 degrees.
  The coordinates are public approximate site locations; the masks are an engineering
  assumption, not a cited figure.
- A mission opts in through `WindowPolicy.ground_station_ids` and sets
  `WindowPolicy.downlink_rate_mb_s` (megabytes per second). Both live in the existing
  `window_policy` JSON column, so scenarios need no migration.
- Contact windows come from the same Skyfield `find_events` pass extraction as target
  windows, evaluated at the station with the station mask. They are derived, not
  persisted: the session computes them from the stored orbit and catalogue on demand.
  Contact ids are `CON-<station>-<n>`, stable for a given orbit and mission span.

### Action kind

- `ScheduledAction.kind` is `imaging` or `downlink`. Imaging actions keep the current
  meaning. Downlink actions have `request_id = None`, `window_id = <contact id>`, and
  `station_id = <station id>`.
- `scheduled_actions.request_id` and `window_id` become nullable in migration 0004,
  which also adds `kind` (default `imaging`) and `station_id`. Existing rows read back
  as imaging actions unchanged.

### Storage math

- A downlink action's `storage_cost_mb` is a signed delta: `-(rate x duration)`. Its
  energy cost is zero in Wave 4 (transmitter power is folded into the bus budget until
  Wave 6 models power over time).
- Storage frees at contact **end**, not start: data counts as removed only after the
  pass that sent it is over. Imaging still charges at its start. At equal instants the
  downlink release applies before an imaging charge.
- Storage floors at zero: a downlink never frees more than is stored when it ends.

### Timeline walk

- `ResourceProjection` walks every committed action in event-time order (imaging at
  start, downlink at end), flooring at zero at each step. `available_at` and
  `check_commit` share that walk. This is the projection Wave 6 recharge extends.
- `validate_plan` pre-commits every planned downlink, then judges each imaging action
  against the walk at its start.
- `MissionSession.step` charges imaging at start (unchanged) and applies a downlink
  release when the downlink completes.

### Placement policy: reservations, not decisions

- Downlink placement is planner-owned but not optimized. Before imaging placement, the
  planner reserves one downlink action per valid contact that ends after the current
  simulated time, spanning the whole contact (clipped to start no earlier than now).
  After imaging placement, downlinks that free nothing (storage already zero when they
  end) are pruned, so the plan only shows passes that move data.
- Downlink uses the communication subsystem, not the payload, so it does not take part
  in the overlap or settling rule and is not blocked by payload outages.
- Greedy sees reservations through the timeline walk, so storage freed by a contact lets
  later imaging fit. CP-SAT keeps its linear storage sum. That sum ignores releases, so it
  is conservative: any CP-SAT selection stays feasible under the walk. The existing
  "never below the greedy baseline" fallback means a downlink-enabled mission never loses
  utility to that conservatism. An exact reservoir model is deferred to Wave 6.

### Request-less actions in diff, traces, churn, impact, metrics

- Plan diff and decision traces are request-scoped and ignore downlink actions.
  Downlinks are reservations re-derived on every plan, not operator-visible decisions,
  so they never produce `MOVED`/`DROPPED` entries or traces.
- Churn counts only imaging actions in both numerator and denominator.
- Impact and validation use a subject key: the request id for imaging, the action id
  for downlink. A downlink whose contact a `COMMUNICATION_OUTAGE` invalidated is
  reported as an invalid unfrozen action with reason `WINDOW_INVALIDATED`, and the
  replan simply reserves the remaining contacts.
- Metrics utility and completion read imaging actions only. `downlink_action_count`
  and `downlink_volume_mb` (total rate x duration of the plan's downlinks) report the
  downlink side; pruning guarantees every counted downlink frees storage.

### Communication outages

`COMMUNICATION_OUTAGE` carries `station_id` and an `[outage_start, outage_end)` span.
Every contact at that station overlapping the span is marked invalid, derived from the
event log so replay needs nothing else. The event flows through the existing impact and
replan path.

## Consequences

- Nothing that keys by request id sees a `None` key; each consumer filters by kind.
- A mission with no stations behaves exactly as before: no contacts, no downlinks.
- CP-SAT is weaker than greedy on storage-bound downlink missions until Wave 6.
