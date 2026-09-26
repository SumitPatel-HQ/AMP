import type { MissionPlanSchema, ScenarioSchema } from "../api/client";

/** One step of onboard storage: the level right after a change at ``time``. */
export interface StoragePoint {
  time: string;
  usedMb: number;
  kind: "start" | "imaging" | "downlink";
}

/**
 * Storage across the whole mission under the ADR-0011 timeline walk:
 * imaging charges at its start, downlink frees at its end, and the level
 * floors at zero. At equal instants a downlink release lands first.
 */
export function storageProfile(scenario: ScenarioSchema, plan: MissionPlanSchema): StoragePoint[] {
  const deltas = plan.actions.map((action) => {
    const downlink = action.kind === "downlink";
    return {
      time: downlink ? action.end : action.start,
      order: downlink ? 0 : 1,
      delta: action.storage_cost_mb,
      kind: downlink ? ("downlink" as const) : ("imaging" as const),
    };
  });
  deltas.sort((a, b) => Date.parse(a.time) - Date.parse(b.time) || a.order - b.order);
  let used = scenario.satellite.storage_usage_mb;
  const points: StoragePoint[] = [{ time: scenario.start_time, usedMb: used, kind: "start" }];
  for (const step of deltas) {
    used = Math.max(0, used + step.delta);
    points.push({ time: step.time, usedMb: used, kind: step.kind });
  }
  return points;
}
