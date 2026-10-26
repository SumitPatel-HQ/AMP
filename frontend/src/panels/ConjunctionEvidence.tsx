import type { MissionEventSchema } from "../api/client";

type Outage = Extract<MissionEventSchema, { event_type: "SATELLITE_UNAVAILABLE" }>["payload"];
type RecordedOutage = Outage & { event_id: string };

export function ConjunctionEvidenceDetails({ event }: { event: MissionEventSchema }) {
  if (event.event_type !== "SATELLITE_UNAVAILABLE" || !event.payload.conjunction) return null;
  return <OutageDetails payload={event.payload} eventId={event.id} />;
}

function OutageDetails({ payload: p, eventId }: { payload: Outage; eventId: string }) {
  const e = p.conjunction;
  if (!e) return null;
  return <div aria-label="Conjunction evidence" className="space-y-1 p-2 text-xs text-neutral-300">
    <p>{p.satellite_id} · {eventId} · encounter {e.encounter_id}</p>
    <p>Matched NORAD {e.matched_norad_id} · counterpart NORAD {e.counterpart_norad_id}</p>
    <p>TCA {e.tca} · miss distance {e.miss_distance_km} km</p>
    <p>Source maximum probability {e.maximum_probability} · threshold {e.threshold}</p>
    <p>Assumed outage [{p.outage_start}, {p.outage_end}) · padding {e.pre_padding_s}s / {e.post_padding_s}s</p>
    <p>Source attribution: {e.source} · policy {e.policy_version}</p>
    <p>Threshold and outage interval are AMIS simulation policy. This prediction does not confirm a maneuver.
      Orbit change, fuel use, delta-v, and maneuver confirmation are not modeled.</p>
  </div>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

/** Trace metadata is untyped JSON; display only a complete recorded evidence group. */
function isRecordedOutage(value: unknown): value is RecordedOutage {
  if (!isRecord(value) || !isRecord(value.conjunction)) return false;
  const e = value.conjunction;
  return ["event_id", "satellite_id", "outage_start", "outage_end"].every(key => typeof value[key] === "string")
    && ["source", "encounter_id", "tca", "policy_version"].every(key => typeof e[key] === "string")
    && ["matched_norad_id", "counterpart_norad_id", "miss_distance_km", "maximum_probability", "threshold",
      "pre_padding_s", "post_padding_s"].every(key => typeof e[key] === "number" && Number.isFinite(e[key]));
}

export function ConjunctionTraceEvidence({ records }: { records: unknown }) {
  if (!Array.isArray(records)) return null;
  return records.filter(isRecordedOutage).map(record =>
    <OutageDetails key={record.event_id} payload={record} eventId={record.event_id} />);
}
