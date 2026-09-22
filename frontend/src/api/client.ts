import createClient from "openapi-fetch";
import type { paths, components } from "./schema";

const API_BASE_URL = import.meta.env.VITE_AMIS_API_URL ?? "http://127.0.0.1:8000";

export const client = createClient<paths>({ baseUrl: API_BASE_URL });

export type ScenarioSchema = components["schemas"]["ScenarioSchema"];
export type ObservationRequestSchema = components["schemas"]["ObservationRequestSchema"];
export type ObservationWindowSchema = components["schemas"]["ObservationWindowSchema"];
export type MissionPlanSchema = components["schemas"]["MissionPlanSchema"];
export type ScheduledActionSchema = components["schemas"]["ScheduledActionSchema"];
export type MissionStateSchema = components["schemas"]["MissionStateSchema"];
export type MissionEventSchema = components["schemas"]["MissionEventSchema"];
export type ImpactSchema = components["schemas"]["ImpactSchema"];
export type PlanDiffSchema = components["schemas"]["PlanDiffSchema"];
export type PlanDiffEntrySchema = components["schemas"]["PlanDiffEntrySchema"];
export type UnscheduledEntrySchema = components["schemas"]["UnscheduledEntrySchema"];
export type PlanChangeType = components["schemas"]["PlanChangeType"];
export type MetricsSchema = components["schemas"]["MetricsSchema"];
export type DecisionTraceSchema = components["schemas"]["DecisionTraceSchema"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];
export type ApiErrorCode = ErrorEnvelope["error"]["code"];

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly details: Record<string, unknown>;

  constructor(envelope: ErrorEnvelope) {
    super(envelope.error.message);
    this.code = envelope.error.code;
    this.details = envelope.error.details;
  }
}

export function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error?: unknown }).error === "object"
  );
}
