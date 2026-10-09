import { useEffect, useMemo, useState } from "react";
import { fetchMetrics } from "../api/amis";
import type {
  ContactWindowSchema,
  ImpactSchema,
  MetricsSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  PlanChangeType,
  PlanDiffSchema,
  ScenarioSchema,
} from "../api/client";
import { planLabel } from "../state/planContext";
import { StorageProfileChart } from "./StorageProfileChart";
import type { ReplanResult } from "../state/types";
import { PanelFrame } from "./PanelFrame";
import { PlanTimeline } from "./PlanTimeline";

const NO_CHANGES: Record<string, PlanChangeType> = {};
const NO_RESPONSE: NonNullable<MetricsSchema["emergency_response"]> = [];

/**
 * The metrics whose emergency response the timeline draws: the selected
 * plan's own when an earlier version is selected (its RequestPool excludes
 * later arrivals and its planned attribution is its own), otherwise the
 * displayed plan's. Refetched whenever the displayed plan's metrics change,
 * which happens after every injection, replan, clock step, and reload.
 */
function useResponseMetrics(
  plan: MissionPlanSchema | null,
  metrics: MetricsSchema | null,
  selectedPlanId: string | null,
  loadPlanMetrics: (planId: string) => Promise<MetricsSchema>,
): MetricsSchema | null {
  const historicalPlanId =
    selectedPlanId !== null && plan !== null && selectedPlanId !== plan.id ? selectedPlanId : null;
  const [fetched, setFetched] = useState<MetricsSchema | null>(null);
  useEffect(() => {
    if (historicalPlanId === null) {
      return;
    }
    let cancelled = false;
    loadPlanMetrics(historicalPlanId).then(
      (next) => {
        if (!cancelled) setFetched(next);
      },
      () => {
        if (!cancelled) setFetched(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [historicalPlanId, metrics, loadPlanMetrics]);
  if (historicalPlanId !== null) {
    return fetched?.plan_id === historicalPlanId ? fetched : null;
  }
  // Metrics fetched for another plan describe nothing drawn here.
  return metrics !== null && plan !== null && metrics.plan_id === plan.id ? metrics : null;
}

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
    { label: "Planned response", className: "amis-legend-response-planned" },
    { label: "Achieved response", className: "amis-legend-response-achieved" },
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
  contacts,
  events,
  impact,
  metrics = null,
  plans = [],
  selectedPlanId = null,
  loadPlanMetrics = fetchMetrics,
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
  contacts?: ContactWindowSchema[];
  events: MissionEventSchema[];
  impact: ImpactSchema | null;
  /** The displayed plan's metrics; their emergency response draws the response segments. */
  metrics?: MetricsSchema | null;
  plans?: readonly MissionPlanSchema[];
  /** A selected earlier plan whose emergency response the segments show instead. */
  selectedPlanId?: string | null;
  loadPlanMetrics?: (planId: string) => Promise<MetricsSchema>;
  selectedRequestId: string | null;
  selectedWindowId: string | null;
  selectedEventId: string | null;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow: (windowId: string | null) => void;
  onSelectEvent: (eventId: string | null) => void;
  className?: string;
}) {
  const changeByRequestId = useMemo(() => currentPlanChanges(plan, replanResult), [plan, replanResult]);
  const responseMetrics = useResponseMetrics(plan, metrics, selectedPlanId, loadPlanMetrics);
  const emergencyResponse = responseMetrics?.emergency_response ?? NO_RESPONSE;
  const responsePlanLabel =
    responseMetrics !== null && plan !== null && responseMetrics.plan_id !== plan.id
      ? planLabel(responseMetrics.plan_id, plans)
      : undefined;
  return (
    <PanelFrame
      title="Mission timeline"
      meta={
        plan === null
          ? undefined
          : responsePlanLabel === undefined
            ? `V${plan.version}`
            : `V${plan.version} · emergency response for ${responsePlanLabel}`
      }
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
        <div className="flex min-w-0 flex-col gap-2">
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
            contacts={contacts}
            emergencyResponse={emergencyResponse}
            responsePlanLabel={responsePlanLabel}
            selectedRequestId={selectedRequestId}
            selectedWindowId={selectedWindowId}
            selectedEventId={selectedEventId}
            onSelectRequest={onSelectRequest}
            onSelectWindow={onSelectWindow}
            onSelectEvent={onSelectEvent}
          />
          <StorageProfileChart scenario={scenario} plan={plan} missionState={missionState} />
        </div>
      )}
    </PanelFrame>
  );
}
