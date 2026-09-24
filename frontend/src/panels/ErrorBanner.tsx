import type { MissionPlanSchema } from "../api/client";
import type { MissionSessionError, PlanConflict } from "../state/types";
import { shortPlanId } from "./format";

/** One validation failure as the API reports it: where, and what it says. */
function validationLine(entry: unknown): string | null {
  if (typeof entry !== "object" || entry === null) {
    return null;
  }
  const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
  const where = Array.isArray(loc) ? loc.filter((part) => part !== "body").join(".") : "";
  return typeof msg === "string" ? `${where === "" ? "" : `${where}: `}${msg}` : null;
}

/**
 * The backend's error details, verbatim but compact: request-validation
 * failures by field, anything else as key=value pairs.
 */
function detailLines(details: Record<string, unknown>): string[] {
  const errors = details["errors"];
  if (Array.isArray(errors)) {
    return errors
      .map(validationLine)
      .filter((line): line is string => line !== null)
      .slice(0, 3);
  }
  return Object.entries(details).map(
    ([key, value]) => `${key}=${typeof value === "string" ? value : JSON.stringify(value)}`,
  );
}

export function ErrorBanner({
  error,
  onDismiss,
}: {
  error: MissionSessionError | null;
  onDismiss: () => void;
}) {
  if (error === null) {
    return null;
  }
  const lines = detailLines(error.details);

  return (
    <div
      role="alert"
      className="flex shrink-0 items-start justify-between gap-4 border-b border-red-900 bg-red-950/60 px-3 py-1 text-xs text-red-200"
    >
      <span>
        <span className="font-mono text-red-400">{error.code}</span>: {error.message}
        {lines.length === 0 ? null : (
          <span className="ml-2 font-mono text-[10px] text-red-300/70">{lines.join(" · ")}</span>
        )}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="text-red-400 hover:text-red-200"
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
  );
}

/**
 * A replan the backend refused as stale. The session has already loaded the
 * plan the backend holds, so the reviewer sees which version is current now
 * and replans again only after looking at it.
 */
export function PlanConflictBanner({
  conflict,
  plan,
  onDismiss,
}: {
  conflict: PlanConflict | null;
  plan: MissionPlanSchema | null;
  onDismiss: () => void;
}) {
  if (conflict === null) {
    return null;
  }
  const refreshed = plan !== null && plan.id === conflict.currentPlanId;
  return (
    <div
      role="status"
      aria-label="Stale plan"
      className="flex shrink-0 items-start justify-between gap-4 border-b border-amber-800 bg-amber-950/50 px-3 py-1 text-xs text-amber-100"
    >
      <span>
        <span className="font-semibold uppercase tracking-wide text-amber-300">Stale plan</span>
        <span className="ml-2 font-mono text-amber-400">PLAN_VERSION_CONFLICT</span>
        {`: ${conflict.message} · replan named ${shortPlanId(conflict.expectedPlanId)}, but the backend's current plan is ${
          conflict.currentPlanId === null ? "unknown" : shortPlanId(conflict.currentPlanId)
        }. `}
        {refreshed
          ? `Plan context refreshed to V${plan.version}; review it, then Replan again.`
          : "The current plan could not be loaded; reload the mission before replanning."}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="text-amber-300 hover:text-amber-100"
        aria-label="Dismiss stale plan notice"
      >
        ×
      </button>
    </div>
  );
}
