import type { FeasibilityQuery } from "../api/amis";
import type { FeasibilitySchema, SatelliteFeasibilitySchema } from "../api/client";

/** What the window-only answer accounts for, as the backend computes it. */
export const FEASIBILITY_INCLUDES =
  "stored orbital geometry, daylight and pointing policy, imaging duration, deadline, and Scenario satellite availability";

/** What it deliberately leaves out, so no row reads as a schedulable action. */
export const FEASIBILITY_EXCLUDES =
  "the current plan and resources, pairwise slew, active outages, and reservations";

export const FEASIBILITY_PROMISE =
  "It is not a promise that the Planner will select the candidate or that a resource-feasible action exists. Nothing is submitted or reserved.";

export type FeasibilityRowState = "earliest" | "suitable" | "no_suitable_window" | "satellite_unavailable";

const ROW_STATE_BY_REASON: Record<NonNullable<SatelliteFeasibilitySchema["reason"]>, FeasibilityRowState> = {
  no_suitable_window: "no_suitable_window",
  satellite_unavailable: "satellite_unavailable",
};

export const FEASIBILITY_STATE_LABEL: Record<FeasibilityRowState, string> = {
  earliest: "Earliest",
  suitable: "Suitable",
  no_suitable_window: "No suitable window",
  satellite_unavailable: "Satellite unavailable",
};

export function rowStateForSatellite(
  row: SatelliteFeasibilitySchema,
  earliestSatelliteId: string | null,
): FeasibilityRowState {
  return row.reason === null
    ? row.satellite_id === earliestSatelliteId ? "earliest" : "suitable"
    : ROW_STATE_BY_REASON[row.reason];
}

/** The form exactly as typed, before the backend validates it. */
export interface FeasibilityForm {
  lat: string;
  lon: string;
  durationS: string;
  /** A `datetime-local` value, read as UTC. */
  deadlineUtc: string;
  /** Empty for every satellite. */
  satelliteId: string;
}

/** `datetime-local` text for an ISO instant, in UTC. */
export function toUtcInput(isoTime: string): string {
  return new Date(isoTime).toISOString().slice(0, 19);
}

function parseCandidateNumber(text: string): number {
  return text.trim() === "" ? Number.NaN : Number(text);
}

/**
 * The query the form describes. Numbers pass through unchecked: bounds,
 * finiteness, and the deadline's relation to the Scenario are the backend's
 * validation, shown as its own errors. Only a deadline that is not a date at
 * all is refused here, since it cannot be sent with a timezone.
 */
export function feasibilityQuery(form: FeasibilityForm): FeasibilityQuery | string {
  const deadline = new Date(`${form.deadlineUtc}Z`);
  if (form.deadlineUtc.trim() === "" || Number.isNaN(deadline.getTime())) {
    return "Enter a deadline in UTC.";
  }
  return {
    lat: parseCandidateNumber(form.lat),
    lon: parseCandidateNumber(form.lon),
    duration: parseCandidateNumber(form.durationS),
    deadline: deadline.toISOString(),
    satelliteId: form.satelliteId === "" ? null : form.satelliteId,
  };
}

/** A result belongs to the open mission only if the backend answered for it. */
export function resultForScenario(
  result: FeasibilitySchema | null,
  scenarioId: string | null,
): FeasibilitySchema | null {
  return result !== null && result.scenario_id === scenarioId ? result : null;
}
