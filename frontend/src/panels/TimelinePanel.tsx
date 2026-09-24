import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
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

/** Changes that belong to the plan currently displayed on the mission clock. */
function currentPlanChanges(
  plan: MissionPlanSchema | null,
  replanResult: ReplanResult | null,
): Record<string, PlanChangeType> {
  return plan !== null && replanResult?.revisedPlan.id === plan.id
    ? replanChanges(replanResult.diff)
    : NO_CHANGES;
}

function Swatch({ className }: { className: string }) {
  return <span aria-hidden="true" className={`amis-timeline-legend-swatch ${className}`} />;
}

/** What the bars on the timeline mean, in the colours the timeline draws. */
function TimelineLegend() {
  const items = [
    { label: "Window", className: "amis-legend-window" },
    { label: "Planned", className: "amis-legend-planned" },
    { label: "Started", className: "amis-legend-started" },
    { label: "Completed", className: "amis-legend-completed" },
    { label: "Frozen", className: "amis-legend-frozen" },
    { label: "Impacted", className: "amis-legend-impacted" },
    { label: "Event", className: "amis-legend-event" },
    { label: "Mission time", className: "amis-legend-mission-time" },
  ];
  return (
    <ul aria-label="Timeline legend" className="flex items-center gap-3 text-[10px] text-neutral-400">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1">
          <Swatch className={item.className} />
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
  windows,
  events,
  impact,
  selectedRequestId,
  selectedWindowId,
  selectedEventId,
  onSelectRequest,
  onSelectWindow,
  onSelectEvent,
  className,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  replanResult: ReplanResult | null;
  missionState: MissionStateSchema | null;
  windows: ObservationWindowSchema[];
  events: MissionEventSchema[];
  impact: ImpactSchema | null;
  selectedRequestId: string | null;
  selectedWindowId: string | null;
  selectedEventId: string | null;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow: (windowId: string | null) => void;
  onSelectEvent: (eventId: string | null) => void;
  className?: string;
}) {
  const changeByRequestId = currentPlanChanges(plan, replanResult);
  return (
    <PanelFrame
      title="Mission timeline"
      meta={plan === null ? undefined : `V${plan.version}`}
      actions={plan === null ? undefined : <TimelineLegend />}
      className={className}
    >
      {scenario === null || plan === null ? (
        <p className="text-xs text-neutral-500">
          {scenario === null
            ? "Load a scenario and generate a plan to see scheduled actions."
            : "Generate plan to lay the mission's scheduled actions on the timeline."}
        </p>
      ) : (
        <div className="flex max-w-[1100px] flex-col gap-4">
          <PlanTimeline
            key={plan.id}
            label="Mission plan"
            scenario={scenario}
            windows={windows}
            plan={plan}
            missionState={missionState}
            events={events}
            impact={impact}
            changeByRequestId={changeByRequestId}
            selectedRequestId={selectedRequestId}
            selectedWindowId={selectedWindowId}
            selectedEventId={selectedEventId}
            onSelectRequest={onSelectRequest}
            onSelectWindow={onSelectWindow}
            onSelectEvent={onSelectEvent}
          />
        </div>
      )}
    </PanelFrame>
  );
}
