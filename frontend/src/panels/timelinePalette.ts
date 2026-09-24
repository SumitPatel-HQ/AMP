import type { ScheduledActionSchema } from "../api/client";

/** Scheduled-action fills, shared by the timeline and its legend. */
export const STATUS_COLORS: Record<ScheduledActionSchema["status"], string> = {
  planned: "#3b82f6",
  started: "#f59e0b",
  completed: "#10b981",
};

export const FROZEN_STROKE = "#e5e7eb";
export const CHANGED_MARKER = "#f472b6";
