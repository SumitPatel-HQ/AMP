import type {
  ApiErrorCode,
  DecisionTraceSchema,
  MissionPlanSchema,
  PlanDiffSchema,
} from "../api/client";

export interface MissionSessionError {
  code: ApiErrorCode | "CLIENT_ERROR";
  message: string;
  /** The backend's error details, kept verbatim so no context is lost. */
  details: Record<string, unknown>;
}

/** The mutation a mission request is running, while one is in flight. */
export type MissionOperation = "inject" | "replan";

/**
 * A replan the backend refused because the plan it named was no longer
 * current. The session refreshes to the backend's current plan instead of
 * retrying, so the reviewer decides again against a known version.
 */
export interface PlanConflict {
  /** The backend's PLAN_VERSION_CONFLICT message, shown verbatim. */
  message: string;
  expectedPlanId: string;
  currentPlanId: string | null;
}

/** One replan: the plan it started from, the plan it produced, and their diff. */
export interface ReplanResult {
  initialPlan: MissionPlanSchema;
  revisedPlan: MissionPlanSchema;
  diff: PlanDiffSchema;
  /** Every changed request's trace, in the chronological order it was decided. */
  traces: DecisionTraceSchema[];
}

/**
 * The mission objects the reviewer is following across panels. Each field is
 * independent: a panel reads the one it can show and ignores the rest.
 */
export interface MissionSelection {
  requestId: string | null;
  windowId: string | null;
  eventId: string | null;
  planId: string | null;
}

export const EMPTY_SELECTION: MissionSelection = {
  requestId: null,
  windowId: null,
  eventId: null,
  planId: null,
};
