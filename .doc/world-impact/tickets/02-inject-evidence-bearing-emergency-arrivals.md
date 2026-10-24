# 02: Inject, inspect, and map evidence-bearing emergency arrivals

**What to build:** An operator can inject an ordinary emergency arrival or one carrying cue evidence through the existing emergency interface, inspect that evidence in the dashboard and on linked map markers, and retrieve the same accepted event after persistence and offline replay.

**Blocked by:** None (can start immediately).

**Status:** implemented

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

- [x] The existing `EMERGENCY_TASK` accepts nonempty `source`, nonempty `source_event_id`, and normalized `alert_level` as an all-or-nothing evidence group. Alert values are red, orange, yellow, green, or unknown. Partial groups and unsupported values produce actionable validation errors.
- [x] Optional finite numeric `mag` and `sig` require the core evidence group and are omitted when absent. An evidence-free manual payload preserves its previous serialized shape and behavior.
- [x] Domain conversion, MissionSession validation, API schemas, frontend types, event retrieval, persistence, and reconstruction preserve evidence consistently. Existing persisted events remain loadable.
- [x] An accepted event uses the current simulated clock and a stable session-assigned event identifier. Clients cannot rewrite its recorded time using the intended time in a generated developer input.
- [x] Orbital injection with no supplied windows uses the existing provider and records the resulting windows in the accepted event, including an empty set. Recorded windows are reused during replay rather than regenerated.
- [x] Duplicate request injection and invalid evidence fail before adding an event or altering resources, RequestPool, or plan state. An accepted cue with no feasible action remains a legitimate emergency arrival.
- [x] Injection preserves the pristine Scenario, stores ordinary Impact against the selected plan, and leaves replan as a separate explicit operation. Existing frozen-action, expiry, and ReasonCode behavior remains authoritative.
- [x] The dashboard's existing event inspection shows source, source event identifier, alert level, and available magnitude/significance. It shows `U.S. Geological Survey` for USGS evidence and labels priority/deadline choices as AMIS simulation policy, not source recommendations.
- [x] Evidence remains consistent after injection, reset, reload, and session reconstruction. Reset removes accepted event evidence with the rest of the event log.
- [x] Replaying a pristine Scenario and accepted ordered events preserves request data, evidence, recorded windows, and ordinary impact/explanation behavior without archive or network access.

- [x] Evidence-bearing USGS arrivals create a cue marker at the normalized request point. The map uses backend event/request data and the established longitude/latitude interpretation.
- [x] Each marker links to the same accepted event identifier and request identifier used in event inspection and metrics. Selecting it exposes source, source event identifier, alert level, and available magnitude/significance through existing dashboard access patterns.
- [x] Cue evidence displays `U.S. Geological Survey` and the AMIS policy notice beside the evidence. A cue's arrival location is not labelled as completed imaging or an operational response guarantee.
- [x] Rendering, replan, session reload, and switching selected plans do not duplicate markers for the same accepted event. Marker identity derives from recorded event/request identity.
- [x] Injection adds the marker, reset removes it with the event log, and loading another Scenario removes the previous Scenario's cue markers. Reload reconstructs markers from accepted evidence without archive or network access.
- [x] Existing manual evidence-free emergencies and existing map layers continue to work. Markers use existing dashboard styling and selection conventions.
