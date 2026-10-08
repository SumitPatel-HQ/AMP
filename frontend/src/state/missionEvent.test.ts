import { describe, expect, it } from "vitest";
import type {
  MissionEventSchema,
  MissionPlanSchema,
  PlanDiffSchema,
  ScenarioSchema,
} from "../api/client";
import { cueEvent } from "../test/mapFixtures";
import {
  buildEmergencyRequestEvent,
  cueEvidence,
  emergencyEvidence,
  emergencyRequestDefaults,
  eventSummary,
  introducedRequests,
  missionRequestPool,
  newlyUnscheduled,
} from "./missionEvent";

const cloudBlock = {
  id: "EVT-001",
  scenario_id: "SCN",
  event_time: "2026-09-21T10:05:00Z",
  event_type: "CLOUD_BLOCK",
  payload: { request_id: "OBS-B", window_id: "WIN-OBS-B-1" },
} satisfies MissionEventSchema;

const batteryDrop = {
  id: "EVT-002",
  scenario_id: "SCN",
  event_time: "2026-09-21T10:06:00Z",
  event_type: "BATTERY_DROP",
  payload: { satellite_id: "SAT-001", new_battery_wh: 120 },
} satisfies MissionEventSchema;

const emergency = {
  id: "EVT-003",
  scenario_id: "SCN",
  event_time: "2026-09-21T10:07:00Z",
  event_type: "EMERGENCY_TASK",
  payload: {
    request: {
      id: "OBS-EMERGENCY",
      target_lat: 34.05,
      target_lon: -118.24,
      priority: 5,
      duration_s: 600,
      deadline: "2026-09-21T10:50:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
    windows: [
      {
        id: "WIN-OBS-EMERGENCY-1",
        request_id: "OBS-EMERGENCY",
        satellite_id: "SAT-001",
        start: "2026-09-21T10:40:00Z",
        end: "2026-09-21T10:55:00Z",
        valid: true,
        invalid_reason: null,
      },
    ],
  },
} satisfies MissionEventSchema;

function plan(id: string, unscheduled: MissionPlanSchema["unscheduled"]): MissionPlanSchema {
  return {
    id,
    scenario_id: "SCN",
    version: 1,
    parent_plan_id: null,
    created_at: "2026-09-21T10:00:00Z",
    actions: [],
    unscheduled,
    mission_utility: 0,
    violation_count: 0,
    planning_time_ms: 0,
    planner_name: "greedy",
  };
}

describe("eventSummary", () => {
  it("names the blocked request and window of a cloud block", () => {
    expect(eventSummary(cloudBlock)).toBe("OBS-B / WIN-OBS-B-1");
  });

  it("appends the archived-weather evidence of a weather-derived block", () => {
    const weatherBlock = {
      ...cloudBlock,
      payload: {
        ...cloudBlock.payload,
        source: "open-meteo-archive",
        cloud_cover_pct: 85,
        threshold_pct: 50,
      },
    } satisfies MissionEventSchema;
    expect(eventSummary(weatherBlock)).toBe(
      "OBS-B / WIN-OBS-B-1 · 85% cloud ≥ 50% (open-meteo-archive)",
    );
  });

  it("gives the battery value a battery drop set, with no request", () => {
    expect(eventSummary(batteryDrop)).toBe("SAT-001 battery → 120.0 Wh");
  });

  it("names the emergency request, its priority and window count", () => {
    expect(eventSummary(emergency)).toBe("OBS-EMERGENCY · P5 · 1 window");
  });
});

describe("introducedRequests", () => {
  it("reads emergency requests from the event log, in log order, with their event", () => {
    expect(introducedRequests([cloudBlock, emergency, batteryDrop])).toEqual([
      { eventId: "EVT-003", request: emergency.payload.request },
    ]);
  });
});

describe("newlyUnscheduled", () => {
  it("reads DROPPED entries from the backend diff and adds unscheduled requests the parent never held", () => {
    const previous = plan("P1", [{ request_id: "OBS-D", reason_code: "TIME_OVERLAP" }]);
    const revised = plan("P2", [
      { request_id: "OBS-D", reason_code: "TIME_OVERLAP" },
      { request_id: "OBS-C", reason_code: "NO_ALTERNATIVE_WINDOW" },
      { request_id: "OBS-EMERGENCY", reason_code: "TIME_OVERLAP" },
    ]);
    const diff = {
      from_plan_id: "P1",
      to_plan_id: "P2",
      entries: [
        { request_id: "OBS-C", change_type: "DROPPED", reason_code: "NO_ALTERNATIVE_WINDOW", old_start: "2026-09-21T10:30:00Z", new_start: null },
        { request_id: "OBS-D", change_type: "UNCHANGED", reason_code: "REQUEST_UNCHANGED", old_start: null, new_start: null },
        { request_id: "OBS-EMERGENCY", change_type: "UNCHANGED", reason_code: "REQUEST_UNCHANGED", old_start: null, new_start: null },
      ],
      request_pool_mismatch: true,
    } satisfies PlanDiffSchema;
    const previousWithC = {
      ...previous,
      actions: [
        {
          id: "ACT-OBS-C-1",
          request_id: "OBS-C",
          satellite_id: "SAT-001",
          window_id: "WIN-OBS-C-1",
          start: "2026-09-21T10:30:00Z",
          end: "2026-09-21T10:40:00Z",
          energy_cost_wh: 40,
          storage_cost_mb: 100,
          status: "planned" as const,
          kind: "imaging" as const,
        },
      ],
    };
    expect(
      newlyUnscheduled({ initialPlan: previousWithC, revisedPlan: revised, diff, traces: [] }),
    ).toEqual([
      { requestId: "OBS-C", reasonCode: "NO_ALTERNATIVE_WINDOW", kind: "dropped" },
      { requestId: "OBS-EMERGENCY", reasonCode: "TIME_OVERLAP", kind: "arrived" },
    ]);
  });
});

describe("missionRequestPool", () => {
  it("lists the scenario requests, then those the event log introduced", () => {
    const scenario = {
      id: "SCN",
      name: "Pool",
      start_time: "2026-09-21T10:00:00Z",
      end_time: "2026-09-21T14:00:00Z",
      satellite: {
        id: "SAT-001",
        battery_capacity_wh: 500,
        battery_charge_wh: 500,
        storage_capacity_mb: 2000,
        storage_usage_mb: 0,
        available: true,
      },
      requests: [{ ...emergency.payload.request, id: "OBS-A" }],
    } satisfies ScenarioSchema;
    expect(missionRequestPool(scenario, [cloudBlock, emergency]).map((request) => request.id)).toEqual([
      "OBS-A",
      "OBS-EMERGENCY",
    ]);
    expect(scenario.requests).toHaveLength(1);
  });
});

describe("emergency request event", () => {
  it("defaults to a free request id and a window after the mission clock", () => {
    const defaults = emergencyRequestDefaults("2026-09-21T10:05:00Z", [
      "OBS-A",
      "OBS-EMERGENCY-1",
    ]);
    expect(defaults.requestId).toBe("OBS-EMERGENCY-2");
    expect(defaults.windowStart).toBe("2026-09-21T10:15");
    expect(defaults.windowEnd).toBe("2026-09-21T10:30");
    expect(defaults.deadline).toBe("2026-09-21T10:30");
  });

  it("builds the EMERGENCY_TASK body with one explicit window on the mission satellite", () => {
    const body = buildEmergencyRequestEvent(
      {
        requestId: "OBS-EMERGENCY",
        targetLat: "34.05",
        targetLon: "-118.24",
        priority: "5",
        durationS: "600",
        deadline: "2026-09-21T10:50",
        energyCostWh: "40",
        storageCostMb: "100",
        windowStart: "2026-09-21T10:40",
        windowEnd: "2026-09-21T10:55",
      },
      "SAT-001",
    );
    expect(body).toEqual({
      event_type: "EMERGENCY_TASK",
      payload: emergency.payload,
    });
  });

  it("refuses a form with a field that is not a number", () => {
    expect(
      buildEmergencyRequestEvent(
        {
          ...emergencyRequestDefaults("2026-09-21T10:05:00Z", []),
          targetLat: "north",
        },
        "SAT-001",
      ),
    ).toBeNull();
  });
});

describe("cue evidence", () => {
  it("reads the recorded evidence and credits the U.S. Geological Survey", () => {
    expect(cueEvidence(cueEvent)).toEqual({
      eventId: "EVT-004",
      requestId: "CUE-1",
      source: "usgs",
      sourceLabel: "U.S. Geological Survey",
      sourceEventId: "us7000test",
      alertLevel: "orange",
      mag: 6.4,
      sig: 650,
    });
    expect(eventSummary(cueEvent)).toBe(
      "CUE-1 · P5 · 0 windows · orange alert us7000test (U.S. Geological Survey)",
    );
  });

  it("leaves manual arrivals and other events without evidence", () => {
    expect(cueEvidence(emergency)).toBeNull();
    expect(cueEvidence(cloudBlock)).toBeNull();
    const { mag: _mag, sig: _sig, ...withoutOptional } = cueEvent.payload;
    expect(cueEvidence({ ...cueEvent, payload: withoutOptional })).toMatchObject({ mag: null, sig: null });
  });
});

describe("cue evidence guard", () => {
  it.each([
    ["a partial group", { source: "usgs", source_event_id: undefined }],
    ["a blank source", { source: "  " }],
    ["a blank source event id", { source_event_id: "" }],
    ["an unsupported alert level", { alert_level: "purple" }],
    ["a non-finite magnitude", { mag: Number.POSITIVE_INFINITY }],
  ])("refuses to display %s the backend would reject", (_label, change) => {
    const payload = { ...cueEvent.payload, ...change } as unknown as typeof cueEvent.payload;
    expect(cueEvidence({ ...cueEvent, payload })).toBeNull();
  });
});

describe("emergency form evidence", () => {
  const base = emergencyRequestDefaults("2026-09-21T10:05:00Z", []);
  const filled = { ...base, targetLat: "38.3", targetLon: "142.4" };

  it("keeps a manual arrival's payload free of evidence keys", () => {
    const body = buildEmergencyRequestEvent(filled, "SAT-001");
    expect(body?.event_type).toBe("EMERGENCY_TASK");
    expect(Object.keys(body!.payload)).toEqual(["request", "windows"]);
  });

  it("attaches a complete evidence group, with optional magnitude and significance", () => {
    const body = buildEmergencyRequestEvent(
      { ...filled, source: "usgs", sourceEventId: "us7000test", alertLevel: "orange", mag: "6.4" },
      "SAT-001",
      true,
    );
    expect(body?.payload).toMatchObject({ source: "usgs", source_event_id: "us7000test", alert_level: "orange", mag: 6.4 });
    expect(body?.payload).not.toHaveProperty("sig");
  });

  it.each([
    ["a partial group", { source: "usgs" }, "together"],
    ["magnitude without a group", { mag: "6" }, "need source"],
    ["an unsupported alert level", { source: "usgs", sourceEventId: "us1", alertLevel: "RED" }, "must be one of"],
    ["a non-numeric significance", { source: "usgs", sourceEventId: "us1", alertLevel: "red", sig: "high" }, "finite numbers"],
  ])("refuses %s like the backend", (_label, change, problem) => {
    const form = { ...filled, ...change };
    expect(buildEmergencyRequestEvent(form, "SAT-001")).toBeNull();
    const result = emergencyEvidence(form);
    expect("problem" in result && result.problem).toContain(problem);
  });
});
