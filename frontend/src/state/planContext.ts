import type { MissionPlanSchema } from "../api/client";
import { shortPlanId } from "../panels/format";

/**
 * The name every panel gives a plan: its version where the session knows it,
 * so the bar, summary, timeline, impact, trace and metrics all say "V2" for
 * the same plan. An id the session never loaded keeps its backend suffix.
 */
export function planLabel(planId: string, plans: readonly MissionPlanSchema[]): string {
  const known = plans.find((candidate) => candidate.id === planId);
  return known === undefined ? shortPlanId(planId) : `V${known.version}`;
}
