import type {
  ImpactSchema,
  MissionPlanSchema,
  PlanChangeType,
  PlanDiffSchema,
} from "../api/client";

export type RequestState =
  | "completed"
  | "started"
  | "planned"
  | "invalid"
  | "unscheduled"
  | "not-planned";

/**
 * One status per request, so the list never repeats itself (a completed action
 * is also reported completed by the clock). The reason code and the last
 * replan's change travel alongside as secondary detail.
 */
export interface RequestStatus {
  state: RequestState;
  reasonCode: string | null;
  change: PlanChangeType | null;
}

/** Changes a replan made. COMPLETED is the clock's doing and UNCHANGED is no change. */
const REPLAN_CHANGES: ReadonlySet<PlanChangeType> = new Set(["MOVED", "INSERTED", "DROPPED"]);

export function requestStatus(
  requestId: string,
  {
    plan,
    completedRequestIds,
    impact,
    diff,
  }: {
    plan: MissionPlanSchema | null;
    /** Live from mission state, so completion shows even where the plan lags. */
    completedRequestIds: ReadonlySet<string>;
    impact: ImpactSchema | null;
    diff: PlanDiffSchema | null;
  },
): RequestStatus {
  const entry =
    plan === null || diff === null || diff.to_plan_id !== plan.id
      ? undefined
      : diff.entries.find((candidate) => candidate.request_id === requestId);
  const change =
    entry !== undefined && REPLAN_CHANGES.has(entry.change_type) ? entry.change_type : null;
  const status = (state: RequestState, reasonCode: string | null = null): RequestStatus => ({
    state,
    reasonCode,
    change,
  });

  const action = plan?.actions.find((candidate) => candidate.request_id === requestId);
  if (completedRequestIds.has(requestId) || action?.status === "completed") {
    return status("completed");
  }
  if (plan === null) {
    return status("not-planned");
  }
  if (action !== undefined) {
    // An impact speaks for the plan it evaluated, and only that plan's actions.
    if (
      impact !== null &&
      impact.evaluated_plan_id === plan.id &&
      impact.invalid_unfrozen_action_ids.includes(action.id)
    ) {
      return status("invalid", impact.reason_codes[action.id]?.[0] ?? null);
    }
    return status(action.status === "started" ? "started" : "planned");
  }
  const unscheduled = plan.unscheduled.find((candidate) => candidate.request_id === requestId);
  return unscheduled === undefined
    ? status("not-planned")
    : status("unscheduled", unscheduled.reason_code);
}
