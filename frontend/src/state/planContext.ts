import type { MissionPlanSchema } from "../api/client";
import { shortPlanId } from "../panels/format";
import type { ReplanResult } from "./types";

/** The plan versions this session holds: the current one, and after a replan its parent. */
export function knownPlans(
  plan: MissionPlanSchema | null,
  replanResult: ReplanResult | null,
): MissionPlanSchema[] {
  if (replanResult !== null) {
    return [replanResult.initialPlan, replanResult.revisedPlan];
  }
  return plan === null ? [] : [plan];
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
