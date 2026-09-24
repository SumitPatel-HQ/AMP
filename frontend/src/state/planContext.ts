import type { MissionPlanSchema } from "../api/client";
import { shortPlanId } from "../panels/format";
import type { ReplanResult } from "./types";

/** The plan versions this session holds: the current one, and after a replan its parent. */
export function knownPlans(
  plan: MissionPlanSchema | null,
  replanResult: ReplanResult | null,
): MissionPlanSchema[] {
  const plans = replanResult === null ? [] : [replanResult.initialPlan, replanResult.revisedPlan];
  // After a version conflict the session holds the backend's current plan,
  // which may belong to neither side of the last replan it saw.
  if (plan !== null && !plans.some((candidate) => candidate.id === plan.id)) {
    plans.push(plan);
  }
  return plans;
}

/**
 * The name every panel gives a plan: its version where the session knows it,
 * so the bar, summary, timeline, impact, trace and metrics all say "V2" for
 * the same plan. An id the session never loaded keeps its backend suffix.
 */
export function planLabel(planId: string, plans: readonly MissionPlanSchema[]): string {
  const known = plans.find((candidate) => candidate.id === planId);
  return known === undefined ? shortPlanId(planId) : `V${known.version}`;
}
