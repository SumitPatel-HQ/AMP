import { describe, expect, it } from "vitest";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import { buildMissionTimelineModel, eventAnchorRequestId, eventAnchorWindowId, findWindowAtTime, MISSION_EVENTS_GROUP_ID } from "./missionTimelineModel";

const scenario = {
  id: "SCN-1",
  name: "Mission",
  start_time: "2026-09-21T10:00:00Z",
  end_time: "2026-09-21T14:00:00Z",
  satellite: {
    id: "SAT-1",
    battery_capacity_wh: 500,
    battery_charge_wh: 500,
    storage_capacity_mb: 2000,
    storage_usage_mb: 0,
    available: true,
  },
  requests: [
    {
      id: "OBS-A",
      target_lat: 12,
      target_lon: 77,
      priority: 5,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
    {
      id: "OBS-B",
      target_lat: 28,
      target_lon: 77,
      priority: 3,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
  ],
} satisfies ScenarioSchema;

const windows = [
  {
    id: "WIN-A",
    request_id: "OBS-A",
    satellite_id: "SAT-1",
    start: "2026-09-21T10:10:00Z",
    end: "2026-09-21T10:40:00Z",
    valid: false,
    invalid_reason: "WINDOW_INVALIDATED",
  },
  {
    id: "WIN-B",
    request_id: "OBS-B",
    satellite_id: "SAT-1",
    start: "2026-09-21T12:00:00Z",
    end: "2026-09-21T12:30:00Z",
    valid: true,
    invalid_reason: null,
  },
] satisfies ObservationWindowSchema[];

const plan = {
  id: "PLAN-1",
  scenario_id: scenario.id,
  version: 1,
  parent_plan_id: null,
  created_at: scenario.start_time,
  actions: [
    {
      id: "ACT-A",
      request_id: "OBS-A",
      satellite_id: "SAT-1",
      window_id: "WIN-A",
      start: "2026-09-21T10:15:00Z",
      end: "2026-09-21T10:25:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "started",
    },
  ],
  unscheduled: [{ request_id: "OBS-B", reason_code: "WINDOW_INVALIDATED" }],
  mission_utility: 5,
  violation_count: 1,
  planning_time_ms: 2,
} satisfies MissionPlanSchema;

const state = {
  scenario_id: scenario.id,
  simulated_time: "2026-09-21T10:20:00Z",
  satellite_id: "SAT-1",
  battery_wh: 480,
  storage_usage_mb: 100,
  available: true,
  active_event_ids: ["EVENT-1"],
  completed_request_ids: [],
  mission_complete: false,
} satisfies MissionStateSchema;

const event = {
  id: "EVENT-1",
  scenario_id: scenario.id,
  event_time: "2026-09-21T10:18:00Z",
  event_type: "CLOUD_BLOCK",
  payload: { request_id: "OBS-A", window_id: "WIN-A" },
} satisfies MissionEventSchema;

const impact = {
  id: "IMPACT-1",
  event_id: event.id,
  evaluated_plan_id: plan.id,
  frozen_action_ids: [],
  valid_unfrozen_action_ids: [],
  invalid_unfrozen_action_ids: ["ACT-A"],
  reason_codes: { "ACT-A": ["WINDOW_INVALIDATED"] },
} satisfies ImpactSchema;

describe("mission timeline model", () => {
  it("maps requests, real windows, actions, events, and mission time without deriving new domain state", () => {
    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan,
      missionState: state,
      events: [event],
      impact,
      selectedRequestId: "OBS-A",
      selectedWindowId: "WIN-A",
      selectedEventId: event.id,
      changeByRequestId: { "OBS-A": "MOVED" },
    });

    expect(model.bounds).toEqual({
      start: scenario.start_time,
      end: scenario.end_time,
      current: state.simulated_time,
    });
    expect(model.groups).toHaveLength(2);
    expect(model.groups[0]).toMatchObject({
      id: "OBS-A",
      requestId: "OBS-A",
      selected: true,
    });

    const windowItem = model.items.find((item) => item.kind === "window");
    expect(windowItem).toMatchObject({
      group: "OBS-A",
      start: windows[0].start,
      end: windows[0].end,
      windowId: "WIN-A",
      selected: true,
    });
    expect(windowItem?.className).toContain("amis-window-invalid");

    const actionItem = model.items.find((item) => item.kind === "action");
    expect(actionItem).toMatchObject({
      group: "OBS-A",
      start: plan.actions[0].start,
      end: plan.actions[0].end,
      actionId: "ACT-A",
      windowId: "WIN-A",
      selected: true,
    });
    expect(actionItem?.className).toContain("amis-action-started");
    expect(actionItem?.className).toContain("amis-action-frozen");
    expect(actionItem?.className).toContain("amis-action-impacted");
    expect(actionItem?.className).toContain("amis-change-moved");

    const eventItem = model.items.find((item) => item.kind === "event");
    expect(eventItem).toMatchObject({
      group: "OBS-A",
      start: event.event_time,
      eventId: event.id,
      selected: true,
    });
  });

  it("does not apply an impact to a different plan version", () => {
    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan: { ...plan, id: "PLAN-2", version: 2 },
      missionState: state,
      events: [event],
      impact,
      selectedRequestId: null,
      selectedWindowId: null,
      selectedEventId: null,
      changeByRequestId: {},
    });

    const actionItem = model.items.find((item) => item.kind === "action");
    expect(actionItem?.className).not.toContain("amis-action-impacted");
  });

  it("finds a background window from its request row and mission time", () => {
    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan,
      missionState: state,
      events: [event],
      impact,
      selectedRequestId: null,
      selectedWindowId: null,
      selectedEventId: null,
      changeByRequestId: {},
    });

    expect(findWindowAtTime(model.items, "OBS-A", new Date("2026-09-21T10:30:00Z"))?.windowId).toBe(
      "WIN-A",
    );
    expect(findWindowAtTime(model.items, "OBS-A", new Date("2026-09-21T11:00:00Z"))).toBeUndefined();
    expect(findWindowAtTime(model.items, "OBS-B", new Date("2026-09-21T10:30:00Z"))).toBeUndefined();
  });

  it("renders a row-less battery-drop marker on the mission lane instead of dropping it", () => {
    // The generated API types only expose the CLOUD_BLOCK payload shape, so
    // future domain payloads are cast: the timeline must render them anyway.
    const batteryEvent = {
      id: "EVENT-BATT",
      scenario_id: scenario.id,
      event_time: "2026-09-21T11:00:00Z",
      event_type: "BATTERY_DROP",
      payload: { satellite_id: "SAT-1", new_battery_wh: 120 },
    } as unknown as MissionEventSchema;

    expect(eventAnchorRequestId(batteryEvent)).toBeNull();
    expect(eventAnchorWindowId(batteryEvent)).toBeNull();

    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan,
      missionState: state,
      events: [batteryEvent],
      impact,
      selectedRequestId: null,
      selectedWindowId: null,
      selectedEventId: batteryEvent.id,
      changeByRequestId: {},
    });

    expect(model.groups.map((group) => group.id)).toEqual([
      "OBS-A",
      "OBS-B",
      MISSION_EVENTS_GROUP_ID,
    ]);
    const marker = model.items.find((item) => item.kind === "event");
    expect(marker).toMatchObject({
      group: MISSION_EVENTS_GROUP_ID,
      start: batteryEvent.event_time,
      eventId: batteryEvent.id,
      selected: true,
    });
  });

  it("renders an emergency request marker on its own row", () => {
    const emergencyEvent = {
      id: "EVENT-EMG",
      scenario_id: scenario.id,
      event_time: "2026-09-21T11:30:00Z",
      event_type: "EMERGENCY_TASK",
      payload: {
        request: {
          id: "OBS-EMG",
          target_lat: 19,
          target_lon: 73,
          priority: 5,
          duration_s: 600,
          deadline: "2026-09-21T14:00:00Z",
          energy_cost_wh: 40,
          storage_cost_mb: 100,
          status: "pending",
        },
        windows: [],
      },
    } as unknown as MissionEventSchema;

    expect(eventAnchorRequestId(emergencyEvent)).toBe("OBS-EMG");

    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan,
      missionState: state,
      events: [emergencyEvent],
      impact,
      selectedRequestId: "OBS-EMG",
      selectedWindowId: null,
      selectedEventId: null,
      changeByRequestId: {},
    });

    expect(model.groups.map((group) => group.id)).toEqual(["OBS-A", "OBS-B", "OBS-EMG"]);
    const marker = model.items.find((item) => item.kind === "event");
    expect(marker).toMatchObject({ group: "OBS-EMG", eventId: emergencyEvent.id });
    expect(model.groups.find((group) => group.id === "OBS-EMG")).toMatchObject({
      selected: true,
    });
  });

  it("draws the backend's window for an emergency request on the emergency row", () => {
    const emergencyWindow = {
      id: "WIN-OBS-EMG-1",
      request_id: "OBS-EMG",
      satellite_id: "SAT-001",
      start: "2026-09-21T11:40:00Z",
      end: "2026-09-21T11:55:00Z",
      valid: true,
      invalid_reason: null,
    };
    const emergencyEvent = {
      id: "EVENT-EMG",
      scenario_id: scenario.id,
      event_time: "2026-09-21T11:30:00Z",
      event_type: "EMERGENCY_TASK",
      payload: {
        request: {
          id: "OBS-EMG",
          target_lat: 19,
          target_lon: 73,
          priority: 5,
          duration_s: 600,
          deadline: "2026-09-21T14:00:00Z",
          energy_cost_wh: 40,
          storage_cost_mb: 100,
          status: "pending",
        },
        windows: [emergencyWindow],
      },
    } satisfies MissionEventSchema;

    const model = buildMissionTimelineModel({
      scenario,
      windows: [...windows, emergencyWindow],
      plan,
      missionState: state,
      events: [emergencyEvent],
      impact,
      selectedRequestId: null,
      selectedWindowId: null,
      selectedEventId: null,
      changeByRequestId: {},
    });

    expect(model.items.find((item) => item.id === "window:WIN-OBS-EMG-1")).toMatchObject({
      group: "OBS-EMG",
      kind: "window",
    });
  });

  it("routes a cloud block for an unknown request to the mission lane", () => {
    const strayEvent = {
      id: "EVENT-STRAY",
      scenario_id: scenario.id,
      event_time: "2026-09-21T11:15:00Z",
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-UNKNOWN", window_id: "WIN-UNKNOWN" },
    } satisfies MissionEventSchema;

    expect(eventAnchorRequestId(strayEvent)).toBe("OBS-UNKNOWN");
    expect(eventAnchorWindowId(strayEvent)).toBe("WIN-UNKNOWN");

    const model = buildMissionTimelineModel({
      scenario,
      windows,
      plan,
      missionState: state,
      events: [strayEvent],
      impact,
      selectedRequestId: null,
      selectedWindowId: null,
      selectedEventId: null,
      changeByRequestId: {},
    });

    const marker = model.items.find((item) => item.kind === "event");
    expect(marker).toMatchObject({ group: MISSION_EVENTS_GROUP_ID });
  });
});
