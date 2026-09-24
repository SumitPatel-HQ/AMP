import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  ScenarioSchema,
} from "../api/client";
import type { ReplanResult } from "./types";

/**
 * One plan version in the transition. `evaluated` is the current plan an event
 * has just been assessed against; `previous` is the plan a replan replaced.
 */
export interface PlanStage {
  kind: "plan";
  role: "current" | "evaluated" | "previous";
  planId: string;
  version: number;
  scheduled: number;
  requestCount: number;
}

/** The event whose impact the transition shows. Type and payload are null if unlisted. */
export interface EventStage {
  kind: "event";
  eventId: string;
  eventType: MissionEventSchema["event_type"] | null;
  requestId: string | null;
  windowId: string | null;
  time: string | null;
}

/** The persisted impact, with its invalid actions read back to their requests. */
export interface ImpactStage {
  kind: "impact";
  invalidCount: number;
  affectedRequestIds: string[];
  reasonCodes: string[];
}

export type TransitionStage =
  | PlanStage
  | EventStage
  | ImpactStage
  | { kind: "awaiting-replan" }
  | { kind: "no-event" };

export type MissionPhase = "no-plan" | "planned" | "awaiting-replan" | "replanned";

export interface MissionTransition {
  phase: MissionPhase;
  stages: TransitionStage[];
}

function planStage(
  plan: MissionPlanSchema,
  role: PlanStage["role"],
  requestCount: number,
): PlanStage {
  return {
    kind: "plan",
    role,
    planId: plan.id,
    version: plan.version,
    scheduled: plan.actions.length,
    requestCount,
  };
}

function eventStage(eventId: string, events: MissionEventSchema[]): EventStage {
  const event = events.find((candidate) => candidate.id === eventId);
  return {
    kind: "event",
    eventId,
    eventType: event?.event_type ?? null,
    requestId: event?.payload.request_id ?? null,
    windowId: event?.payload.window_id ?? null,
    time: event?.event_time ?? null,
  };
}

function impactStage(impact: ImpactSchema, evaluatedPlan: MissionPlanSchema): ImpactStage {
  const invalid = impact.invalid_unfrozen_action_ids;
  const requestIds = invalid.map(
    (actionId) =>
      evaluatedPlan.actions.find((action) => action.id === actionId)?.request_id ?? actionId,
  );
  const reasonCodes = invalid.flatMap((actionId) => impact.reason_codes[actionId] ?? []);
  return {
    kind: "impact",
    invalidCount: invalid.length,
    affectedRequestIds: [...new Set(requestIds)],
    reasonCodes: [...new Set(reasonCodes)],
  };
}

/**
 * Where the mission stands in its plan -> event -> impact -> replan loop, read
 * only from what the backend returned. An impact belongs to the plan it
 * evaluated, so it joins the transition only while that plan is either the
 * current one (awaiting a replan) or the one the last replan started from.
 */
export function missionTransition({
  scenario,
  plan,
  impact,
  events,
  replanResult,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  impact: ImpactSchema | null;
  events: MissionEventSchema[];
  replanResult: ReplanResult | null;
}): MissionTransition {
  if (plan === null) {
    return { phase: "no-plan", stages: [] };
  }
  const requestCount = scenario?.requests.length ?? 0;

  if (impact !== null && impact.evaluated_plan_id === plan.id) {
    return {
      phase: "awaiting-replan",
      stages: [
        planStage(plan, "evaluated", requestCount),
        eventStage(impact.event_id, events),
        impactStage(impact, plan),
        { kind: "awaiting-replan" },
      ],
    };
  }

  if (replanResult !== null && replanResult.revisedPlan.id === plan.id) {
    const previous = replanResult.initialPlan;
    const current = planStage(plan, "current", requestCount);
    if (impact !== null && impact.evaluated_plan_id === previous.id) {
      return {
        phase: "replanned",
        stages: [
          planStage(previous, "previous", requestCount),
          eventStage(impact.event_id, events),
          impactStage(impact, previous),
          current,
        ],
      };
    }
    return {
      phase: "replanned",
      stages: [planStage(previous, "previous", requestCount), { kind: "no-event" }, current],
    };
  }

  return { phase: "planned", stages: [planStage(plan, "current", requestCount)] };
}
