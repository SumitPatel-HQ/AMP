import type {
  DecisionTraceSchema,
  PlanChangeType,
  ReasonCode,
} from "../api/client";
import type { ReplanResult } from "./types";

/**
 * The concise human label for a backend reason code. The code itself stays
 * authoritative and is always shown beside the label; these phrases paraphrase
 * the cause clauses in `amis/trace.py` without adding new causality.
 */
export const REASON_LABELS: Record<ReasonCode, string> = {
  WINDOW_INVALIDATED: "Observation window invalidated",
  INSUFFICIENT_BATTERY: "Projected battery insufficient",
  INSUFFICIENT_STORAGE: "Projected storage insufficient",
  DEADLINE_VIOLATION: "No window before deadline",
  TIME_OVERLAP: "Overlapped a scheduled action",
  SATELLITE_UNAVAILABLE: "Satellite unavailable",
  DISPLACED_BY_COMPETING_REQUEST: "Displaced by competing request",
  ALTERNATIVE_WINDOW_AVAILABLE: "Alternative window available",
  NO_ALTERNATIVE_WINDOW: "No alternative window",
  REQUEST_UNCHANGED: "Unaffected by the event",
  HIGHER_PRIORITY_TASK_INSERTED: "Entered the pool and was scheduled",
};

/** Changed decisions first, clock outcomes and non-changes last and quiet. */
const CHANGE_ORDER: Record<PlanChangeType, number> = {
  MOVED: 0,
  INSERTED: 1,
  DROPPED: 2,
  COMPLETED: 3,
  UNCHANGED: 4,
};

/** The diff statuses that are replan decisions and carry decision traces. */
export function isChangedDecision(changeType: PlanChangeType): boolean {
  return (
    changeType === "MOVED" || changeType === "INSERTED" || changeType === "DROPPED"
  );
}

export interface PlanComparisonRow {
  requestId: string;
  changeType: PlanChangeType;
  reasonCode: ReasonCode;
  reasonLabel: string;
  oldStart: string | null;
  newStart: string | null;
  oldWindowId: string | null;
  oldActionId: string | null;
  newWindowId: string | null;
  newActionId: string | null;
  /** The backend trace for this request, or null when it recorded none. */
  trace: DecisionTraceSchema | null;
  /**
   * The event that drove the trace, or null for a planning decision the
   * backend recorded without a triggering event (e.g. replan without event).
   */
  traceEventId: string | null;
  /**
   * The request entered the pool after the parent plan (an emergency request)
   * and the revised plan still leaves it unscheduled. The backend diff reports
   * such a request as UNCHANGED, so the flag keeps it from reading as a
   * request the replan simply ignored.
   */
  newlyArrivedUnscheduled: boolean;
}

/**
 * One row per backend diff entry, pairing the entry with the old/new
 * placements read from the two plans and the backend trace for the same
 * request. Nothing is re-compared here: change types, reason codes, times and
 * traces all come from the backend-supplied replan result.
 */
export function comparisonRows(replanResult: ReplanResult): PlanComparisonRow[] {
  const { initialPlan, revisedPlan, diff, traces } = replanResult;
  const oldActions = new Map(
    initialPlan.actions.map((action) => [action.request_id, action]),
  );
  const newActions = new Map(
    revisedPlan.actions.map((action) => [action.request_id, action]),
  );
  const traceByRequest = new Map<string, DecisionTraceSchema>();
  for (const trace of traces) {
    if (trace.request_id !== null && !traceByRequest.has(trace.request_id)) {
      traceByRequest.set(trace.request_id, trace);
    }
  }
  const knownInParent = new Set([
    ...initialPlan.actions.map((action) => action.request_id),
    ...initialPlan.unscheduled.map((entry) => entry.request_id),
  ]);
  const unscheduledInRevised = new Set(
    revisedPlan.unscheduled.map((entry) => entry.request_id),
  );

  return [...diff.entries]
    .map((entry) => {
      const oldAction = oldActions.get(entry.request_id);
      const newAction = newActions.get(entry.request_id);
      const trace = traceByRequest.get(entry.request_id) ?? null;
      return {
        requestId: entry.request_id,
        changeType: entry.change_type,
        reasonCode: entry.reason_code,
        reasonLabel: REASON_LABELS[entry.reason_code] ?? entry.reason_code,
        oldStart: entry.old_start,
        newStart: entry.new_start,
        oldWindowId: oldAction?.window_id ?? null,
        oldActionId: oldAction?.id ?? null,
        newWindowId: newAction?.window_id ?? null,
        newActionId: newAction?.id ?? null,
        trace,
        traceEventId: trace?.event_id ?? null,
        newlyArrivedUnscheduled:
          !knownInParent.has(entry.request_id) &&
          unscheduledInRevised.has(entry.request_id),
      } satisfies PlanComparisonRow;
    })
    .sort(
      (left, right) =>
        CHANGE_ORDER[left.changeType] - CHANGE_ORDER[right.changeType] ||
        (left.requestId < right.requestId ? -1 : left.requestId > right.requestId ? 1 : 0),
    );
}

export interface PlanComparisonSummary {
  changed: number;
  completed: number;
  unchanged: number;
}

export function comparisonSummary(rows: readonly PlanComparisonRow[]): PlanComparisonSummary {
  return {
    changed: rows.filter((row) => isChangedDecision(row.changeType)).length,
    completed: rows.filter((row) => row.changeType === "COMPLETED").length,
    unchanged: rows.filter((row) => row.changeType === "UNCHANGED").length,
  };
}

/** Header counts naming each backend status exactly; absent statuses are omitted. */
export function comparisonMeta(summary: PlanComparisonSummary): string {
  const parts = [`${summary.changed} changed`];
  if (summary.completed > 0) {
    parts.push(`${summary.completed} completed`);
  }
  parts.push(`${summary.unchanged} unchanged`);
  return parts.join(" · ");
}
