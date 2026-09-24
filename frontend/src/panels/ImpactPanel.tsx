import type { ImpactSchema, MissionPlanSchema } from "../api/client";
import { shortPlanId } from "./format";
import { PanelFrame } from "./PanelFrame";

function actionSummary(
  plan: MissionPlanSchema | null,
  actionId: string,
): { requestId: string; start: string; end: string } | null {
  const action = plan?.actions.find((candidate) => candidate.id === actionId);
  if (action === undefined) {
    return null;
  }
  return { requestId: action.request_id, start: action.start, end: action.end };
}

/** The persisted impact of the last injected event on the plan it evaluated. */
export function ImpactPanel({
  impact,
  plan,
}: {
  impact: ImpactSchema | null;
  plan: MissionPlanSchema | null;
}) {
  return (
    <PanelFrame
      title="Impact"
      meta={impact === null ? undefined : `${impact.event_id} on ${shortPlanId(impact.evaluated_plan_id)}`}
    >
      {impact === null ? (
        <p className="text-xs text-neutral-500">Inject an event to see its impact.</p>
      ) : (
        <div className="flex flex-col gap-1.5 text-xs">
          {impact.invalid_unfrozen_action_ids.length === 0 ? (
            <p className="text-emerald-400">No scheduled actions became invalid.</p>
          ) : (
            <ul className="space-y-0.5">
              {impact.invalid_unfrozen_action_ids.map((actionId) => {
                const summary = actionSummary(plan, actionId);
                const reasons = impact.reason_codes[actionId] ?? [];
                return (
                  <li key={actionId} className="text-red-300">
                    {summary?.requestId ?? actionId}: {reasons.join(", ") || "invalidated"}
                  </li>
                );
              })}
            </ul>
          )}
          <p className="text-neutral-500">
            {impact.frozen_action_ids.length} frozen,{" "}
            {impact.valid_unfrozen_action_ids.length} still valid.
          </p>
        </div>
      )}
    </PanelFrame>
  );
}
