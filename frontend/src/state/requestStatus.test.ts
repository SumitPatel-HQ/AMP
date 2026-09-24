import { describe, expect, it } from "vitest";
import type { ImpactSchema, MissionPlanSchema, PlanDiffSchema } from "../api/client";
import { requestStatus } from "./requestStatus";

function action(id: string, requestId: string, status: "planned" | "started" | "completed") {
  return {
    id,
    request_id: requestId,
    satellite_id: "SAT-001",
    window_id: `WIN-${requestId}-1`,
    start: "2026-09-21T10:30:00Z",
    end: "2026-09-21T10:40:00Z",
    energy_cost_wh: 40,
    storage_cost_mb: 100,
    status,
  } as const;
}

const plan = {
  id: "SCN:PLAN-002",
  scenario_id: "SCN",
  version: 2,
  parent_plan_id: "SCN:PLAN-001",
  created_at: "2026-09-21T10:00:00Z",
  actions: [
    action("ACT-001", "OBS-A", "completed"),
    action("ACT-002", "OBS-B", "planned"),
    action("ACT-003", "OBS-C", "started"),
  ],
  unscheduled: [{ request_id: "OBS-D", reason_code: "TIME_OVERLAP" }],
  mission_utility: 9,
  violation_count: 1,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

const none = { completedRequestIds: new Set<string>(), impact: null, diff: null };

describe("requestStatus", () => {
  it("is not planned while no plan exists", () => {
    expect(requestStatus("OBS-A", { ...none, plan: null })).toEqual({
      state: "not-planned",
      reasonCode: null,
      change: null,
    });
  });

  it("reads completed once, whether the clock or the plan reports it", () => {
    expect(
      requestStatus("OBS-A", { ...none, plan, completedRequestIds: new Set(["OBS-A"]) }).state,
    ).toBe("completed");
    expect(requestStatus("OBS-A", { ...none, plan }).state).toBe("completed");
    expect(
      requestStatus("OBS-B", { ...none, plan, completedRequestIds: new Set(["OBS-B"]) }).state,
    ).toBe("completed");
  });

  it("follows the action status of a scheduled request", () => {
    expect(requestStatus("OBS-B", { ...none, plan }).state).toBe("planned");
    expect(requestStatus("OBS-C", { ...none, plan }).state).toBe("started");
  });

  it("keeps the planner's reason for an unscheduled request", () => {
    expect(requestStatus("OBS-D", { ...none, plan })).toEqual({
      state: "unscheduled",
      reasonCode: "TIME_OVERLAP",
      change: null,
    });
  });

  it("marks an action the current plan's impact invalidated", () => {
    const impact = {
      id: "IMPACT-001",
      event_id: "EVT-001",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: [],
      invalid_unfrozen_action_ids: ["ACT-002"],
      reason_codes: { "ACT-002": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema;

    expect(requestStatus("OBS-B", { ...none, plan, impact })).toEqual({
      state: "invalid",
      reasonCode: "WINDOW_INVALIDATED",
      change: null,
    });
    expect(
      requestStatus("OBS-B", { ...none, plan, impact: { ...impact, evaluated_plan_id: "SCN:PLAN-001" } })
        .state,
    ).toBe("planned");
  });

  it("carries the last replan's change only when that replan produced the current plan", () => {
    const diff = {
      from_plan_id: "SCN:PLAN-001",
      to_plan_id: plan.id,
      entries: [
        {
          request_id: "OBS-B",
          change_type: "MOVED",
          reason_code: "ALTERNATIVE_WINDOW_AVAILABLE",
          old_start: "2026-09-21T10:20:00Z",
          new_start: "2026-09-21T10:30:00Z",
        },
        {
          request_id: "OBS-A",
          change_type: "COMPLETED",
          reason_code: "REQUEST_UNCHANGED",
          old_start: null,
          new_start: null,
        },
      ],
      request_pool_mismatch: false,
    } satisfies PlanDiffSchema;

    expect(requestStatus("OBS-B", { ...none, plan, diff }).change).toBe("MOVED");
    expect(requestStatus("OBS-A", { ...none, plan, diff }).change).toBeNull();
    expect(
      requestStatus("OBS-B", { ...none, plan, diff: { ...diff, to_plan_id: "SCN:PLAN-003" } }).change,
    ).toBeNull();
  });
});
