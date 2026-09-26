import type { MissionPlanSchema, MissionStateSchema, ScenarioSchema } from "../api/client";

/** One step of onboard storage: the level right after a change at ``time``. */
export interface StoragePoint {
  time: string;
  usedMb: number;
  kind: "start" | "now" | "imaging" | "downlink";
}

type Action = MissionPlanSchema["actions"][number];

interface Delta {
  time: string;
  order: number;
  delta: number;
  kind: "imaging" | "downlink";
}

function delta(action: Action): Delta {
  const downlink = action.kind === "downlink";
  return {
    time: downlink ? action.end : action.start,
    order: downlink ? 0 : 1,
    delta: action.storage_cost_mb,
    kind: downlink ? "downlink" : "imaging",
  };
}

/** Whether the backend has already charged this action to mission state. */
function applied(action: Action): boolean {
  // Imaging charges when it starts, downlink releases when it completes.
  return action.kind === "downlink" ? action.status === "completed" : action.status !== "planned";
}

function walk(seed: number, deltas: Delta[], points: StoragePoint[]): void {
  deltas.sort((a, b) => Date.parse(a.time) - Date.parse(b.time) || a.order - b.order);
  let used = seed;
  for (const step of deltas) {
    used = Math.max(0, used + step.delta);
    points.push({ time: step.time, usedMb: used, kind: step.kind });
  }
}

/**
 * Storage across the whole mission under the ADR-0011 timeline walk:
 * imaging charges at its start, downlink frees at its end, and the level
 * floors at zero. At equal instants a downlink release lands first.
 *
 * With a mission state, the future walks from the backend's live
 * ``storage_usage_mb`` (the same seed `MissionSession.step` uses), and the
 * past replays only the deltas the backend has already applied.
 */
export function storageProfile(
  scenario: ScenarioSchema,
  plan: MissionPlanSchema,
  missionState: MissionStateSchema | null = null,
): StoragePoint[] {
  const points: StoragePoint[] = [
    { time: scenario.start_time, usedMb: scenario.satellite.storage_usage_mb, kind: "start" },
  ];
  if (missionState === null) {
    walk(scenario.satellite.storage_usage_mb, plan.actions.map(delta), points);
    return points;
  }
  walk(scenario.satellite.storage_usage_mb, plan.actions.filter(applied).map(delta), points);
  points.push({ time: missionState.simulated_time, usedMb: missionState.storage_usage_mb, kind: "now" });
  walk(missionState.storage_usage_mb, plan.actions.filter((action) => !applied(action)).map(delta), points);
  return points;
}
