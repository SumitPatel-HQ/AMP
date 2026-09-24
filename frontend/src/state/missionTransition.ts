import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  ScenarioSchema,
} from "../api/client";
import { eventSummary } from "./missionEvent";
import type { MissionOperation, ReplanResult } from "./types";

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

/** The event whose impact the transition shows. Type and summary are null if unlisted. */
export interface EventStage {
  kind: "event";
  eventId: string;
  eventType: MissionEventSchema["event_type"] | null;
  /** What the payload carries, e.g. the blocked request/window or the new battery value. */
  summary: string | null;
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
  | { kind: "no-event" }
  /** A request to the backend is running; the phase still reads only what it returned. */
  | { kind: "injecting" }
  | { kind: "replanning" };

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
    summary: event === undefined ? null : eventSummary(event),
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
 * The loop as the backend last reported it, read only from what it returned.
 * An impact belongs to the plan it evaluated, so it joins the transition only
 * while that plan is either the current one (awaiting a replan) or the one the
 * last replan started from.
 */
function settledTransition({
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

/**
 * Where the mission stands in its plan -> event -> impact -> replan loop.
 * While an inject or replan request is in flight the strip says so, but the
 * phase only moves once the backend has answered and the session refetched.
 */
export function missionTransition(input: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  impact: ImpactSchema | null;
  events: MissionEventSchema[];
  replanResult: ReplanResult | null;
  operation?: MissionOperation | null;
}): MissionTransition {
  const settled = settledTransition(input);
  const operation = input.operation ?? null;
  if (settled.phase === "no-plan" || operation === null) {
    return settled;
  }
  if (operation === "inject") {
    return { ...settled, stages: [...settled.stages, { kind: "injecting" }] };
  }
  const waiting = settled.stages.filter((stage) => stage.kind !== "awaiting-replan");
  return { ...settled, stages: [...waiting, { kind: "replanning" }] };
}
