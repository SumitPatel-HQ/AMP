import type { MissionPlanSchema } from "../api/client";
import { newlyUnscheduled } from "../state/missionEvent";
import { planLabel } from "../state/planContext";
import type { ReplanResult } from "../state/types";
import { shortPlanId } from "./format";
import { PanelFrame } from "./PanelFrame";

/**
 * What the last replan produced: the new immutable version, the parent it
 * kept unchanged, and the requests it newly left unscheduled with the
 * backend's reason codes. Kept apart from Impact, which says what an event
 * invalidated; the full version comparison is a later analysis.
 */
export function ReplanOutcomePanel({
  replanResult,
  plans,
  selectedRequestId,
  onSelectRequest,
}: {
  replanResult: ReplanResult | null;
  plans: readonly MissionPlanSchema[];
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  if (replanResult === null) {
    return null;
  }
  const { initialPlan, revisedPlan } = replanResult;
  const unscheduled = newlyUnscheduled(replanResult);
  return (
    <PanelFrame
      title="Replan outcome"
      meta={`${planLabel(initialPlan.id, plans)} → ${planLabel(revisedPlan.id, plans)}`}
      className="shrink-0"
      bodyClassName="px-2 py-1 text-[11px]"
    >
      <p className="text-neutral-400">
        <span className="font-semibold text-emerald-300">{`Replanned → ${planLabel(revisedPlan.id, plans)}`}</span>
        {` from ${planLabel(initialPlan.id, plans)} · ${revisedPlan.actions.length} actions · `}
        <span className="text-neutral-600" title={revisedPlan.id}>
          {shortPlanId(revisedPlan.id)}
        </span>
        <span className="text-neutral-600">{` · ${planLabel(initialPlan.id, plans)} kept unchanged`}</span>
      </p>
      {unscheduled.length === 0 ? (
        <p className="text-neutral-500">No request newly unscheduled.</p>
      ) : (
        <ul aria-label="Newly unscheduled requests" className="flex flex-wrap gap-x-3">
          {unscheduled.map((entry) => (
            <li key={entry.requestId} data-kind={entry.kind}>
              <button
                type="button"
                aria-pressed={entry.requestId === selectedRequestId}
                onClick={() =>
                  onSelectRequest(entry.requestId === selectedRequestId ? null : entry.requestId)
                }
                className="text-left hover:text-neutral-100"
              >
                <span className="font-semibold text-neutral-200">{entry.requestId}</span>
                <span className="text-amber-300">{` unscheduled · ${entry.reasonCode}`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </PanelFrame>
  );
}
