import { useEffect, useMemo, useRef } from "react";
import moment from "moment";
import { Timeline, type TimelineEventPropertiesResult, type TimelineOptions } from "vis-timeline";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  PlanChangeType,
  ScenarioSchema,
  UnscheduledEntrySchema,
} from "../api/client";
import { missionRequestPool } from "../state/missionEvent";
import {
  buildMissionTimelineModel,
  findWindowAtTime,
  MISSION_EVENTS_GROUP_ID,
  type MissionTimelineGroup,
  type MissionTimelineItem,
} from "../timeline/missionTimelineModel";

const MISSION_NOW_ID = "mission-now";

/** One timeline of one plan, with that plan's unscheduled requests beneath it. */
export interface PlanTimelineProps {
  label: string;
  scenario: ScenarioSchema;
  windows: ObservationWindowSchema[];
  plan: MissionPlanSchema;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  impact: ImpactSchema | null;
  changeByRequestId: Record<string, PlanChangeType>;
  selectedRequestId: string | null;
  selectedWindowId: string | null;
  selectedEventId: string | null;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow: (windowId: string | null) => void;
  onSelectEvent: (eventId: string | null) => void;
}

function priorityOf(scenario: ScenarioSchema, events: MissionEventSchema[], requestId: string): string {
  const request = missionRequestPool(scenario, events).find((candidate) => candidate.id === requestId);
  return request === undefined ? "unknown" : String(request.priority);
}

function UnscheduledList({
  label,
  scenario,
  events,
  entries,
  changeByRequestId,
  selectedRequestId,
  onSelectRequest,
}: {
  label: string;
  scenario: ScenarioSchema;
  events: MissionEventSchema[];
  entries: UnscheduledEntrySchema[];
  changeByRequestId: Record<string, PlanChangeType>;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-[10px] uppercase tracking-widest text-neutral-500">Unscheduled</h4>
      {entries.length === 0 ? (
        <p className="text-xs text-neutral-500">This plan fitted every request in the pool.</p>
      ) : (
        <ul aria-label={`${label} unscheduled requests`} className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {entries.map((entry) => {
            const change = changeByRequestId[entry.request_id];
            return (
              <li
                key={entry.request_id}
                data-request-id={entry.request_id}
                data-change={change}
                className="text-amber-300"
              >
                <button
                  type="button"
                  aria-pressed={selectedRequestId === entry.request_id}
                  onClick={() => onSelectRequest(selectedRequestId === entry.request_id ? null : entry.request_id)}
                  className="border-l-2 border-transparent px-1 text-left hover:bg-white/[0.04] aria-pressed:border-fuchsia-400 aria-pressed:bg-fuchsia-400/10"
                >
                  <span className="font-mono">{entry.request_id}</span>
                  {" · priority "}
                  {priorityOf(scenario, events, entry.request_id)}
                  {" · "}
                  <span className="font-mono text-amber-400">{entry.reason_code}</span>
                  {change === undefined ? null : (
                    <span className="font-mono text-pink-400">{` · ${change}`}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function timelineOptions(
  groupCount: number,
  start: string,
  end: string,
  onSelectRequest: (requestId: string | null) => void,
): TimelineOptions {
  const duration = Math.max(new Date(end).getTime() - new Date(start).getTime(), 1);
  return {
    start,
    end,
    min: start,
    max: end,
    height: Math.min(Math.max(groupCount * 32 + 50, 115), 350),
    orientation: "top",
    editable: false,
    selectable: true,
    multiselect: true,
    stack: true,
    moveable: true,
    zoomable: true,
    zoomMin: Math.max(Math.floor(duration / 100), 60_000),
    zoomMax: duration,
    showCurrentTime: false,
    showMajorLabels: true,
    showMinorLabels: true,
    verticalScroll: true,
    horizontalScroll: true,
    groupHeightMode: "fitItems",
    margin: { axis: 4, item: { horizontal: 3, vertical: 5 } },
    dataAttributes: [
      "kind",
      "request-id",
      "window-id",
      "action-id",
      "event-id",
      "status",
      "frozen",
      "impacted",
      "change",
      "selected",
    ],
    moment: (value) => moment.utc(value),
    format: {
      minorLabels: { minute: "HH:mm", hour: "HH:mm", day: "DD" },
      majorLabels: {
        minute: "YYYY-MM-DD [UTC]",
        hour: "YYYY-MM-DD [UTC]",
        day: "YYYY-MM-DD [UTC]",
      },
    },
    groupTemplate: (rawGroup) => {
      if (rawGroup === null) {
        return document.createElement("span");
      }
      const group = rawGroup as MissionTimelineGroup;
      // The mission lane is not an observation request, so it renders a
      // static label rather than a request-selection button.
      if (group.requestId === MISSION_EVENTS_GROUP_ID) {
        const label = document.createElement("span");
        label.className = "amis-timeline-group-label";
        label.textContent = "Mission events";
        label.title = String(group.title ?? "Mission-level events");
        return label;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "amis-timeline-group-button";
      button.textContent = `${group.requestId} · P${group.priority}`;
      button.title = String(group.title ?? group.requestId);
      button.dataset.requestId = group.requestId;
      button.dataset.selected = group.selected ? "true" : "false";
      button.setAttribute("aria-pressed", String(group.selected));
      button.setAttribute("aria-label", `${group.requestId}, priority ${group.priority}`);
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectRequest(group.selected ? null : group.requestId);
      });
      return button;
    },
  };
}

function selectedItemIds(items: MissionTimelineItem[]): Array<string | number> {
  return items.filter((item) => item.selected && item.kind !== "window").map((item) => item.id);
}

function decorateTimelineItems(container: HTMLElement) {
  for (const element of Array.from(
    container.querySelectorAll<HTMLElement>(".vis-item[data-kind], .vis-item [data-kind]"),
  )) {
    const kind = element.dataset.kind;
    const id =
      element.dataset.actionId ?? element.dataset.windowId ?? element.dataset.eventId ?? "item";
    element.tabIndex = 0;
    element.setAttribute("role", "button");
    element.setAttribute("aria-label", `Select ${kind} ${id}`);
  }
}

export function PlanTimeline({
  label,
  scenario,
  windows,
  plan,
  missionState,
  events,
  impact,
  changeByRequestId,
  selectedRequestId,
  selectedWindowId,
  selectedEventId,
  onSelectRequest,
  onSelectWindow,
  onSelectEvent,
}: PlanTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);
  const keyboardFocusedItemRef = useRef<{ kind: string; id: string } | null>(null);
  const hasMissionNowRef = useRef(false);
  const itemByIdRef = useRef(new Map<string | number, MissionTimelineItem>());

  const model = useMemo(
    () =>
      buildMissionTimelineModel({
        scenario,
        windows,
        plan,
        missionState,
        events,
        impact,
        selectedRequestId,
        selectedWindowId,
        selectedEventId,
        changeByRequestId,
      }),
    [
      scenario,
      windows,
      plan,
      missionState,
      events,
      impact,
      selectedRequestId,
      selectedWindowId,
      selectedEventId,
      changeByRequestId,
    ],
  );
  useEffect(() => {
    itemByIdRef.current = new Map(model.items.map((item) => [item.id, item]));
  }, [model.items]);

  useEffect(() => {
    if (containerRef.current === null) {
      return;
    }
    const timeline = new Timeline(
      containerRef.current,
      [],
      [],
      timelineOptions(
        model.groups.length,
        model.bounds.start,
        model.bounds.end,
        onSelectRequest,
      ),
    );
    timelineRef.current = timeline;
    const container = containerRef.current;

    const selectElement = (element: HTMLElement) => {
      const kind = element.dataset.kind;
      const nextId = element.dataset.selected === "true" ? null : undefined;
      if (kind === "event") {
        onSelectEvent(nextId === null ? null : element.dataset.eventId ?? null);
      } else if (kind === "action" || kind === "window") {
        onSelectWindow(nextId === null ? null : element.dataset.windowId ?? null);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      const element =
        event.target instanceof Element
          ? event.target.closest<HTMLElement>("[data-kind]")
          : null;
      if (element === null || !container.contains(element)) {
        return;
      }
      const id = element.dataset.actionId ?? element.dataset.windowId ?? element.dataset.eventId;
      if (id !== undefined) {
        keyboardFocusedItemRef.current = { kind: element.dataset.kind ?? "", id };
      }
      event.preventDefault();
      event.stopPropagation();
      selectElement(element);
    };

    const handleChanged = () => decorateTimelineItems(container);
    container.addEventListener("keydown", handleKeyDown);
    timeline.on("changed", handleChanged);

    const handleClick = (properties: TimelineEventPropertiesResult) => {
      if (properties.item === null || properties.item === undefined) {
        if (properties.group !== null && properties.group !== undefined && properties.time instanceof Date) {
          const window = findWindowAtTime(
            [...itemByIdRef.current.values()],
            properties.group,
            properties.time,
          );
          if (window !== undefined) {
            onSelectWindow(window.selected ? null : window.windowId);
          }
        }
        return;
      }
      const item = itemByIdRef.current.get(properties.item);
      if (item?.kind === "event") {
        onSelectEvent(item.selected ? null : item.eventId);
      } else if (item?.kind === "action" || item?.kind === "window") {
        onSelectWindow(item.selected ? null : item.windowId);
      }
    };
    timeline.on("click", handleClick);

    return () => {
      container.removeEventListener("keydown", handleKeyDown);
      timeline.off("changed", handleChanged);
      timeline.off("click", handleClick);
      timeline.destroy();
      timelineRef.current = null;
      hasMissionNowRef.current = false;
    };
  }, [model.bounds.end, model.bounds.start, model.groups.length, onSelectEvent, onSelectRequest, onSelectWindow]);

  useEffect(() => {
    const timeline = timelineRef.current;
    if (timeline === null) {
      return;
    }
    const container = containerRef.current;
    const activeItem =
      container !== null && document.activeElement instanceof HTMLElement
        ? document.activeElement.closest<HTMLElement>(".vis-item[data-kind]")
        : null;
    const focusedIdentity =
      activeItem !== null && container?.contains(activeItem)
        ? {
            kind: activeItem.dataset.kind,
            id:
              activeItem.dataset.actionId ??
              activeItem.dataset.windowId ??
              activeItem.dataset.eventId,
          }
        : document.activeElement === document.body
          ? keyboardFocusedItemRef.current
          : null;
    timeline.setData({ groups: model.groups, items: model.items });
    timeline.redraw();
    if (container !== null) {
      decorateTimelineItems(container);
      if (focusedIdentity?.id !== undefined) {
        const replacement = Array.from(container.querySelectorAll<HTMLElement>(".vis-item[data-kind]"))
          .find((element) =>
            element.dataset.kind === focusedIdentity.kind &&
            (element.dataset.actionId ?? element.dataset.windowId ?? element.dataset.eventId) === focusedIdentity.id,
          );
        replacement?.focus();
      }
    }
    keyboardFocusedItemRef.current = null;
    timeline.setSelection(selectedItemIds(model.items));
    if (model.bounds.current === null) {
      if (hasMissionNowRef.current) {
        timeline.removeCustomTime(MISSION_NOW_ID);
        hasMissionNowRef.current = false;
      }
      return;
    }
    if (hasMissionNowRef.current) {
      timeline.setCustomTime(model.bounds.current, MISSION_NOW_ID);
    } else {
      timeline.addCustomTime(model.bounds.current, MISSION_NOW_ID);
      hasMissionNowRef.current = true;
    }
    timeline.setCustomTimeTitle(
      `Mission time: ${new Date(model.bounds.current).toISOString()}`,
      MISSION_NOW_ID,
    );
  }, [model]);

  return (
    <div role="group" aria-label={label} className="flex min-w-0 flex-col gap-1.5">
      <h3 className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-neutral-400">
        {label} <span className="text-neutral-500">V{plan.version}</span>
        <span className="normal-case tracking-normal text-neutral-600">UTC · drag to inspect · wheel to zoom</span>
      </h3>
      <div
        ref={containerRef}
        role="group"
        aria-label={`${label} timeline of observation windows, scheduled actions, mission events, and mission time`}
        className="amis-vis-timeline min-w-0"
      />
      <UnscheduledList
        label={label}
        scenario={scenario}
        events={events}
        entries={plan.unscheduled}
        changeByRequestId={changeByRequestId}
        selectedRequestId={selectedRequestId}
        onSelectRequest={onSelectRequest}
      />
    </div>
  );
}
