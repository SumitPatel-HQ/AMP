import type { TargetPlanStatus } from "./missionMapModel";

export type Rgb = readonly [number, number, number];

/** One colour per target status; the legend and the layers read the same map. */
export const STATUS_COLORS: Record<TargetPlanStatus, Rgb> = {
  scheduled: [56, 189, 248],
  completed: [52, 211, 153],
  unscheduled: [251, 191, 36],
  unplanned: [148, 163, 184],
};

export const STATUS_LABELS: Record<TargetPlanStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  unscheduled: "Unscheduled",
  unplanned: "Not planned",
};

export const EVENT_COLOR: Rgb = [248, 113, 113];
export const SELECTED_COLOR: Rgb = [232, 121, 249];
export const SATELLITE_COLOR: Rgb = [249, 115, 22];
export const SEQUENCE_COLOR: Rgb = [125, 211, 252];

export function cssColor([red, green, blue]: Rgb): string {
  return `rgb(${red} ${green} ${blue})`;
}

/** The overlays a reviewer can switch off; targets themselves always draw. */
export interface LayerVisibility {
  labels: boolean;
  sequence: boolean;
  satellite: boolean;
  events: boolean;
}

export const DEFAULT_VISIBILITY: LayerVisibility = {
  labels: true,
  sequence: true,
  satellite: true,
  events: true,
};
