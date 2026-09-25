import { useState } from "react";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationRequestSchema,
  ObservationWindowSchema,
  PlanDiffSchema,
  ScenarioSchema,
} from "../api/client";
import { eventSummary, introducedRequests, type IntroducedRequest } from "../state/missionEvent";
import { planLabel } from "../state/planContext";
import { expiredRequestIds, requestStatus, type RequestState } from "../state/requestStatus";
import type { MissionSelection, ReplanResult } from "../state/types";
import { clockTime } from "./format";
import { PanelFrame } from "./PanelFrame";

type Tab = "requests" | "windows" | "events" | "plans";

const TABS: { id: Tab; label: string }[] = [
  { id: "requests", label: "Requests" },
  { id: "windows", label: "Windows" },
  { id: "events", label: "Events" },
  { id: "plans", label: "Plans" },
];

const ROW =
  "grid w-full cursor-pointer items-baseline gap-x-2 border-l-2 px-2 py-1 text-left text-xs hover:bg-white/[0.04]";

function rowTone(selected: boolean, related = false): string {
  if (selected) return "border-fuchsia-400 bg-fuchsia-400/10 text-neutral-100";
  if (related) return "border-fuchsia-900 text-neutral-200";
  return "border-transparent text-neutral-300";
}

function Empty({ children }: { children: string }) {
  return <p className="px-2 py-1.5 text-xs text-neutral-500">{children}</p>;
}

const STATE_STYLE: Record<RequestState, { dot: string; text: string; label: string }> = {
  completed: { dot: "bg-emerald-400", text: "text-emerald-400", label: "completed" },
  started: { dot: "bg-amber-400", text: "text-amber-300", label: "started" },
  planned: { dot: "bg-sky-400", text: "text-sky-300", label: "planned" },
  invalid: { dot: "bg-red-500", text: "text-red-400", label: "invalid" },
  expired: { dot: "bg-neutral-600", text: "text-neutral-500", label: "expired" },
  unscheduled: { dot: "bg-neutral-500", text: "text-neutral-400", label: "unscheduled" },
  "not-planned": { dot: "bg-neutral-700", text: "text-neutral-600", label: "not planned" },
};

function RequestList({
  scenario,
  introduced,
  plan,
  impact,
  diff,
  completedRequestIds,
  expiredRequestIds,
  selectedRequestId,
  onSelectRequest,
}: {
  scenario: ScenarioSchema;
  /** Emergency requests the event log added; the scenario itself never lists them. */
  introduced: IntroducedRequest[];
  plan: MissionPlanSchema | null;
  impact: ImpactSchema | null;
  /** The last replan's diff; it marks changes only while its plan is current. */
  diff: PlanDiffSchema | null;
  completedRequestIds: ReadonlySet<string>;
  expiredRequestIds: ReadonlySet<string>;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  const rows = [
    ...scenario.requests.map((request) => ({ request, eventId: null as string | null })),
    ...introduced.map(({ request, eventId }) => ({ request, eventId })),
  ];
  return (
    <ul aria-label="Observation requests">
      {rows.map(({ request, eventId }) => {
        const selected = request.id === selectedRequestId;
        const status = requestStatus(request.id, {
          plan,
          completedRequestIds,
          expiredRequestIds,
          impact,
          diff,
        });
        const style = STATE_STYLE[status.state];
        const detail = [
          eventId === null ? null : `emergency · ${eventId}`,
          status.change,
          status.reasonCode,
        ].filter((part) => part !== null);
        return (
          <li key={request.id}>
            <button
              type="button"
              aria-pressed={selected}
              data-selected={selected ? "true" : undefined}
              data-plan-status={status.state}
              data-emergency={eventId === null ? undefined : "true"}
              title={`deadline ${clockTime(request.deadline)} UTC`}
              onClick={() => onSelectRequest(selected ? null : request.id)}
              className={`${ROW} grid-cols-[auto_1fr_auto_5.5rem] items-center ${rowTone(selected)}`}
            >
              <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
              <span className="truncate font-semibold">{request.id}</span>
              <span className="text-[10px] text-neutral-500" title="priority">
                P{request.priority}
              </span>
              <span className={`truncate text-[10px] uppercase tracking-wide ${style.text}`}>
                {style.label}
              </span>
              {detail.length === 0 ? null : (
                <span className="col-span-3 col-start-2 truncate text-[10px] text-neutral-500">
                  {detail.join(" · ")}
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function WindowList({
  windows,
  plan,
  selection,
  onSelectWindow,
}: {
  windows: ObservationWindowSchema[];
  plan: MissionPlanSchema | null;
  selection: MissionSelection;
  onSelectWindow: (windowId: string | null) => void;
}) {
  if (windows.length === 0) {
    return <Empty>Generate a plan to compute observation windows.</Empty>;
  }
  const plannedWindowIds = new Set(plan?.actions.map((action) => action.window_id) ?? []);
  const ordered = [...windows].sort(
    (left, right) => new Date(left.start).getTime() - new Date(right.start).getTime(),
  );
  return (
    <ul aria-label="Observation windows">
      {ordered.map((window) => {
        const selected = window.id === selection.windowId;
        const related = window.request_id === selection.requestId;
        return (
          <li key={window.id}>
            <button
              type="button"
              aria-pressed={selected}
              data-selected={selected ? "true" : undefined}
              data-valid={window.valid ? "true" : "false"}
              onClick={() => onSelectWindow(selected ? null : window.id)}
              className={`${ROW} grid-cols-[1fr_auto] ${rowTone(selected, related)}`}
            >
              <span className="truncate">{window.id}</span>
              <span className="text-[10px] tabular-nums text-neutral-500">
                {clockTime(window.start)}–{clockTime(window.end)}
              </span>
              <span className="col-span-2 flex gap-2 truncate text-[10px]">
                <span className="text-neutral-500">{window.request_id}</span>
                {plannedWindowIds.has(window.id) ? (
                  <span className="text-sky-300">in plan</span>
                ) : null}
                {window.valid ? null : (
                  <span className="text-red-400">
                    invalid{window.invalid_reason === null ? "" : ` · ${window.invalid_reason}`}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function EventList({
  events,
  missionState,
  selectedEventId,
  onSelectEvent,
}: {
  events: MissionEventSchema[];
  missionState: MissionStateSchema | null;
  selectedEventId: string | null;
  onSelectEvent: (eventId: string | null) => void;
}) {
  if (events.length === 0) {
    return <Empty>No events injected.</Empty>;
  }
  const activeIds = new Set(missionState?.active_event_ids ?? []);
  return (
    <ul aria-label="Mission events">
      {events.map((event) => {
        const selected = event.id === selectedEventId;
        return (
          <li key={event.id}>
            <button
              type="button"
              aria-pressed={selected}
              data-selected={selected ? "true" : undefined}
              onClick={() => onSelectEvent(selected ? null : event.id)}
              className={`${ROW} grid-cols-[1fr_auto] ${rowTone(selected)}`}
            >
              <span className="truncate font-semibold">{event.id}</span>
              <span className="text-[10px] tabular-nums text-neutral-500">
                {clockTime(event.event_time)}
              </span>
              <span className="col-span-2 flex gap-2 truncate text-[10px]">
                <span className="text-amber-300">{event.event_type}</span>
                <span className="truncate text-neutral-500">{eventSummary(event)}</span>
                {activeIds.has(event.id) ? <span className="text-amber-400">active</span> : null}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function PlanList({
  plan,
  plans,
  selectedPlanId,
  onSelectPlan,
}: {
  plan: MissionPlanSchema | null;
  plans: readonly MissionPlanSchema[];
  selectedPlanId: string | null;
  onSelectPlan: (planId: string | null) => void;
}) {
  if (plans.length === 0) {
    return <Empty>No plan generated.</Empty>;
  }
  return (
    <ul aria-label="Mission plans">
      {plans.map((candidate) => {
        const selected = candidate.id === selectedPlanId;
        const current = candidate.id === plan?.id;
        return (
          <li key={candidate.id}>
            <button
              type="button"
              aria-pressed={selected}
              data-selected={selected ? "true" : undefined}
              onClick={() => onSelectPlan(selected ? null : candidate.id)}
              className={`${ROW} grid-cols-[auto_1fr_auto] ${rowTone(selected)}`}
            >
              <span className="font-semibold">{planLabel(candidate.id, plans)}</span>
              <span className="truncate text-[10px] text-neutral-500">{candidate.id}</span>
              {current ? (
                <span className="text-[10px] uppercase text-emerald-400">current</span>
              ) : (
                <span />
              )}
              <span className="col-span-3 text-[10px] text-neutral-400">
                {candidate.actions.length} actions · {candidate.unscheduled.length} unscheduled ·
                utility {candidate.mission_utility.toFixed(1)}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The mission's objects by kind. Each list selects into the shared selection,
 * so the map, timeline and trace follow what is picked here.
 */
export function MissionNavPanel({
  scenario,
  plan,
  plans,
  replanResult,
  impact,
  missionState,
  windows,
  events,
  requestPool,
  selection,
  onSelectRequest,
  onSelectWindow,
  onSelectEvent,
  onSelectPlan,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  plans: readonly MissionPlanSchema[];
  replanResult: ReplanResult | null;
  impact: ImpactSchema | null;
  missionState: MissionStateSchema | null;
  windows: ObservationWindowSchema[];
  events: MissionEventSchema[];
  /** The backend's request pool; its statuses carry expiry, which nothing else reports. */
  requestPool: ObservationRequestSchema[];
  selection: MissionSelection;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow: (windowId: string | null) => void;
  onSelectEvent: (eventId: string | null) => void;
  onSelectPlan: (planId: string | null) => void;
}) {
  const [tab, setTab] = useState<Tab>("requests");
  const introduced = introducedRequests(events);
  const counts: Record<Tab, number> = {
    requests: (scenario?.requests.length ?? 0) + introduced.length,
    windows: windows.length,
    events: events.length,
    plans: plans.length,
  };

  return (
    <PanelFrame title="Mission" bodyClassName="flex flex-col">
      <div role="tablist" aria-label="Mission objects" className="amis-object-tabs flex shrink-0 border-b border-[var(--amis-border)]">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex-1 whitespace-nowrap border-b-2 px-1 py-1 text-[10px] uppercase tracking-wide ${
              tab === id
                ? "border-neutral-300 text-neutral-100"
                : "border-transparent text-neutral-500 hover:text-neutral-300"
            }`}
          >
            {label} <span className="amis-tab-count text-neutral-600">{counts[id]}</span>
          </button>
        ))}
      </div>
      <div role="tabpanel" className="min-h-0 flex-1 overflow-auto py-1">
        {scenario === null ? (
          <Empty>Load a scenario to list its mission objects.</Empty>
        ) : tab === "requests" ? (
          <RequestList
            scenario={scenario}
            introduced={introduced}
            plan={plan}
            impact={impact}
            diff={replanResult?.diff ?? null}
            completedRequestIds={new Set(missionState?.completed_request_ids ?? [])}
            expiredRequestIds={expiredRequestIds(requestPool)}
            selectedRequestId={selection.requestId}
            onSelectRequest={onSelectRequest}
          />
        ) : tab === "windows" ? (
          <WindowList
            windows={windows}
            plan={plan}
            selection={selection}
            onSelectWindow={onSelectWindow}
          />
        ) : tab === "events" ? (
          <EventList
            events={events}
            missionState={missionState}
            selectedEventId={selection.eventId}
            onSelectEvent={onSelectEvent}
          />
        ) : (
          <PlanList
            plan={plan}
            plans={plans}
            selectedPlanId={selection.planId}
            onSelectPlan={onSelectPlan}
          />
        )}
      </div>
    </PanelFrame>
  );
}
