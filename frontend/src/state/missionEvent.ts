import type {
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
    case "CLOUD_BLOCK":
      return `${event.payload.request_id} / ${event.payload.window_id}`;
    case "BATTERY_DROP":
      return `${event.payload.satellite_id} battery → ${event.payload.new_battery_wh.toFixed(1)} Wh`;
    case "EMERGENCY_TASK": {
      const count = event.payload.windows.length;
      return `${event.payload.request.id} · P${event.payload.request.priority} · ${count} window${
        count === 1 ? "" : "s"
      }`;
    }
  }
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
  if (
    requestId === "" ||
    targetLat === null ||
    targetLon === null ||
    priority === null ||
    durationS === null ||
    energyCostWh === null ||
    storageCostMb === null ||
    deadline === null ||
    windowStart === null ||
    windowEnd === null
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
      windows: [
        {
          id: emergencyWindowId(requestId),
          request_id: requestId,
          satellite_id: satelliteId,
          start: windowStart,
          end: windowEnd,
          valid: true,
          invalid_reason: null,
        },
      ],
    },
  };
}
