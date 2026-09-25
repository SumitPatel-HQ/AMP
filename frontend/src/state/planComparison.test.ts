import { describe, expect, it } from "vitest";
import type {
  DecisionTraceSchema,
  MissionPlanSchema,
  PlanDiffSchema,
} from "../api/client";
import type { ReplanResult } from "./types";
import { comparisonMeta, comparisonRows, comparisonSummary, isChangedDecision } from "./planComparison";

const initialPlan = {
  id: "SCN-002:PLAN-1",
  scenario_id: "SCN-002",
  version: 1,
  parent_plan_id: null,
  created_at: "2026-09-21T10:00:00Z",
  actions: [
    {
      id: "ACT-OBS-A-1",
      request_id: "OBS-A",
      satellite_id: "SAT-001",
      window_id: "WIN-OBS-A-1",
      start: "2026-09-21T10:10:00Z",
      end: "2026-09-21T10:20:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
    {
      id: "ACT-OBS-C-1",
      request_id: "OBS-C",
      satellite_id: "SAT-001",
      window_id: "WIN-OBS-C-1",
      start: "2026-09-21T12:00:00Z",
      end: "2026-09-21T12:10:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
  ],
  unscheduled: [{ request_id: "OBS-B", reason_code: "DEADLINE_VIOLATION" }],
  mission_utility: 8,
  violation_count: 1,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

const revisedPlan = {
  ...initialPlan,
  id: "SCN-002:PLAN-2",
  version: 2,
  parent_plan_id: initialPlan.id,
  actions: [
    {
      ...initialPlan.actions[0],
      id: "ACT-OBS-A-2",
      window_id: "WIN-OBS-A-2",
      start: "2026-09-21T11:00:00Z",
      end: "2026-09-21T11:10:00Z",
    },
    {
      id: "ACT-OBS-B-1",
      request_id: "OBS-B",
      satellite_id: "SAT-001",
      window_id: "WIN-OBS-B-1",
      start: "2026-09-21T13:00:00Z",
      end: "2026-09-21T13:10:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
  ],
  unscheduled: [{ request_id: "OBS-C", reason_code: "WINDOW_INVALIDATED" }],
  mission_utility: 9,
} satisfies MissionPlanSchema;

const diff = {
  from_plan_id: initialPlan.id,
  to_plan_id: revisedPlan.id,
  entries: [
    {
      request_id: "OBS-A",
      change_type: "MOVED",
      reason_code: "ALTERNATIVE_WINDOW_AVAILABLE",
      old_start: "2026-09-21T10:10:00Z",
      new_start: "2026-09-21T11:00:00Z",
    },
    {
      request_id: "OBS-B",
      change_type: "INSERTED",
      reason_code: "ALTERNATIVE_WINDOW_AVAILABLE",
      old_start: null,
      new_start: "2026-09-21T13:00:00Z",
    },
    {
      request_id: "OBS-C",
      change_type: "DROPPED",
      reason_code: "WINDOW_INVALIDATED",
      old_start: "2026-09-21T12:00:00Z",
      new_start: null,
    },
    {
      request_id: "OBS-D",
      change_type: "UNCHANGED",
      reason_code: "REQUEST_UNCHANGED",
      old_start: null,
      new_start: null,
    },
  ],
  metrics_before: null,
  metrics_after: null,
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

const traces = [
  {
    id: "TRACE-0001",
    plan_id: revisedPlan.id,
    event_id: "EVT-1",
    request_id: "OBS-A",
    reason_code: "ALTERNATIVE_WINDOW_AVAILABLE",
    previous_action: null,
    new_action: null,
    constraint_name: null,
    message: "OBS-A moved because an alternative window was available.",
    metadata: {},
  },
] satisfies DecisionTraceSchema[];

const result: ReplanResult = {
  initialPlan,
  revisedPlan,
  diff,
  traces,
};

describe("plan comparison model", () => {
  it("pairs each diff entry with old/new placements and its backend trace", () => {
    const rows = comparisonRows(result);
    const moved = rows.find((row) => row.requestId === "OBS-A");
    expect(moved?.changeType).toBe("MOVED");
    expect(moved?.oldStart).toBe("2026-09-21T10:10:00Z");
    expect(moved?.newStart).toBe("2026-09-21T11:00:00Z");
    expect(moved?.oldWindowId).toBe("WIN-OBS-A-1");
    expect(moved?.newWindowId).toBe("WIN-OBS-A-2");
    expect(moved?.trace?.id).toBe("TRACE-0001");
    expect(moved?.traceEventId).toBe("EVT-1");
    expect(moved?.reasonLabel).toBe("Alternative window available");
  });

  it("keeps dropped requests visible with their old placement and no new one", () => {
    const rows = comparisonRows(result);
    const dropped = rows.find((row) => row.requestId === "OBS-C");
    expect(dropped?.changeType).toBe("DROPPED");
    expect(dropped?.oldWindowId).toBe("WIN-OBS-C-1");
    expect(dropped?.newWindowId).toBeNull();
    expect(dropped?.newStart).toBeNull();
    expect(dropped?.trace).toBeNull();
  });

  it("sorts changed decisions before quiet entries", () => {
    const rows = comparisonRows(result);
    expect(rows.map((row) => row.requestId)).toEqual(["OBS-A", "OBS-B", "OBS-C", "OBS-D"]);
    expect(isChangedDecision("MOVED")).toBe(true);
    expect(isChangedDecision("UNCHANGED")).toBe(false);
    expect(isChangedDecision("COMPLETED")).toBe(false);
  });

  it("summarises changed, completed and unchanged rows separately", () => {
    expect(comparisonSummary(comparisonRows(result))).toEqual({
      changed: 3,
      completed: 0,
      unchanged: 1,
    });
  });

  it("names each backend status in the header, omitting absent ones", () => {
    expect(comparisonMeta({ changed: 2, completed: 0, unchanged: 1 })).toBe(
      "2 changed · 1 unchanged",
    );
    expect(comparisonMeta({ changed: 0, completed: 1, unchanged: 4 })).toBe(
      "0 changed · 1 completed · 4 unchanged",
    );
  });

  it("flags a request that arrived after the parent plan and stays unscheduled", () => {
    const arrived = {
      ...result,
      revisedPlan: {
        ...revisedPlan,
        unscheduled: [
          ...revisedPlan.unscheduled,
          { request_id: "OBS-EMERGENCY-1", reason_code: "NO_ALTERNATIVE_WINDOW" },
        ],
      },
      diff: {
        ...diff,
        entries: [
          ...diff.entries,
          {
            request_id: "OBS-EMERGENCY-1",
            change_type: "UNCHANGED",
            reason_code: "REQUEST_UNCHANGED",
            old_start: null,
            new_start: null,
          },
        ],
      },
    } satisfies ReplanResult;
    const row = comparisonRows(arrived).find((candidate) => candidate.requestId === "OBS-EMERGENCY-1");
    expect(row?.newlyArrivedUnscheduled).toBe(true);
    const moved = comparisonRows(arrived).find((candidate) => candidate.requestId === "OBS-A");
    expect(moved?.newlyArrivedUnscheduled).toBe(false);
  });
});
