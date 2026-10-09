# USGS cue inputs and recorded emergency replay

Status: accepted for tickets 01-04. Feasibility behavior below defines the
agreed boundary for ticket 05; ticket 01 implements developer archiving and
offline input generation, ticket 02 implements evidence-bearing injection,
persistence, replay, and dashboard/map inspection, ticket 03 bundles a real,
independently verifiable earthquake Example, and ticket 04 reports planned and
achieved emergency response.

## Context

An earthquake's location, event time, alert, magnitude, and significance are
source evidence. Imaging urgency and satellite resource use are simulator
assumptions. Mutable feeds must not become a runtime or replay dependency.
The governing contract is the [A1+B specification](../world-impact/a1-usgs-plus-b-latency/spec.md)
and [ticket 01](../world-impact/tickets/01-build-reproducible-usgs-cue-inputs.md).

## Decision

### Archive and developer inputs

Only the explicit `scripts/fetch_cue_archive.py` operation fetches USGS data.
It stores original response bytes in a new archive directory with the exact
requested URL, source `usgs`, timezone-aware retrieval time, response filename,
and raw-byte SHA-256. It refuses existing directories. Offline loading verifies
the checksum before parsing. Retrieval time stays in the manifest and is excluded
from generated conversion metadata.

The offline builder selects source event ids before normalizing. It validates
every selected occurrence, collapses equal normalized records, and rejects
conflicting occurrences of the same source/id pair. It does not model updates.
USGS GeoJSON coordinates are longitude, latitude, then depth. Only longitude and
latitude become imaging coordinates. Times are integer epoch milliseconds,
converted to timezone-aware UTC. Missing/null alerts become `unknown`; the four
source alert strings are accepted exactly. Missing/null magnitude and significance
remain absent. See the [official USGS format](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php).

Selected times must be in the half-open Scenario interval `[start, end)`. No
time shifting, clamping, clustering, or tiling occurs. One normalized earthquake
produces one ObservationRequest. Its id is `CUE-` plus the SHA-256 of compact
UTF-8 JSON `[source, source_event_id]`. Its descriptive name comes from an
explicit profile override or nonempty USGS place text, never its request id.

An author supplies duration, energy cost, storage cost, and optional satellite
assignment. Request construction reuses `ObservationRequestSchema` validation;
satellite assignment must name a Scenario satellite under ADR-0014. Severity
does not estimate or alter resource costs. Inputs sort by earthquake time, source,
then source event id. Stable JSON serialization and atomic replacement publish
the artifact only after all selected records validate.

### AMIS response policy

Policy version `usgs-earthquake-v1` applies this table:

| Normalized alert | Base priority | Deadline from earthquake time |
| --- | --- | --- |
| red | 5 | 12 hours |
| orange | 4 | 24 hours |
| yellow | 3 | 48 hours |
| green | 2 | 48 hours |
| unknown | 2 | 48 hours |

Magnitude at least 6 raises priority to 5 without changing the alert-based
deadline. Significance has no policy effect. These are AMIS assumptions, not
USGS recommendations or operational imaging commitments. Any policy change
requires a new version; generated artifacts record the version and explicit
imaging profile so an existing artifact retains its original meaning.

### Injection and replay boundary

The artifact is a developer input, not a MissionEvent. Each input carries its
intended earthquake UTC injection time, the existing `EMERGENCY_TASK` event type,
request, complete `source`/`source_event_id`/`alert_level` evidence group, and
optional magnitude/significance. It has no session event id, accepted simulated
time, or recorded windows. Ticket 02 supplies evidence-compatible injection;
ticket 03 supplies the real Example and exact-time runner.

ADR-0001 keeps the adaptive loop behind MissionSession. The runner must advance
the clock to the intended instant before injection. MissionSession assigns event
identity and time, generates orbital windows if needed, and records those
windows, including an empty set. Injection does not replan automatically.
ADR-0002 replay remains the pristine Scenario plus accepted ordered events,
without the archive or network. ADR-0008 stored orbital inputs and ADR-0012's
archive-then-replay boundary remain intact. No new EventType, Planner input,
runtime archive lookup, or changes to frozen actions are introduced.

### Ticket 03: bundled Example

The bundled Example replays USGS event `us6000u0xi`, M6.3, "102 km NE of
Norsup, Vanuatu", 2026-10-08T09:00:07.768Z, archived from
`https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson`
at `amis/data/cues/vanuatu-us6000u0xi-20261008/` (manifest and raw bytes
committed). `amis/examples.usgs_vanuatu_example()` builds a dated Scenario
(2026-10-07T12:00Z-2026-10-08T22:30Z, bounded by the stored Landsat-8
element epoch's 14-day validity window) with routine baseline demand; it
carries no emergency request. The committed developer cue input at
`amis/data/examples/usgs-vanuatu-2026-10-08/cue-inputs.json` (built by the
ticket 01 CLI from the committed archive and an explicit imaging profile)
supplies the request actually injected. `scripts/run_usgs_vanuatu_replay.py`
creates the baseline plan, advances the clock to the cue's exact recorded
time, checks the clock reached exactly that instant before injecting, and
optionally performs the separate explicit replan. The Example appears in the
`/examples` library; loading it creates a new Scenario, matching every other
Example. `ScenarioSummarySchema.briefing` carries the trainee-facing text
(from `amis/data/examples/usgs-vanuatu-2026-10-08/briefing.md`) that names
the real earthquake and separates it from this Example's hypothetical
satellite, imaging-resource, and point-target choices; it is null for every
Example without a bundled briefing.

The request's policy deadline (2026-10-10T09:00:07.768Z, the `green`-alert
48-hour offset) outlives the Scenario's end (2026-10-08T22:30:00Z, capped
by the stored Landsat 8 element's 14-day validity, not an authoring
choice); the Scenario end is the real binding constraint. A real daylight
pass over the epicenter under the Scenario's 60-degree off-nadir policy
opens at 2026-10-08T21:58:41Z, inside that horizon, so the request is
still demonstrably servable; `tests/test_usgs_vanuatu_bundle.py` asserts
the replan schedules it with `HIGHER_PRIORITY_TASK_INSERTED` and no
unscheduled requests, so this cannot regress silently.

`examples()` guards `orbital_example()` and `usgs_vanuatu_example()` with
independent `try/except ModuleNotFoundError` blocks: one Example's
builder failing (missing skyfield/sgp4) must not withhold the other.
`tests/test_usgs_vanuatu_bundle.py` also asserts `usgs_vanuatu_example()`
stays byte-identical to the committed `scenario.json` that generated
`cue-inputs.json`, so the two cannot silently drift apart.

### Planned and achieved response, and window-only feasibility

Ticket 04 measures latency from accepted event time to imaging start,
excluding downlinks. Planned values come from the selected plan; achieved values
come from authoritative execution/frozen history once imaging actually starts,
and remain stable across replans and reconstruction. Unserved and expired arrivals
remain visible with null acquisition fields. Planned and achieved means use
their own non-null denominators and expose counts. Negative latency is an error.
Historical-plan membership and current `measured_at` semantics remain explicit.

Implementation: `amis.metrics.compute_emergency_response` builds one
`EmergencyResponse` row per accepted `EMERGENCY_TASK` event whose request is in
the measured plan's RequestPool, ordered by arrival time then request id.
`MissionSession._executed_actions` supplies the authoritative history: the
current plan's frozen actions (start at or before the clock, carried forward
unchanged by every replan under ADR-0003) plus any recorded-plan action the
clock marked started. A historical plan's proposed start is never treated as
execution, and `compute_metrics` without that history reports nothing
achieved. A plan with no recorded RequestPool snapshot rebuilds its membership
from the event log and impacts, never the live pool. The
`time_to_first_acquisition_s` wire names follow the spec but hold mean
latencies over their own denominators. Because the history lives in persisted plans and the event log, the
existing reconstruction path restores it with no new table; resetting the
session clears it with the plans. A negative latency raises
`SimulationStateError` naming the request, event, and action. The plan-metrics
route, `MetricsResult.to_dict`, and frontend `MetricsSchema` expose
`emergency_response`, `time_to_first_acquisition_s`,
`achieved_time_to_first_acquisition_s`, and the three counts. The dashboard
shows each mean with its denominator and the total, per-request planned and
achieved attribution, and the note that acquisition means imaging started. The
mission timeline draws arrival-to-planned and arrival-to-achieved segments from
the selected plan's own metrics (an earlier version's when selected, labelled
with that version), keeps both when they differ, and marks
unserved or expired arrivals at arrival rather than as zero-width successes.

Ticket 05 will provide a read-only, scenario-wide orbital window query starting
at Scenario start. Duration, deadline, Scenario horizon, geometry, daylight,
pointing policy, culmination placement, and satellite availability constrain the
result. Each satellite appears, including those without a suitable window, with
deterministic time/id ordering. `scope: window_only` excludes current plans,
resources, pairwise slew, active outages, and reservations. The query changes no
session data or identifiers and makes no scheduling promise.

## Consequences

Existing manual emergency arrivals and application behavior remain unchanged.
Ticket 02 extends the `EMERGENCY_TASK` payload, API schema, frontend types,
dashboard emergency form, and dashboard/map inspection with the optional
evidence group. One domain validator owns the all-or-nothing rule and the API
schema delegates to it; MissionSession applies it before computing orbital
windows, so rejected evidence has no observable effect. An evidence-free
payload keeps its previous serialized shape, and the payload refuses unknown
keys such as a generated input's intended injection time. Ticket 01 does not
extend event payloads, API schemas, persistence, Examples,
metrics, feasibility, or dashboard UI. Tests use explicitly synthetic USGS-shaped
records, not fabricated historical evidence. Selecting and bundling a verifiable
real earthquake belongs to ticket 03.

A3 CEMS centroid-only conversion is a future direction requiring its own spec;
it is not implemented here. Other research adapters and policy features remain
outside ticket 01.
