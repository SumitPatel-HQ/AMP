import type { MissionEventSchema } from "../api/client";

export function ConjunctionEvidenceDetails({ event }: { event: MissionEventSchema }) {
  if (event.event_type !== "SATELLITE_UNAVAILABLE" || !event.payload.conjunction) return null;
  const p = event.payload;
  const e = event.payload.conjunction;
  return <div aria-label="Conjunction evidence" className="space-y-1 p-2 text-xs text-neutral-300">
    <p>{p.satellite_id} · {event.id} · encounter {e.encounter_id}</p>
    <p>Matched NORAD {e.matched_norad_id} · counterpart NORAD {e.counterpart_norad_id}</p>
    <p>TCA {e.tca} · miss distance {e.miss_distance_km} km</p>
    <p>Source maximum probability {e.maximum_probability} · threshold {e.threshold}</p>
    <p>Assumed outage [{p.outage_start}, {p.outage_end}) · padding {e.pre_padding_s}s / {e.post_padding_s}s</p>
    <p>Source attribution: {e.source} · policy {e.policy_version}</p>
    <p>Threshold and outage interval are AMIS simulation policy. This prediction does not confirm a maneuver.
      Orbit change, fuel use, delta-v, and maneuver confirmation are not modeled.</p>
  </div>;
}
