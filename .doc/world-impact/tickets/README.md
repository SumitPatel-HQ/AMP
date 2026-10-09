# A1 USGS replay and B response tickets

Status: tickets 01-05 implemented. The batch covers A1+B only.

Source of implementation requirements: [A1+B specification](../a1-usgs-plus-b-latency/spec.md). Source of feature rationale: [world-impact research](../../reference/amis-world-impact-research.md), sections A1 and B. The specification governs detailed behavior and scope.

| Ticket | Blocked by | Independently observable delivery |
| --- | --- | --- |
| [01: Build reproducible USGS cue inputs](01-build-reproducible-usgs-cue-inputs.md) | None | A developer archives evidence and builds deterministic, validated emergency inputs offline. |
| [02: Inject, inspect, and map evidence-bearing emergency arrivals](02-inject-evidence-bearing-emergency-arrivals.md) | None | Emergency evidence survives injection, dashboard/map inspection, persistence, and replay. |
| [03: Bundle a real earthquake replay Example](03-bundle-real-earthquake-replay-example.md) | 01, 02 | A trainee loads a dated Example offline, injects its real cue at the exact time, and explicitly replans. |
| [04: Report planned and achieved emergency response](04-report-emergency-response.md) | None | The API, dashboard, and timeline distinguish intended response, actual imaging starts, and unserved requests. |
| [05: Compare window-only feasibility](05-compare-window-only-feasibility.md) | None | A duty officer compares each satellite's earliest suitable window without changing the mission. |

## Implementation scope and pending research

These five tickets implement only **A1: USGS earthquake cue replay** and **B: response latency and window-only feasibility**, including their backend, persistence, Example, dashboard, map, and timeline behavior. Completing this batch does not complete the full world-impact research roadmap.

| Research feature | Status outside this ticket batch |
| --- | --- |
| A3: CEMS activation replay | Pending, planned as the next slice; needs its own specification and tickets. |
| E: Conjunction avoidance | Pending for a later slice; needs its own specification and tickets. |
| C: Requester fairness | Pending for a later slice; needs its own specification and tickets. |
| D: Archive-first imaging | Pending for a later slice; needs its own specification and tickets. |
| A2 and A4-A7: Other cue adapters | Outside this batch, unscheduled; require separate scope and source/licensing decisions. |
| F: Monitoring campaigns | Deferred, with no fixed implementation stage. |
| G: Training packs | Deferred, with no fixed implementation stage. |
| I: Benchmark alignment | Deferred, with no fixed implementation stage. |
| H: Cloud-probability-aware planning | Rejected for now; not a committed later stage. |

The later features are not acceptance criteria or blockers for these five tickets. A1+B tickets 01-05 are implemented.

## Dependency rationale

01, 02, 04, and 05 can start independently. Evidence injection uses the specification's payload contract, so it does not wait for the archive builder. Response reporting works for existing manual emergency arrivals, so it does not wait for USGS ingestion. Feasibility uses stored Scenario inputs and the existing orbital provider, so it does not wait for injection or latency.

03 needs both generated cue inputs from 01 and evidence-compatible injection from 02. Map markers are delivered with evidence injection in 02. Planned and achieved metrics, persistence-compatible execution history, dashboard reporting, and timeline presentation are delivered together in 04.

No standalone prefactor is required by current source inspection. Sharing orbital-provider behavior belongs to 05. Serialization and persistence work belong to the ticket whose behavior requires them.

## Delivery constraints

- These tickets cover A1+B only. A3 CEMS, conjunction outages, requester fairness, archive satisfaction, campaigns, training packs, and benchmark imports require their own specifications. Cloud-probability-aware planning remains rejected for now.
- Preserve the MissionSession facade, immutable Scenario, recorded-event replay, stored orbital inputs, per-satellite behavior, Planner interfaces, ReasonCodes, and explicit replan operation.
- The only network operation is the explicit developer archive fetch. Startup, normalization, Example loading, and replay remain offline.
- Acceptance checkboxes describe observable outcomes. Ticket decomposition requires no test writing or execution. There is no standalone testing ticket; implementation verification must follow the requester's instructions then in force.
- Preserve existing metric meanings and dashboard styling. A window-only result never promises a resource-feasible action or operational disaster response.

## Specification coverage

| Specification acceptance criteria | Tickets |
| --- | --- |
| 1-3: integrity, deterministic policy, explicit imaging profile | 01 |
| 4: real archived earthquake and honest Example briefing | 03 |
| 5-8: exact-time injection, compatibility, replan, offline replay | 02, 03 |
| 9-11: response states, stable achieved values, historical-plan membership | 04 |
| 12: complete, deterministic, read-only feasibility | 05 |
| 13: evidence, markers, latency, counts, attribution, lifecycle refresh | 02, 04, 05 |
| 14: established domain and offline behavior | All tickets |
