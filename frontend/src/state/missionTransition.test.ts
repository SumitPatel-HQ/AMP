import { describe, expect, it } from "vitest";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  PlanDiffSchema,
  ScenarioSchema,
} from "../api/client";
import { missionTransition } from "./missionTransition";
import type { ReplanResult } from "./types";

const request = {
  target_lat: 0,
  target_lon: 0,
  priority: 3,
  duration_s: 600,
  deadline: "2026-09-21T14:00:00Z",
  energy_cost_wh: 40,
  storage_cost_mb: 100,
  status: "pending",
} as const;

const scenario = {
  id: "SCN",
  name: "Cloud block",
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
  requests: [
    { ...request, id: "OBS-A" },
    { ...request, id: "OBS-B" },
    { ...request, id: "OBS-C" },
  ],
} satisfies ScenarioSchema;

function action(id: string, requestId: string) {
  return {
    id,
    request_id: requestId,
    satellite_id: "SAT-001",
    window_id: `WIN-${requestId}-1`,
    start: "2026-09-21T10:30:00Z",
    end: "2026-09-21T10:40:00Z",
    energy_cost_wh: 40,
    storage_cost_mb: 100,
    status: "planned",
  } as const;
}

const planV1 = {
  id: "SCN:PLAN-001",
  scenario_id: "SCN",
  version: 1,
  parent_plan_id: null,
  created_at: "2026-09-21T10:00:00Z",
  actions: [action("ACT-001", "OBS-A"), action("ACT-002", "OBS-B")],
  unscheduled: [{ request_id: "OBS-C", reason_code: "TIME_OVERLAP" }],
  mission_utility: 9,
  violation_count: 1,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

const planV2 = {
  ...planV1,
  id: "SCN:PLAN-002",
  version: 2,
  parent_plan_id: planV1.id,
  actions: [action("ACT-001", "OBS-A"), action("ACT-003", "OBS-B"), action("ACT-004", "OBS-C")],
  unscheduled: [],
} satisfies MissionPlanSchema;

const cloudEvent = {
  id: "EVT-001",
  scenario_id: "SCN",
  event_time: "2026-09-21T10:20:00Z",
  event_type: "CLOUD_BLOCK",
  payload: { request_id: "OBS-B", window_id: "WIN-OBS-B-1" },
} satisfies MissionEventSchema;

const impactOnV1 = {
  id: "IMPACT-001",
  event_id: "EVT-001",
  evaluated_plan_id: planV1.id,
  frozen_action_ids: [],
  valid_unfrozen_action_ids: ["ACT-001"],
  invalid_unfrozen_action_ids: ["ACT-002"],
  reason_codes: { "ACT-002": ["WINDOW_INVALIDATED"] },
} satisfies ImpactSchema;

const diff = {
  from_plan_id: planV1.id,
  to_plan_id: planV2.id,
  entries: [],
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

const replanned: ReplanResult = {
  initialPlan: planV1,
  revisedPlan: planV2,
  diff,
  traces: [],
};

describe("missionTransition", () => {
  it("has no stages before a plan exists", () => {
    expect(
      missionTransition({ scenario, plan: null, impact: null, events: [], replanResult: null }),
    ).toEqual({ phase: "no-plan", stages: [] });
  });

  it("shows only the current plan before any event", () => {
    const transition = missionTransition({
      scenario,
      plan: planV1,
      impact: null,
      events: [],
      replanResult: null,
    });

    expect(transition.phase).toBe("planned");
    expect(transition.stages).toEqual([
      {
        kind: "plan",
        role: "current",
        planId: "SCN:PLAN-001",
        version: 1,
        scheduled: 2,
        requestCount: 3,
      },
    ]);
  });

  it("walks plan, event and impact to an awaiting replan once an event hits the current plan", () => {
    const transition = missionTransition({
      scenario,
      plan: planV1,
      impact: impactOnV1,
      events: [cloudEvent],
      replanResult: null,
    });

    expect(transition.phase).toBe("awaiting-replan");
    expect(transition.stages).toEqual([
      {
        kind: "plan",
        role: "evaluated",
        planId: "SCN:PLAN-001",
        version: 1,
        scheduled: 2,
        requestCount: 3,
      },
      {
        kind: "event",
        eventId: "EVT-001",
        eventType: "CLOUD_BLOCK",
        requestId: "OBS-B",
        windowId: "WIN-OBS-B-1",
        time: "2026-09-21T10:20:00Z",
      },
      {
        kind: "impact",
        invalidCount: 1,
        affectedRequestIds: ["OBS-B"],
        reasonCodes: ["WINDOW_INVALIDATED"],
      },
      { kind: "awaiting-replan" },
    ]);
  });

  it("ends at the revised plan once the event's plan has been replanned", () => {
    const transition = missionTransition({
      scenario,
      plan: planV2,
      impact: impactOnV1,
      events: [cloudEvent],
      replanResult: replanned,
    });

    expect(transition.phase).toBe("replanned");
    expect(transition.stages.map((stage) => stage.kind)).toEqual([
      "plan",
      "event",
      "impact",
      "plan",
    ]);
    expect(transition.stages[0]).toMatchObject({ role: "previous", version: 1 });
    expect(transition.stages[3]).toMatchObject({ role: "current", version: 2, scheduled: 3 });
  });

  it("goes straight from previous to current plan when a replan ran without an event", () => {
    const transition = missionTransition({
      scenario,
      plan: planV2,
      impact: null,
      events: [],
      replanResult: replanned,
    });

    expect(transition.phase).toBe("replanned");
    expect(transition.stages).toMatchObject([
      { kind: "plan", role: "previous", version: 1 },
      { kind: "no-event" },
      { kind: "plan", role: "current", version: 2 },
    ]);
  });

  it("awaits a new replan when a later event hits the already revised plan", () => {
    const impactOnV2 = {
      ...impactOnV1,
      id: "IMPACT-002",
      event_id: "EVT-002",
      evaluated_plan_id: planV2.id,
      invalid_unfrozen_action_ids: ["ACT-004"],
      reason_codes: { "ACT-004": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema;
    const secondEvent = {
      ...cloudEvent,
      id: "EVT-002",
      payload: { request_id: "OBS-C", window_id: "WIN-OBS-C-1" },
    } satisfies MissionEventSchema;

    const transition = missionTransition({
      scenario,
      plan: planV2,
      impact: impactOnV2,
      events: [cloudEvent, secondEvent],
      replanResult: replanned,
    });

    expect(transition.phase).toBe("awaiting-replan");
    expect(transition.stages).toMatchObject([
      { kind: "plan", role: "evaluated", version: 2 },
      { kind: "event", eventId: "EVT-002", requestId: "OBS-C" },
      { kind: "impact", affectedRequestIds: ["OBS-C"] },
      { kind: "awaiting-replan" },
    ]);
  });

  it("reports an event with no invalid action as an impact with nothing affected", () => {
    const harmless = {
      ...impactOnV1,
      valid_unfrozen_action_ids: ["ACT-001", "ACT-002"],
      invalid_unfrozen_action_ids: [],
      reason_codes: {},
    } satisfies ImpactSchema;

    const transition = missionTransition({
      scenario,
      plan: planV1,
      impact: harmless,
      events: [cloudEvent],
      replanResult: null,
    });

    expect(transition.stages[2]).toEqual({
      kind: "impact",
      invalidCount: 0,
      affectedRequestIds: [],
      reasonCodes: [],
    });
  });
});
