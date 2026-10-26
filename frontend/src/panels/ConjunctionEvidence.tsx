import type { MissionEventSchema } from "../api/client";
import type { components } from "../api/schema";

type Outage = Extract<MissionEventSchema, { event_type: "SATELLITE_UNAVAILABLE" }>["payload"];
type Evidence = components["schemas"]["ConjunctionEvidenceSchema"];
type RecordedOutage = Outage & { event_id: string; conjunction: Evidence };

export function ConjunctionEvidenceDetails({ event }: { event: MissionEventSchema }) {
  if (event.event_type !== "SATELLITE_UNAVAILABLE" || !event.payload.conjunction) return null;
  return <OutageDetails payload={event.payload} eventId={event.id} />;
}

function OutageDetails({ payload, eventId }: { payload: Outage; eventId: string }) {
  const evidence = payload.conjunction;
  if (!evidence) return null;
  return <div aria-label="Conjunction evidence" className="space-y-1 p-2 text-xs text-neutral-300">
    <p>{payload.satellite_id} · {eventId} · encounter {evidence.encounter_id}</p>
    <p>Matched NORAD {evidence.matched_norad_id} · counterpart NORAD {evidence.counterpart_norad_id}</p>
    <p>TCA {evidence.tca} · miss distance {evidence.miss_distance_km} km</p>
    <p>Source maximum probability {evidence.maximum_probability} · threshold {evidence.threshold}</p>
    <p>Assumed outage [{payload.outage_start}, {payload.outage_end}) · padding {evidence.pre_padding_s}s / {evidence.post_padding_s}s</p>
    <p>Source attribution: {evidence.source} · policy {evidence.policy_version}</p>
    <p>Threshold and outage interval are AMIS simulation policy. This prediction does not confirm a maneuver.
      Orbit change, fuel use, delta-v, and maneuver confirmation are not modeled.</p>
  </div>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

const isString = (value: unknown): value is string => typeof value === "string";
const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
type FieldGuards<T> = { [Key in keyof T]-?: (value: unknown) => value is T[Key] };

// Schema-checked field coverage: generated schema changes must update these guards.
const evidenceFields = {
  source: isString,
  encounter_id: isString,
  tca: isString,
  policy_version: isString,
  matched_norad_id: isFiniteNumber,
  counterpart_norad_id: isFiniteNumber,
  miss_distance_km: isFiniteNumber,
  maximum_probability: isFiniteNumber,
  threshold: isFiniteNumber,
  pre_padding_s: isFiniteNumber,
  post_padding_s: isFiniteNumber,
} satisfies FieldGuards<Evidence>;

function isConjunctionEvidence(value: unknown): value is Evidence {
  return isRecord(value) && Object.entries(evidenceFields).every(([key, guard]) => guard(value[key]));
}

const recordedOutageFields = {
  event_id: isString,
  satellite_id: isString,
  outage_start: isString,
  outage_end: isString,
  conjunction: isConjunctionEvidence,
} satisfies FieldGuards<RecordedOutage>;

/** Trace metadata is untyped JSON; narrow it to the generated schema before display. */
function isRecordedOutage(value: unknown): value is RecordedOutage {
  return isRecord(value) && Object.entries(recordedOutageFields).every(([key, guard]) => guard(value[key]));
}

export function ConjunctionTraceEvidence({ records }: { records: unknown }) {
  if (!Array.isArray(records)) return null;
  return records.filter(isRecordedOutage).map(record =>
    <OutageDetails key={record.event_id} payload={record} eventId={record.event_id} />);
}
