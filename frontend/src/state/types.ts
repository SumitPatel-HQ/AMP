import type {
  ApiErrorCode,
  DecisionTraceSchema,
  MissionPlanSchema,
  PlanDiffSchema,
} from "../api/client";

export interface MissionSessionError {
  code: ApiErrorCode | "CLIENT_ERROR";
  message: string;
}

/** One replan: the plan it started from, the plan it produced, and their diff. */
export interface ReplanResult {
  initialPlan: MissionPlanSchema;
  revisedPlan: MissionPlanSchema;
  diff: PlanDiffSchema;
  /** Every changed request's trace, in the chronological order it was decided. */
  traces: DecisionTraceSchema[];
  /**
   * The simulated time the replan ran at. Frozen actions are the ones this
   * clock had already started, so pinning it keeps the two timelines showing
   * what that replan could not touch rather than what the live clock has since
   * overtaken.
   */
  frozenAt: string;
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
