# Developer USGS archives and inputs

This directory is the intended location for explicitly fetched archives.
Ticket 01 bundles no real earthquake or Example. No archive is loaded at
application startup or by the planner. U.S. Geological Survey is the source
credit for USGS evidence; AMIS priority, deadlines, and imaging costs are
simulation assumptions.

Use the repository's installed Python environment from its root. Fetching is
an explicit developer action, for example:

```powershell
python scripts/fetch_cue_archive.py --source-url "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson" --archive-dir amis/data/cues/my-usgs-archive
```

The command archives the bytes actually returned at execution time. It does not
claim that a mutable feed contains any event from the research's earlier probe.
An archive is a new directory containing `response.geojson` and `manifest.json`.
The manifest records source, exact requested URL, aware retrieval time, response
filename, and raw-byte SHA-256. Reusing a directory fails. Inspect and commit the
response and manifest together if retaining evidence for future work.

Prepare an existing Scenario JSON and an explicit imaging profile JSON:

```json
{
  "duration_s": 60,
  "energy_cost_wh": 10,
  "storage_cost_mb": 25
}
```

These sample resource numbers are hypothetical author inputs, not earthquake
facts or default values. Optional `satellite_id` pins the request to a Scenario
satellite. Optional `target_name` overrides the archived place text. If both
name sources are absent or empty, the build fails. Missing duration or costs
fail; zero costs are allowed by existing ObservationRequest validation.

Select source ids explicitly from the actual archive:

```powershell
python scripts/build_cue_events.py scenario.json --archive-manifest amis/data/cues/my-usgs-archive/manifest.json --imaging-profile imaging-profile.json --event-id SOURCE_EVENT_ID --out cue-inputs.json
```

Repeat `--event-id` to select several earthquakes. Alternatively use `--all`
to explicitly select every archived record. Each selected time must satisfy
`Scenario.start_time <= earthquake_time < Scenario.end_time`. Unselected invalid
or out-of-range records are ignored. Missing selections, invalid selected
records, checksum mismatches, and conflicting duplicates fail before output
publication. A failed build preserves any previous output. Successful builds
replace the complete output atomically. The output parent directory must exist.

The artifact contains:

- `metadata.artifact_type: developer-cue-inputs`, Scenario id, policy version
  `usgs-earthquake-v1`, the author imaging profile, and archive identity/checksum.
- `inputs`, ordered by UTC event time, source, then source event id. Each has
  `injection_time`, `event_type: EMERGENCY_TASK`, and a payload containing the
  ObservationRequest and source evidence group, with optional `mag` and `sig`.

Inputs omit session-assigned event ids and recorded observation windows. They
are not accepted event logs or directly supported evidence-bearing API payloads
until ticket 02 lands. Ticket 03 will provide a real Example and exact-time
injection runner. Conversion and publication never fetch data. Retrieval times
remain only in archive manifests so equivalent conversions are byte stable.

The policy table and replay boundaries are in
[ADR-0015](../../../.doc/adr/0015-usgs-cue-replay.md).
