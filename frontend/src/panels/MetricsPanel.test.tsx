import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { MetricsSchema, MissionPlanSchema, PlanDiffSchema } from "../api/client";
import { MetricsPanel } from "./MetricsPanel";

const metricsBefore = {
  plan_id: "PLAN-1",
  mission_utility: 12,
  completion_rate: 0.4,
  violation_count: 0,
  planning_time_ms: 3.2,
  battery_utilisation: 0.1,
  storage_utilisation: 0.2,
  request_pool_size: 5,
  request_pool_ids: ["OBS-A", "OBS-B", "OBS-C", "OBS-D", "OBS-E"],
  measured_at: "2026-09-21T11:05:00Z",
  plan_churn: null,
  explanation_coverage: null,
  downlink_action_count: 0,
  downlink_volume_mb: 0,
  emergency_response: [],
  time_to_first_acquisition_s: null,
  achieved_time_to_first_acquisition_s: null,
  emergency_request_count: 0,
  planned_emergency_request_count: 0,
  achieved_emergency_request_count: 0,
} satisfies MetricsSchema;

const metricsAfter = {
  ...metricsBefore,
  plan_id: "PLAN-2",
  mission_utility: 14,
  completion_rate: 0.6,
  plan_churn: 0.25,
  explanation_coverage: 1.0,
  downlink_action_count: 0,
  downlink_volume_mb: 0,
  emergency_response: [],
  time_to_first_acquisition_s: null,
  achieved_time_to_first_acquisition_s: null,
  emergency_request_count: 0,
  planned_emergency_request_count: 0,
  achieved_emergency_request_count: 0,
} satisfies MetricsSchema;

const diff = {
  from_plan_id: "PLAN-1",
  to_plan_id: "PLAN-2",
  entries: [],
  metrics_before: metricsBefore,
  metrics_after: metricsAfter,
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

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

const plans = [plan("PLAN-1", 1), plan("PLAN-2", 2)];

function metricRow(label: string): HTMLElement {
  const row = screen.getByText(label).closest("tr");
  if (row === null) {
    throw new Error(`no row for ${label}`);
  }
  return row;
}

afterEach(cleanup);

describe("metrics panel", () => {
  it("asks for a plan before it can evaluate anything", () => {
    render(<MetricsPanel currentPlanId={null} metrics={null} diff={null} />);

    expect(screen.getByText("Generate a plan to evaluate it.")).toBeTruthy();
  });

  it("says the current plan is being evaluated, not that none exists, until its metrics arrive", () => {
    render(<MetricsPanel currentPlanId="PLAN-2" metrics={metricsBefore} diff={null} plans={plans} />);

    expect(screen.queryByText("Generate a plan to evaluate it.")).toBeNull();
    expect(screen.getByText("Evaluating V2…")).toBeTruthy();
  });

  it("evaluates the current plan on its own before any replan", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-1" metrics={metricsBefore} diff={null} plans={plans} />,
    );

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Metric", "V1"]);
    expect(metricRow("Mission utility").textContent).toContain("12");
    expect(metricRow("Plan churn").textContent).toContain("N/A");
  });

  it("names both plan versions and the change between them after a replan", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />,
    );

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Metric", "V1", "V2", "Δ"]);
    const utility = within(metricRow("Mission utility"));
    expect(utility.getByText("+2").getAttribute("data-trend")).toBe("better");
    expect(metricRow("Completion").textContent).toContain("40% of 5");
    expect(metricRow("Completion").textContent).toContain("60% of 5");
    expect(metricRow("Completion").textContent).toContain("+20 pp");
  });

  it("renders churn and coverage as not applicable when null, not as zero or a perfect score", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />,
    );

    const cells = within(metricRow("Plan churn")).getAllByRole("cell");
    expect(cells[1].textContent).toBe("N/A");
    expect(cells[2].textContent).toBe("25%");
    const coverage = within(metricRow("Explanation coverage")).getAllByRole("cell");
    expect(coverage[1].textContent).toBe("N/A");
    expect(coverage[2].textContent).toBe("100%");
  });

  it("reads battery and storage once, as mission state at the instant measured", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />,
    );

    const state = screen.getByLabelText("Mission state readings");
    expect(state.textContent).toContain("11:05 UTC");
    expect(state.textContent).toContain("battery used 10%");
    expect(state.textContent).toContain("storage used 20%");
    expect(screen.queryByText("Battery used")).toBeNull();
  });

  it("flags a comparison whose two sides used different request pools and names the difference", () => {
    const grown = {
      ...metricsAfter,
      request_pool_size: 6,
      request_pool_ids: [...metricsBefore.request_pool_ids, "OBS-EMERGENCY"],
    };
    render(
      <MetricsPanel
        currentPlanId="PLAN-2"
        metrics={grown}
        diff={{ ...diff, metrics_after: grown, request_pool_mismatch: true }}
        plans={plans}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("different request pools");
    expect(alert.textContent).toContain("OBS-EMERGENCY only in V2");
    expect(metricRow("Mission utility").textContent).toContain("pools differ");
  });

  it("raises no mismatch flag when the two sides agree", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />,
    );

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("drops the comparison once the current plan is not the one the replan produced", () => {
    const later = { ...metricsAfter, plan_id: "PLAN-3" };
    render(
      <MetricsPanel
        currentPlanId="PLAN-3"
        metrics={later}
        diff={diff}
        plans={[...plans, plan("PLAN-3", 3)]}
      />,
    );

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Metric", "V3"]);
  });

  it("shows planned and achieved response means separately with counts and per-request attribution", () => {
    const responding = {
      ...metricsBefore,
      time_to_first_acquisition_s: 2100,
      achieved_time_to_first_acquisition_s: null,
      emergency_request_count: 2,
      planned_emergency_request_count: 1,
      achieved_emergency_request_count: 0,
      emergency_response: [
        {
          request_id: "OBS-EMG",
          event_id: "EVT-001",
          arrival_time: "2026-09-21T10:05:00Z",
          request_status: "scheduled" as const,
          planned_start_time: "2026-09-21T10:40:00Z",
          planned_latency_s: 2100,
          planned_satellite_id: "SAT-001",
          achieved_start_time: null,
          achieved_latency_s: null,
          achieved_satellite_id: null,
        },
        {
          request_id: "OBS-LATE",
          event_id: "EVT-002",
          arrival_time: "2026-09-21T10:06:00Z",
          request_status: "expired" as const,
          planned_start_time: null,
          planned_latency_s: null,
          planned_satellite_id: null,
          achieved_start_time: null,
          achieved_latency_s: null,
          achieved_satellite_id: null,
        },
      ],
    } satisfies MetricsSchema;
    render(<MetricsPanel currentPlanId="PLAN-1" metrics={responding} diff={null} plans={plans} />);

    expect(metricRow("Planned response").textContent).toContain("35 min · 1 of 2 planned");
    expect(metricRow("Achieved response").textContent).toContain("N/A · 0 of 2 started");
    const list = screen.getByRole("region", { name: "Emergency response" });
    expect(list.textContent).toContain("imaging has started, not finished or downlinked");
    const items = within(list).getAllByRole("listitem");
    expect(items.map((item) => item.getAttribute("data-response-state"))).toEqual([
      "planned",
      "expired",
    ]);
    expect(items[0].textContent).toContain("V1 planned: 10:40 UTC on SAT-001 · 35 min");
    expect(items[0].textContent).toContain("Achieved: not started");
    expect(items[1].textContent).toContain("expired · no acquisition");
    expect(items[1].textContent).toContain("no planned acquisition");
  });

  it("omits the per-request list when no emergency arrived", () => {
    render(<MetricsPanel currentPlanId="PLAN-1" metrics={metricsBefore} diff={null} plans={plans} />);

    expect(screen.queryByRole("region", { name: "Emergency response" })).toBeNull();
    expect(metricRow("Planned response").textContent).toContain("N/A · 0 of 0 planned");
  });
});
