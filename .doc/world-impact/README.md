# World impact work

Source research: `amis-world-impact-research.md` in `.doc/reference/`.
Each folder below is one ranked slice from that report, so the folder name tells you which letter it implements.

## Slices

- `a1-usgs-plus-b-latency/` — first build. A1 USGS earthquake cue replay plus B response-latency metric and feasibility query. Status: ticket 01 implemented; tickets 02-05 remain pending.
- `a3-cems/` — second build. CEMS activation cue replay with centroid-only area rule. Status: planned.
- `e-conjunction/` — SOCRATES conjunction outage as satellite outage. Status: planned.
- `c-fair-requester/` — fair multi-requester tasking. Status: planned.
- `d-archive-check/` — archive-first check against Copernicus STAC. Status: planned.
- `deferred-f-g-h-i/` — campaigns, training packs, cloud-aware planning (rejected for now), benchmark alignment. Status: deferred.

## Ticket batch scope

The five approved tickets in [tickets/](tickets/README.md) cover only A1 USGS earthquake cue replay and B response latency and window-only feasibility. Completing them will complete that first slice, not the full research roadmap. A3, E, C, and D remain pending later slices. Other cue adapters are unscheduled; F, G, and I are deferred. H cloud-aware planning is rejected for now rather than promised for a later stage.

## Current handoff

Use `a1-usgs-plus-b-latency/spec.md` as the input to `/to-tickets`. It contains the stories, contracts, observable acceptance criteria, scope boundaries, and dependency guidance for the first implementation. The requester has asked for no test work during this planning phase.

The other names above describe planned slices. Their folders and specifications are created when work on each slice begins.

## Rules every slice respects

- Replay is the pristine Scenario plus the ordered event log.
- External data follows archive-then-replay: a developer script fetches, raw responses are committed with a manifest, a pure offline rule turns the archive into recorded events with evidence, the Planner never sees raw data.
- A Cue enters only as an emergency request arrival carrying evidence.
