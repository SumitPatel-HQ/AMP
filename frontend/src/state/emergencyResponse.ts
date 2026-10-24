import type { EmergencyResponseSchema, MetricsSchema } from "../api/client";

/**
 * How one emergency arrival stands, read only from the backend's response
 * row. Achieved means the backend reports that imaging actually started;
 * the browser never infers it from the clock or a proposed action time.
 */
export type EmergencyResponseState = "achieved" | "planned" | "expired" | "unserved";

export function emergencyResponseState(row: EmergencyResponseSchema): EmergencyResponseState {
  if (row.achieved_start_time !== null) {
    return "achieved";
  }
  if (row.request_status === "expired") {
    return "expired";
  }
  return row.planned_start_time === null ? "unserved" : "planned";
}

/** The one label each state carries in every view. */
export const RESPONSE_STATE_LABEL: Record<EmergencyResponseState, string> = {
  achieved: "achieved",
  planned: "planned",
  expired: "expired · no acquisition",
  unserved: "unserved · no acquisition",
};

/** The backend's rows; metrics recorded before emergency response carry none. */
export function emergencyResponseRows(metrics: MetricsSchema): EmergencyResponseSchema[] {
  return metrics.emergency_response ?? [];
}

/** Seconds from arrival to imaging start; null is no acquisition, never zero. */
export function formatLatency(seconds: number | null): string {
  if (seconds === null) {
    return "no acquisition";
  }
  const total = Math.round(seconds);
  if (total < 60) {
    return `${total} s`;
  }
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  const parts = [
    hours > 0 ? `${hours} h` : null,
    minutes > 0 ? `${minutes} min` : null,
    rest > 0 ? `${rest} s` : null,
  ];
  return parts.filter((part) => part !== null).join(" ");
}

export type ResponseSide = "planned" | "achieved";

/**
 * One side's mean latency with the denominator it was taken over and the
 * total it leaves out. The backend's `time_to_first_acquisition_s` fields
 * hold these means, not the earliest acquisition.
 */
export function responseSummary(metrics: MetricsSchema, side: ResponseSide): string {
  const [mean, count, verb] =
    side === "planned"
      ? [metrics.time_to_first_acquisition_s ?? null, metrics.planned_emergency_request_count, "planned"]
      : [metrics.achieved_time_to_first_acquisition_s ?? null, metrics.achieved_emergency_request_count, "started"];
  const total = metrics.emergency_request_count;
  return mean === null
    ? `N/A · 0 of ${total} ${verb}`
    : `${formatLatency(mean)} · ${count} of ${total} ${verb}`;
}

/** Planned and achieved differ when both exist and name another start or satellite. */
export function plannedDiffersFromAchieved(row: EmergencyResponseSchema): boolean {
  if (row.planned_start_time === null || row.achieved_start_time === null) {
    return false;
  }
  return (
    new Date(row.planned_start_time).getTime() !== new Date(row.achieved_start_time).getTime() ||
    row.planned_satellite_id !== row.achieved_satellite_id
  );
}

export const ACQUISITION_MEANING =
  "Acquisition means imaging has started, not finished or downlinked.";
