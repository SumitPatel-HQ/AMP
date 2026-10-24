# World impact work

Source research: [AMIS world-impact feature research](../../.research/reference/amis-world-impact-research.md).
Each folder below is one ranked slice from that report, so the folder name tells you which letter it implements.

## Slices

- [A1 USGS plus B latency and feasibility](a1-usgs-plus-b-latency/spec.md) — first build. Status: tickets 01-05 implemented.
- [A3 CEMS activation replay](a3-cems/README.md) — centroid-only point conversion. Status: specification and two approved tickets ready; implementation pending.
- [E conjunction-derived Satellite outages](e-conjunction/README.md) — SOCRATES conjunction evidence using the existing outage flow. Status: specification and two approved tickets ready; implementation pending.
- [C fair multi-requester tasking](c-fair-requester/README.md) — requester metrics and opt-in fairness policy. Status: specification and two approved tickets ready; implementation pending.
- [D archive-first imagery satisfaction](d-archive-check/README.md) — catalogue checks with a distinct archive-fulfilled outcome. Status: specification and two approved tickets ready; implementation pending.

## Scheduled next

The requester scheduled these eight remaining candidates for the next planning batch. They need their own specifications and tickets before implementation; no calendar dates or implementation order are assigned by this status.

- **A2 — Multi-hazard alerts (GDACS).** Scheduled next; establish source contracts and redistribution terms before committing data.
- **A4 — Active-fire alerts (NASA FIRMS).** Scheduled next; define deterministic clustering and developer-only credential handling.
- **A5 — Methane super-emitter cues.** Scheduled next; confirm permitted use and define honest sensor/capability assumptions.
- **A6 — Dark-vessel cues.** Scheduled next; establish usable detection endpoints, permitted use, and a fixed-point/area-revisit approximation.
- **A7 — Forest-loss alerts.** Scheduled next; establish source/licensing and define its relationship to recurring follow-up.
- **F — Recurring monitoring campaigns.** Scheduled next; define deterministic request expansion and practical Scenario horizons.
- **G — Training packs.** Scheduled next; select available feature content and define briefings, exercises, and scoring without creating prerequisites for the current four feature branches.
- **I — Benchmark alignment.** Scheduled next; assess instance-format compatibility and document modeling differences before importing data.

These are research-derived planning considerations, not newly verified source contracts. Scheduling does not resolve licensing or modeling questions. Preserve independent feature branches wherever the eventual scope permits; document genuine dependencies in the next specifications rather than silently coupling them to A3, E, C, or D.

**H — Cloud-probability-aware planning remains rejected for now** and is not included in the scheduled-next batch.

## Ticket batch scope

The five approved tickets in [tickets/](tickets/README.md) cover only A1 USGS earthquake cue replay and B response latency and window-only feasibility. They are implemented, completing that first slice, not the full research roadmap. A3, E, C, and D each have a specification and two approved tickets, with no cross-feature blockers. A2, A4-A7, F, G, and I are scheduled next for specification and ticket planning. H cloud-aware planning remains rejected for now.

## Current handoff

The current implementation frontier is ticket 01 in each of A3, E, C, and D. Each feature's ticket 02 depends only on its own ticket 01. Each feature can be implemented on a separate branch and merged without waiting for the others. The scheduled-next batch above is the subsequent planning frontier.

The requester confirmed MissionSession lifecycle/replay as the primary verification seam, supplemented by developer archive-builder checks for external inputs and focused API/dashboard checks. Specifications and approved tickets are stored locally; this planning work does not implement application behavior, run tests, or publish external issues. The A1+B specification still retains its earlier planning snapshot; the ticket index is the current delivery-status reference.

## Rules every slice respects

- Replay is the pristine Scenario plus the ordered event log.
- External data follows archive-then-replay: a developer script fetches, raw responses are committed with a manifest, a pure offline rule turns the archive into recorded events with evidence, the Planner never sees raw data.
- A Cue enters only as an emergency request arrival carrying evidence.
