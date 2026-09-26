# Wave 3 spacecraft realism: outages, settling time, culmination placement, derived costs

## Payload outages

Payload outages arrive as `SATELLITE_UNAVAILABLE` events carrying a satellite id and an
`[outage_start, outage_end)` interval. The spans are read from the event log whenever
planning, validation, or impact runs, so replays need nothing outside the scenario and
the event log. Validation rejects an unfrozen action whose interval overlaps an outage
span with reason `SATELLITE_UNAVAILABLE`; frozen actions stay exempt per ADR-0003.
The base `available` flag keeps the scenario's meaning, so actions outside the span
keep validating against it; the span only narrows what the flag allows. No window
provider changes: windows keep their geometry and only actions are judged against
the span.

## Settling time

`WindowPolicy.settling_time_s` is a single per-mission gap between consecutive
observations, enforced by extending the overlap rule: two actions conflict unless each
starts at least the gap after the other ends. Request durations do NOT include the
settling time; the gap lives between actions, may extend past a window's end, and is
rounded up to whole seconds in the CP-SAT model. A zero gap is the historical overlap
rule, so missions without the field behave exactly as before.

## Culmination placement

`WindowPolicy.culmination_placement` is a per-mission option. When on, the greedy
planner tries the peak-centered start (`peak_time` minus half the duration) before the
window start whenever that centered placement fits inside the window; the stability
rule still orders candidate windows, so replans keep their previous window while it
stays feasible. CP-SAT keeps start variables free and adds a geometry tie-break that
cannot displace a higher-utility selection, so both planners agree on utility while
the greedy plan matches peak-centered starts.

## Derived cost defaults

Energy and storage defaults come from engineering numbers in the scenario builder
only: `energy_wh = power_w * duration_s / 3600` and
`storage_mb = data_rate_mbps * duration_s / 8`. Stored costs keep their meaning, so
the planner and the constraint engine do not change.
