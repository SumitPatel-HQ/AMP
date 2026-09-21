import type {
  MissionPlanSchema,
  MissionStateSchema,
  PlanChangeType,
  PlanDiffSchema,
  ScenarioSchema,
} from "../api/client";
import type { ReplanResult } from "../state/types";
import { PanelFrame } from "./PanelFrame";
import { PlanTimeline } from "./PlanTimeline";

const NO_CHANGES: Record<string, PlanChangeType> = {};

/**
 * The change types a replan caused. UNCHANGED is not a change, and COMPLETED
 * is the diff reporting that the clock finished an action, not that replanning
 * touched it, so neither is marked.
 */
function replanChanges(diff: PlanDiffSchema): Record<string, PlanChangeType> {
  const changes: Record<string, PlanChangeType> = {};
  for (const entry of diff.entries) {
    if (entry.change_type !== "UNCHANGED" && entry.change_type !== "COMPLETED") {
      changes[entry.request_id] = entry.change_type;
    }
  }
  return changes;
}

interface TimelineView {
  label: string;
  plan: MissionPlanSchema;
  changeByRequestId: Record<string, PlanChangeType>;
}

/** One timeline before a replan, two stacked for comparison after one. */
function timelineViews(
  plan: MissionPlanSchema | null,
  replanResult: ReplanResult | null,
): TimelineView[] {
  if (replanResult !== null) {
    const changes = replanChanges(replanResult.diff);
    return [
      {
        label: "Initial plan",
        plan: replanResult.initialPlan,
        changeByRequestId: NO_CHANGES,
      },
      {
        label: "Revised plan",
        plan: replanResult.revisedPlan,
        changeByRequestId: changes,
      },
    ];
  }
  return plan === null
    ? []
    : [{ label: "Mission", plan, changeByRequestId: NO_CHANGES }];
}

export function TimelinePanel({
  scenario,
  plan,
  replanResult,
  missionState,
  selectedRequestId,
  loading,
  onReplan,
  onSelectRequest,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  replanResult: ReplanResult | null;
  missionState: MissionStateSchema | null;
  selectedRequestId: string | null;
  loading: boolean;
  onReplan: () => void;
  onSelectRequest: (requestId: string | null) => void;
}) {
  const views = scenario === null ? [] : timelineViews(plan, replanResult);
  // Both stacked timelines are read at the clock the replan ran at, so what
  // they mark as frozen stays what that replan was not allowed to touch.
  const frozenAt = replanResult?.frozenAt ?? missionState?.simulated_time ?? null;

  return (
    <PanelFrame title="Timeline">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onReplan}
          disabled={loading || plan === null}
          className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
        >
          Replan
        </button>
      </div>
      {scenario === null || views.length === 0 ? (
        <p className="text-sm text-neutral-500">
          Load a scenario and generate a plan to see scheduled actions.
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          {views.map((view) => (
            <PlanTimeline
              key={view.plan.id}
              label={view.label}
              scenario={scenario}
              plan={view.plan}
              simulatedTime={frozenAt}
              changeByRequestId={view.changeByRequestId}
              selectedRequestId={selectedRequestId}
              onSelectRequest={onSelectRequest}
            />
          ))}
        </div>
      )}
    </PanelFrame>
  );
}
