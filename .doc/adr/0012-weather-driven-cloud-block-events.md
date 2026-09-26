# Weather-driven cloud-block events

Status: accepted (Wave 5, spec decision 28)

## Context

Cloud blocks so far are hand-injected: an operator names a request and a
window. The research (section 13) found that archived cloud fields
(Open-Meteo hourly `cloud_cover`, reanalysis back to 1940) can replace
hand injection without any live call. The risk is provenance drift: if
the planner or the session ever reads weather directly, a replay would
need the network and two runs could disagree.

## Decision

### Offline archive

- Raw hourly responses live under `amis/data/weather/` with a manifest
  holding the source URL, retrieval time, a per-location SHA-256, and a
  `sample` flag marking hand-written excerpts. `load_archive` verifies
  every record before returning it; a checksum mismatch fails loudly.
- Only `scripts/fetch_weather_archive.py` (developer-run, like the
  CelesTrak fetch script) touches the network. The server, planner,
  session, and routes never fetch.
- `normalize_archive` flattens the Open-Meteo hourly shape into
  `CloudSample` values (target, time, coverage percent, source). Times
  must carry a timezone; coverage must be a finite percentage. Either
  violation is a `ValueError`, never a silent skip.

### Threshold rule

- `cloud_block_payloads_for_windows` reads, per valid window, the
  sample nearest the window's culmination (stored peak time, else the
  midpoint) for that request's target, within a 30-minute default
  tolerance. Coverage at or above the threshold blocks; below it, or
  with no nearby sample, the window is left alone.
- Already-invalid windows are skipped, so a weather pass never
  overwrites a recorded cause. Samples never leak across targets:
  matching is on exact coordinates.
- The rule is pure: samples, requests, and windows in, payloads out.

### Recorded events

- A weather-derived `CLOUD_BLOCK` payload carries the evidence triple
  `source`, `cloud_cover_pct`, `threshold_pct`. The HTTP schema and the
  session facade both enforce all-or-nothing: a block carries all three
  or none, and percentages must be finite and within 0-100.
- Injection, impact, replan, diff, traces, and metrics treat the event
  exactly like a hand-injected block. The planner never sees weather.
- Replay is the pristine scenario plus the event log (ADR-0002): it
  needs neither the archive nor the network. The evaluation-style
  socket guard proves this in `tests/test_weather_replay.py`.
- `scripts/build_weather_events.py` converts an archive plus scenario
  and window files into event-request JSON offline, printing the
  per-window verdict so the operator sees why each window blocked.

## Consequences

- `CloudBlockPayload.to_dict` omits absent evidence keys, so payloads
  recorded before Wave 5 keep their exact serialized shape; no database
  migration is needed (the event payload column is already JSON).
- A mission with no archive behaves exactly as before: hand-injected
  blocks are unchanged.
- Coverage honesty limits: hourly reanalysis at ~25 km resolution
  judges a minutes-long window by its nearest hour. The threshold,
  tolerance, and source travel with the event so an examiner can see
  the coarseness instead of trusting a false precision.
