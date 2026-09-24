import type { DataGroup, DataItem } from "vis-timeline";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  PlanChangeType,
  ScenarioSchema,
} from "../api/client";

export interface MissionTimelineGroup extends DataGroup {
  requestId: string;
  priority: number;
  order: number;
  selected: boolean;
}

interface MissionTimelineItemBase extends DataItem {
  id: string;
  selected: boolean;
  "request-id": string;
  "window-id"?: string;
  "action-id"?: string;
  "event-id"?: string;
  change?: PlanChangeType;
  frozen?: boolean;
  impacted?: boolean;
  status?: string;
}

export interface MissionWindowTimelineItem extends MissionTimelineItemBase {
  kind: "window";
  requestId: string;
  windowId: string;
}

export interface MissionActionTimelineItem extends MissionTimelineItemBase {
  kind: "action";
  requestId: string;
  windowId: string;
  actionId: string;
}

export interface MissionEventTimelineItem extends MissionTimelineItemBase {
  kind: "event";
  requestId: string;
  eventId: string;
}

export type MissionTimelineItem =
  | MissionWindowTimelineItem
  | MissionActionTimelineItem
  | MissionEventTimelineItem;

export interface MissionTimelineModel {
  bounds: {
    start: string;
    end: string;
    current: string | null;
  };
  groups: MissionTimelineGroup[];
  items: MissionTimelineItem[];
}

/**
 * Presentation-only lane for mission-level events that name no observation
 * request (e.g. a battery drop). It is a timeline row, not a domain entity:
 * the backend remains authoritative for what the event means.
 */
export const MISSION_EVENTS_GROUP_ID = "__MISSION_EVENTS__";

export interface MissionTimelineModelInput {
  scenario: ScenarioSchema;
  windows: ObservationWindowSchema[];
  plan: MissionPlanSchema;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  impact: ImpactSchema | null;
  selectedRequestId: string | null;
  selectedWindowId: string | null;
  selectedEventId: string | null;
  changeByRequestId: Record<string, PlanChangeType>;
}

/** Returns the backend window occupying a request row at a given mission time. */
export function findWindowAtTime(
  items: MissionTimelineItem[],
  requestId: string | number,
  time: Date,
): MissionWindowTimelineItem | undefined {
  const timestamp = time.getTime();
  return items.find(
    (item): item is MissionWindowTimelineItem =>
      item.kind === "window" &&
      item.requestId === String(requestId) &&
      new Date(item.start as string).getTime() <= timestamp &&
      new Date(item.end as string).getTime() >= timestamp,
  );
}

function classes(...values: Array<string | false | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function formatUtc(isoTime: string): string {
  return new Date(isoTime).toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function changeClass(change: PlanChangeType | undefined): string | undefined {
  return change === undefined ? undefined : `amis-change-${change.toLowerCase()}`;
}

/**
 * Reads an event payload defensively. The generated API types only expose the
 * CLOUD_BLOCK shape, while the domain already defines battery-drop and
 * emergency-request payloads; the timeline must never drop a marker it does
 * not recognise, so unknown shapes resolve to no anchor instead of vanishing.
 */
function payloadRecord(event: MissionEventSchema): Record<string, unknown> {
  const payload = (event as unknown as { payload?: unknown }).payload;
  return typeof payload === "object" && payload !== null
    ? (payload as Record<string, unknown>)
    : {};
}

function stringField(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/**
 * The observation request an event belongs to, when its payload names one:
 * either directly (`request_id`, e.g. CLOUD_BLOCK) or nested (`request.id`,
 * e.g. EMERGENCY_TASK). Row-less events (e.g. BATTERY_DROP) return null.
 */
export function eventAnchorRequestId(event: MissionEventSchema): string | null {
  const payload = payloadRecord(event);
  const direct = stringField(payload["request_id"]);
  if (direct !== null) {
    return direct;
  }
  const nested = payload["request"];
  if (typeof nested === "object" && nested !== null) {
    return stringField((nested as Record<string, unknown>)["id"]);
  }
  return null;
}

/** The window an event affects, when its payload names one (CLOUD_BLOCK). */
export function eventAnchorWindowId(event: MissionEventSchema): string | null {
  return stringField(payloadRecord(event)["window_id"]);
}

interface EmergencyRow {
  id: string;
  priority: number;
}

/**
 * A request row the timeline must add beyond the scenario's requests: an
 * emergency request arrives via the event log, so the scenario never lists
 * it. Returns null unless the event carries the full nested request.
 */
function emergencyRowOf(
  event: MissionEventSchema,
  knownRequestIds: ReadonlySet<string>,
): EmergencyRow | null {
  const anchor = eventAnchorRequestId(event);
  if (anchor === null || knownRequestIds.has(anchor)) {
    return null;
  }
  const nested = payloadRecord(event)["request"];
  if (typeof nested !== "object" || nested === null) {
    return null;
  }
  const record = nested as Record<string, unknown>;
  if (stringField(record["id"]) !== anchor) {
    return null;
  }
  const priority = record["priority"];
  return {
    id: anchor,
    priority: typeof priority === "number" ? priority : 0,
  };
}

function buildWindowItems(
  windows: ObservationWindowSchema[],
  requestIds: ReadonlySet<string>,
  selectedWindowId: string | null,
): MissionWindowTimelineItem[] {
  return windows
    .filter((window) => requestIds.has(window.request_id))
    .map((window) => {
      const selected = window.id === selectedWindowId;
      const validity = window.valid ? "valid" : "invalid";
      return {
        id: `window:${window.id}`,
        kind: "window",
        requestId: window.request_id,
        windowId: window.id,
        "request-id": window.request_id,
        "window-id": window.id,
        group: window.request_id,
        start: window.start,
        end: window.end,
        type: "background",
        content: "",
        selectable: true,
        selected,
        className: classes(
          "amis-window",
          `amis-window-${validity}`,
          selected && "amis-timeline-selected",
        ),
        title: [
          window.id,
          `${formatUtc(window.start)} to ${formatUtc(window.end)}`,
          window.valid ? "Valid observation window" : window.invalid_reason ?? "Invalid window",
        ].join(" | "),
      };
    });
}

function buildActionItems({
  plan,
  impact,
  selectedWindowId,
  changeByRequestId,
}: Pick<
  MissionTimelineModelInput,
  "plan" | "impact" | "selectedWindowId" | "changeByRequestId"
>): MissionActionTimelineItem[] {
  const applicableImpact = impact?.evaluated_plan_id === plan.id ? impact : null;
  const frozenIds = new Set(applicableImpact?.frozen_action_ids ?? []);
  const invalidIds = new Set(applicableImpact?.invalid_unfrozen_action_ids ?? []);

  return plan.actions.map((action) => {
    const selected = action.window_id === selectedWindowId;
    const frozen = action.status !== "planned" || frozenIds.has(action.id);
    const impacted = invalidIds.has(action.id);
    const change = changeByRequestId[action.request_id];
    return {
      id: `action:${action.id}`,
      kind: "action",
      requestId: action.request_id,
      windowId: action.window_id,
      actionId: action.id,
      "request-id": action.request_id,
      "window-id": action.window_id,
      "action-id": action.id,
      group: action.request_id,
      start: action.start,
      end: action.end,
      type: "range",
      content: action.status,
      selectable: true,
      selected,
      status: action.status,
      frozen,
      impacted,
      change,
      className: classes(
        "amis-action",
        `amis-action-${action.status}`,
        frozen && "amis-action-frozen",
        impacted && "amis-action-impacted",
        selected && "amis-timeline-selected",
        changeClass(change),
      ),
      title: [
        action.id,
        `${formatUtc(action.start)} to ${formatUtc(action.end)}`,
        action.status,
        frozen ? "Frozen" : "Future",
        impacted ? "Impacted by the current event" : null,
        change === undefined ? null : `${change} in this plan version`,
      ]
        .filter((part) => part !== null)
        .join(" | "),
    };
  });
}

function buildEventItems(
  events: MissionEventSchema[],
  requestIds: ReadonlySet<string>,
  emergencyIds: ReadonlySet<string>,
  selectedEventId: string | null,
): MissionEventTimelineItem[] {
  return events.map((event) => {
    const anchor = eventAnchorRequestId(event);
    // Every event renders a marker at its mission time. Request-bound events
    // sit on their request row; anything else sits on the mission lane so a
    // battery drop or otherwise unrecognised event stays visible.
    const group =
      anchor !== null && (requestIds.has(anchor) || emergencyIds.has(anchor))
        ? anchor
        : MISSION_EVENTS_GROUP_ID;
    const selected = event.id === selectedEventId;
    return {
      id: `event:${event.id}`,
      kind: "event" as const,
      requestId: anchor ?? MISSION_EVENTS_GROUP_ID,
      eventId: event.id,
      "request-id": anchor ?? MISSION_EVENTS_GROUP_ID,
      "event-id": event.id,
      group,
      start: event.event_time,
      type: "point" as const,
      content: event.event_type.replaceAll("_", " "),
      selectable: true,
      selected,
      className: classes("amis-event", selected && "amis-timeline-selected"),
      title: `${event.id} | ${event.event_type} | ${formatUtc(event.event_time)}`,
    };
  });
}

/**
 * Maps backend-owned mission facts into vis-timeline rows and items. This file
 * does not infer feasibility, impact, or plan state.
 */
export function buildMissionTimelineModel(
  input: MissionTimelineModelInput,
): MissionTimelineModel {
  const { scenario, selectedRequestId } = input;
  const requestIds = new Set(scenario.requests.map((request) => request.id));
  const groups: MissionTimelineGroup[] = scenario.requests.map((request, order) => {
    const selected = request.id === selectedRequestId;
    return {
      id: request.id,
      requestId: request.id,
      priority: request.priority,
      order,
      content: `${request.id} · P${request.priority}`,
      title: `${request.id}, priority ${request.priority}, deadline ${formatUtc(request.deadline)}`,
      selected,
      className: classes("amis-request-group", selected && "amis-request-group-selected"),
    };
  });

  // Emergency requests arrive via the event log and never appear in the
  // scenario, so each one earns its own row the first time it is seen.
  const emergencyRows = new Map<string, EmergencyRow>();
  for (const event of input.events) {
    const row = emergencyRowOf(event, requestIds);
    if (row !== null && !emergencyRows.has(row.id)) {
      emergencyRows.set(row.id, row);
    }
  }
  for (const row of emergencyRows.values()) {
    const selected = row.id === selectedRequestId;
    groups.push({
      id: row.id,
      requestId: row.id,
      priority: row.priority,
      order: groups.length,
      content: `${row.id} · P${row.priority}`,
      title: `${row.id}, emergency request, priority ${row.priority}`,
      selected,
      className: classes("amis-request-group", selected && "amis-request-group-selected"),
    });
  }

  // Row-less events (battery drops and anything unrecognised) share one
  // mission lane, added only when at least one such event exists.
  const emergencyIds = new Set(emergencyRows.keys());
  const needsMissionLane = input.events.some((event) => {
    const anchor = eventAnchorRequestId(event);
    return anchor === null || (!requestIds.has(anchor) && !emergencyIds.has(anchor));
  });
  if (needsMissionLane) {
    const selected = selectedRequestId === MISSION_EVENTS_GROUP_ID;
    groups.push({
      id: MISSION_EVENTS_GROUP_ID,
      requestId: MISSION_EVENTS_GROUP_ID,
      priority: 0,
      order: groups.length,
      content: "Mission events",
      title: "Mission-level events without an observation request row",
      selected,
      className: classes(
        "amis-request-group",
        "amis-mission-group",
        selected && "amis-request-group-selected",
      ),
    });
  }

  return {
    bounds: {
      start: scenario.start_time,
      end: scenario.end_time,
      current: input.missionState?.simulated_time ?? null,
    },
    groups,
    items: [
      ...buildWindowItems(input.windows, requestIds, input.selectedWindowId),
      ...buildActionItems(input),
      ...buildEventItems(input.events, requestIds, emergencyIds, input.selectedEventId),
    ],
  };
}
