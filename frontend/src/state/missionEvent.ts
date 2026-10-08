import type {
  EmergencyTaskPayloadSchema,
  MissionEventRequest,
  MissionEventSchema,
  ObservationRequestSchema,
  ReasonCode,
  ScenarioSchema,
} from "../api/client";
import type { ReplanResult } from "./types";

/** One line naming what an event's payload carries, in the backend's own terms. */
export function eventSummary(event: MissionEventSchema): string {
  switch (event.event_type) {
    case "CLOUD_BLOCK": {
      const base = `${event.payload.request_id} / ${event.payload.window_id}`;
      if (
        event.payload.source != null &&
        event.payload.cloud_cover_pct != null &&
        event.payload.threshold_pct != null
      ) {
        return `${base} · ${event.payload.cloud_cover_pct}% cloud ≥ ${event.payload.threshold_pct}% (${event.payload.source})`;
      }
      return base;
    }
    case "BATTERY_DROP":
      return `${event.payload.satellite_id} battery → ${event.payload.new_battery_wh.toFixed(1)} Wh`;
    case "EMERGENCY_TASK": {
      const count = event.payload.windows?.length ?? 0;
      const base = `${event.payload.request.id} · P${event.payload.request.priority} · ${count} window${
        count === 1 ? "" : "s"
      }`;
      const evidence = cueEvidence(event);
      return evidence === null
        ? base
        : `${base} · ${evidence.alertLevel} alert ${evidence.sourceEventId} (${evidence.sourceLabel})`;
    }
    case "SATELLITE_UNAVAILABLE":
      return `${event.payload.satellite_id} payload outage`;
    case "COMMUNICATION_OUTAGE":
      return `${event.payload.station_id} comm outage`;
  }
}

/** Display names for evidence sources; any other source shows as recorded. */
const SOURCE_LABELS: Record<string, string> = { usgs: "U.S. Geological Survey" };

/** Shown beside cue evidence: the source reports the event, AMIS chose the rest. */
export const CUE_POLICY_NOTICE =
  "Priority and deadline are AMIS simulation policy, not source recommendations.";

/** A normalized cue alert level, the backend's `AlertLevel` (ADR-0015). */
export type CueAlertLevel = NonNullable<EmergencyTaskPayloadSchema["alert_level"]>;

/** Every alert level the backend accepts; `unknown` marks an absent source alert. */
export const CUE_ALERT_LEVELS: readonly CueAlertLevel[] = ["red", "orange", "yellow", "green", "unknown"];

function isAlertLevel(value: unknown): value is CueAlertLevel {
  return typeof value === "string" && (CUE_ALERT_LEVELS as readonly string[]).includes(value);
}

function isFiniteOrAbsent(value: unknown): boolean {
  return value == null || (typeof value === "number" && Number.isFinite(value));
}

/** The source evidence an emergency arrival carries, as recorded in its accepted event. */
export interface CueEvidence {
  eventId: string;
  requestId: string;
  source: string;
  sourceLabel: string;
  sourceEventId: string;
  alertLevel: CueAlertLevel;
  /** Source-reported USGS magnitude (unitless), when the source gave one. */
  mag: number | null;
  /** Source-reported USGS significance score (unitless), when the source gave one. */
  sig: number | null;
}

/**
 * The evidence on an evidence-bearing EMERGENCY_TASK, or null for any other
 * event. Mirrors the backend rule: only a complete group with non-blank
 * source/id, a known alert level and finite optional numbers is evidence, so
 * a shape the backend would reject is never displayed as a cue.
 */
export function cueEvidence(event: MissionEventSchema): CueEvidence | null {
  if (event.event_type !== "EMERGENCY_TASK") return null;
  const { source, source_event_id: sourceEventId, alert_level: alertLevel, mag, sig } = event.payload;
  if (
    typeof source !== "string" ||
    source.trim() === "" ||
    typeof sourceEventId !== "string" ||
    sourceEventId.trim() === "" ||
    !isAlertLevel(alertLevel) ||
    !isFiniteOrAbsent(mag) ||
    !isFiniteOrAbsent(sig)
  ) {
    return null;
  }
  return {
    eventId: event.id,
    requestId: event.payload.request.id,
    source,
    sourceLabel: SOURCE_LABELS[source] ?? source,
    sourceEventId,
    alertLevel,
    mag: event.payload.mag ?? null,
    sig: event.payload.sig ?? null,
  };
}

/** An emergency request, which enters the mission through the event log, never the scenario. */
export interface IntroducedRequest {
  eventId: string;
  request: ObservationRequestSchema;
}

export function introducedRequests(events: readonly MissionEventSchema[]): IntroducedRequest[] {
  return events.flatMap((event) =>
    event.event_type === "EMERGENCY_TASK"
      ? [{ eventId: event.id, request: event.payload.request }]
      : [],
  );
}

/** Every request the mission holds: the scenario's own, then those the event log introduced. */
export function missionRequestPool(
  scenario: ScenarioSchema,
  events: readonly MissionEventSchema[],
): ObservationRequestSchema[] {
  return [...scenario.requests, ...introducedRequests(events).map((entry) => entry.request)];
}

/** A request the revised plan leaves out that its parent did not already leave out. */
export interface NewlyUnscheduled {
  requestId: string;
  reasonCode: ReasonCode;
  /** `dropped`: the backend diff reports it DROPPED; `arrived`: absent from the parent plan. */
  kind: "dropped" | "arrived";
}

/**
 * The requests a replan newly left unscheduled, read from the backend: the
 * diff's DROPPED entries with its reason codes, plus requests that entered the
 * pool after the parent plan (an emergency request) and are in the revised
 * plan's own unscheduled list. Nothing is compared here beyond membership.
 */
export function newlyUnscheduled({ initialPlan, revisedPlan, diff }: ReplanResult): NewlyUnscheduled[] {
  const dropped = diff.entries
    .filter((entry) => entry.change_type === "DROPPED")
    .map((entry) => ({ requestId: entry.request_id, reasonCode: entry.reason_code, kind: "dropped" as const }));
  const inParent = new Set([
    ...initialPlan.actions.map((action) => action.request_id),
    ...initialPlan.unscheduled.map((entry) => entry.request_id),
  ]);
  const arrived = revisedPlan.unscheduled
    .filter((entry) => !inParent.has(entry.request_id))
    .map((entry) => ({ requestId: entry.request_id, reasonCode: entry.reason_code, kind: "arrived" as const }));
  return [...dropped, ...arrived];
}

/** The one explicit window an emergency request is injected with. */
export function emergencyWindowId(requestId: string): string {
  return `WIN-${requestId}-1`;
}

/**
 * The emergency request form, as the inputs hold it. Times are UTC in the
 * `YYYY-MM-DDTHH:MM` shape a datetime-local input reads and writes.
 */
export interface EmergencyRequestForm {
  requestId: string;
  targetLat: string;
  targetLon: string;
  priority: string;
  durationS: string;
  deadline: string;
  energyCostWh: string;
  storageCostMb: string;
  windowStart: string;
  windowEnd: string;
  /**
   * Optional cue evidence. Leave all blank for a manual arrival; otherwise
   * source, source event id and alert level go together, and magnitude and
   * significance (USGS, unitless) are optional numbers.
   */
  source?: string;
  sourceEventId?: string;
  alertLevel?: string;
  mag?: string;
  sig?: string;
}

type EmergencyEvidencePayload = Pick<
  EmergencyTaskPayloadSchema,
  "source" | "source_event_id" | "alert_level" | "mag" | "sig"
>;

/**
 * The evidence the form carries, under the backend's all-or-nothing rule:
 * `{}` when every evidence field is blank, the payload fields when the group
 * is complete, or a message naming what is wrong.
 */
export function emergencyEvidence(
  form: EmergencyRequestForm,
): { evidence: EmergencyEvidencePayload } | { problem: string } {
  const source = (form.source ?? "").trim();
  const sourceEventId = (form.sourceEventId ?? "").trim();
  const alertLevel = (form.alertLevel ?? "").trim();
  const magText = (form.mag ?? "").trim();
  const sigText = (form.sig ?? "").trim();
  const core = [source, sourceEventId, alertLevel];
  if (core.every((value) => value === "")) {
    return magText === "" && sigText === ""
      ? { evidence: {} }
      : { problem: "Magnitude and significance need source, source event id and alert level." };
  }
  if (core.some((value) => value === "")) {
    return { problem: "Fill source, source event id and alert level together, or leave all blank." };
  }
  if (!isAlertLevel(alertLevel)) {
    return { problem: `Alert level must be one of ${CUE_ALERT_LEVELS.join(", ")}.` };
  }
  const mag = magText === "" ? undefined : numberField(magText);
  const sig = sigText === "" ? undefined : numberField(sigText);
  if (mag === null || sig === null) {
    return { problem: "Magnitude and significance must be finite numbers when given." };
  }
  return {
    evidence: {
      source,
      source_event_id: sourceEventId,
      alert_level: alertLevel,
      ...(mag === undefined ? {} : { mag }),
      ...(sig === undefined ? {} : { sig }),
    },
  };
}

function toInputTime(epochMs: number): string {
  return new Date(epochMs).toISOString().slice(0, 16);
}

function fromInputTime(value: string): string | null {
  const iso = `${value}:00Z`;
  return Number.isNaN(Date.parse(iso)) ? null : new Date(iso).toISOString().replace(".000Z", "Z");
}

const MINUTE_MS = 60_000;

/**
 * Starting values for the form: a request id no request uses yet, and one
 * window opening ten minutes after the mission clock. Every field stays
 * editable; the target is left blank because there is no real one to suggest.
 */
export function emergencyRequestDefaults(
  simulatedTime: string,
  knownRequestIds: readonly string[],
): EmergencyRequestForm {
  const taken = new Set(knownRequestIds);
  let number = 1;
  while (taken.has(`OBS-EMERGENCY-${number}`)) {
    number += 1;
  }
  const now = Date.parse(simulatedTime);
  const windowEnd = toInputTime(now + 25 * MINUTE_MS);
  return {
    requestId: `OBS-EMERGENCY-${number}`,
    targetLat: "",
    targetLon: "",
    priority: "5",
    durationS: "600",
    deadline: windowEnd,
    energyCostWh: "40",
    storageCostMb: "100",
    windowStart: toInputTime(now + 10 * MINUTE_MS),
    windowEnd,
  };
}

function numberField(value: string): number | null {
  if (value.trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * The EMERGENCY_TASK body the event route accepts: the request plus its one
 * explicit window on the mission satellite. Returns null while a field cannot
 * be read; range and ownership checks stay with the backend.
 */
export function buildEmergencyRequestEvent(
  form: EmergencyRequestForm,
  satelliteId: string,
  orbital = false,
): MissionEventRequest | null {
  const requestId = form.requestId.trim();
  const targetLat = numberField(form.targetLat);
  const targetLon = numberField(form.targetLon);
  const priority = numberField(form.priority);
  const durationS = numberField(form.durationS);
  const energyCostWh = numberField(form.energyCostWh);
  const storageCostMb = numberField(form.storageCostMb);
  const deadline = fromInputTime(form.deadline);
  const windowStart = fromInputTime(form.windowStart);
  const windowEnd = fromInputTime(form.windowEnd);
  const evidence = emergencyEvidence(form);
  if (
    "problem" in evidence ||
    requestId === "" ||
    targetLat === null ||
    targetLon === null ||
    priority === null ||
    durationS === null ||
    energyCostWh === null ||
    storageCostMb === null ||
    deadline === null ||
    (!orbital && windowStart === null) ||
    (!orbital && windowEnd === null)
  ) {
    return null;
  }
  return {
    event_type: "EMERGENCY_TASK",
    payload: {
      request: {
        id: requestId,
        target_lat: targetLat,
        target_lon: targetLon,
        priority,
        duration_s: durationS,
        deadline,
        energy_cost_wh: energyCostWh,
        storage_cost_mb: storageCostMb,
        status: "pending",
      },
      windows: orbital ? undefined : [
        {
          id: emergencyWindowId(requestId),
          request_id: requestId,
          satellite_id: satelliteId,
          start: windowStart!,
          end: windowEnd!,
          valid: true,
          invalid_reason: null,
        },
      ],
      ...evidence.evidence,
    },
  };
}
