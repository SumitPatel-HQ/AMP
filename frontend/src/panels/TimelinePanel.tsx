import type { CSSProperties } from "react";
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
import { CHANGED_MARKER, FROZEN_STROKE, STATUS_COLORS } from "./timelinePalette";

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

function Swatch({ style }: { style: CSSProperties }) {
  return <span aria-hidden="true" className="inline-block h-2 w-3 rounded-[1px]" style={style} />;
}

/** What the bars on the timeline mean, in the colours the timeline draws. */
function TimelineLegend() {
  const items: { label: string; style: CSSProperties }[] = [
    { label: "Planned", style: { backgroundColor: STATUS_COLORS.planned } },
    { label: "Started", style: { backgroundColor: STATUS_COLORS.started } },
    { label: "Completed", style: { backgroundColor: STATUS_COLORS.completed } },
    { label: "Frozen", style: { border: `1px dashed ${FROZEN_STROKE}` } },
    { label: "Changed by replan", style: { backgroundColor: CHANGED_MARKER, width: 8, borderRadius: 9999 } },
  ];
  return (
    <ul aria-label="Timeline legend" className="flex items-center gap-3 text-[10px] text-neutral-400">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1">
          <Swatch style={item.style} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function TimelinePanel({
  scenario,
  plan,
  replanResult,
  missionState,
  selectedRequestId,
  onSelectRequest,
  className,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  replanResult: ReplanResult | null;
  missionState: MissionStateSchema | null;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
  className?: string;
}) {
  const views = scenario === null ? [] : timelineViews(plan, replanResult);
  // Both stacked timelines are read at the clock the replan ran at, so what
  // they mark as frozen stays what that replan was not allowed to touch.
  const frozenAt = replanResult?.frozenAt ?? missionState?.simulated_time ?? null;

  return (
    <PanelFrame
      title="Mission timeline"
      meta={views.map((view) => `V${view.plan.version}`).join(" → ") || undefined}
      actions={views.length === 0 ? undefined : <TimelineLegend />}
      className={className}
    >
      {scenario === null || views.length === 0 ? (
        <p className="text-xs text-neutral-500">
          {scenario === null
            ? "Load a scenario and generate a plan to see scheduled actions."
            : "Generate plan to lay the mission's scheduled actions on the timeline."}
        </p>
      ) : (
        // After a replan the two versions sit side by side, before on the left,
        // so both fit the region instead of stacking past its bottom edge.
        <div
          className={
            views.length > 1 ? "grid grid-cols-2 gap-4" : "flex max-w-[1100px] flex-col gap-4"
          }
        >
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
