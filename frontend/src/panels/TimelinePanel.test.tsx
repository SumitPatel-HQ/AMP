import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  EmergencyResponseSchema,
  MetricsSchema,
  MissionPlanSchema,
  ScenarioSchema,
} from "../api/client";
import type { PlanTimelineProps } from "./PlanTimeline";
import { TimelinePanel } from "./TimelinePanel";

const timelineProps: PlanTimelineProps[] = [];

vi.mock("./PlanTimeline", () => ({
  PlanTimeline: (props: PlanTimelineProps) => {
    timelineProps.push(props);
    return null;
  },
}));

vi.mock("./StorageProfileChart", () => ({ StorageProfileChart: () => null }));

const scenario = {
  id: "SCN",
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
  requests: [],
} satisfies ScenarioSchema;

function plan(id: string, version: number): MissionPlanSchema {
  return {
    id,
    scenario_id: "SCN",
    version,
    parent_plan_id: null,
    created_at: "2026-09-21T10:00:00Z",
    actions: [],
    unscheduled: [],
    mission_utility: 0,
    violation_count: 0,
    planning_time_ms: 0,
    planner_name: "greedy",
  };
}

const row = {
  request_id: "OBS-EMG",
  event_id: "EVT-001",
  arrival_time: "2026-09-21T10:05:00Z",
  request_status: "scheduled",
  planned_start_time: "2026-09-21T10:40:00Z",
  planned_latency_s: 2100,
  planned_satellite_id: "SAT-1",
  achieved_start_time: null,
  achieved_latency_s: null,
  achieved_satellite_id: null,
} satisfies EmergencyResponseSchema;

function metrics(planId: string, rows: EmergencyResponseSchema[]): MetricsSchema {
  return {
    plan_id: planId,
    mission_utility: 0,
    completion_rate: 0,
    violation_count: 0,
    planning_time_ms: 0,
    battery_utilisation: 0,
    storage_utilisation: 0,
    request_pool_size: 0,
    request_pool_ids: [],
    measured_at: "2026-09-21T10:30:00Z",
    plan_churn: null,
    explanation_coverage: null,
    downlink_action_count: 0,
    downlink_volume_mb: 0,
    emergency_response: rows,
    emergency_request_count: rows.length,
    planned_emergency_request_count: 0,
    achieved_emergency_request_count: 0,
  };
}

const plans = [plan("PLAN-1", 1), plan("PLAN-2", 2)];

function renderPanel(selectedPlanId: string | null, loadPlanMetrics: (planId: string) => Promise<MetricsSchema>) {
  return render(
    <TimelinePanel
      scenario={scenario}
      plan={plans[1]}
      replanResult={null}
      missionState={null}
      windows={[]}
      events={[]}
      impact={null}
      metrics={metrics("PLAN-2", [row])}
      plans={plans}
      selectedPlanId={selectedPlanId}
      loadPlanMetrics={loadPlanMetrics}
      selectedRequestId={null}
      selectedWindowId={null}
      selectedEventId={null}
      onSelectRequest={() => {}}
      onSelectWindow={() => {}}
      onSelectEvent={() => {}}
    />,
  );
}

afterEach(() => {
  cleanup();
  timelineProps.length = 0;
});

describe("timeline panel emergency response", () => {
  it("draws the displayed plan's own response rows without fetching", () => {
    const load = vi.fn<(planId: string) => Promise<MetricsSchema>>();
    renderPanel(null, load);

    expect(load).not.toHaveBeenCalled();
    expect(timelineProps.at(-1)?.emergencyResponse).toEqual([row]);
    expect(timelineProps.at(-1)?.responsePlanLabel).toBeUndefined();
  });

  it("draws a selected historical plan's own backend rows, labelled with its version", async () => {
    const load = vi.fn(async (planId: string) => metrics(planId, []));
    renderPanel("PLAN-1", load);

    expect(load).toHaveBeenCalledWith("PLAN-1");
    // Until the historical metrics arrive nothing is borrowed from the current plan.
    expect(timelineProps[0].emergencyResponse).toEqual([]);
    await waitFor(() => expect(timelineProps.at(-1)?.responsePlanLabel).toBe("V1"));
    // The earlier plan's RequestPool excludes the later arrival.
    expect(timelineProps.at(-1)?.emergencyResponse).toEqual([]);
    expect(screen.getByText("V2 · emergency response for V1")).toBeTruthy();
  });
});
