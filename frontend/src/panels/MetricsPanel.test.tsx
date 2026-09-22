import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { MetricsSchema, PlanDiffSchema } from "../api/client";
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
  plan_churn: null,
  explanation_coverage: null,
} satisfies MetricsSchema;

const metricsAfter = {
  ...metricsBefore,
  plan_id: "PLAN-2",
  completion_rate: 0.6,
  plan_churn: 0.25,
  explanation_coverage: 1.0,
} satisfies MetricsSchema;

const diff = {
  from_plan_id: "PLAN-1",
  to_plan_id: "PLAN-2",
  entries: [],
  metrics_before: metricsBefore,
  metrics_after: metricsAfter,
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

afterEach(cleanup);

describe("metrics panel", () => {
  it("asks for a replan before it can compare anything", () => {
    render(<MetricsPanel diff={null} />);

    expect(screen.getByText("Replan to compare plan metrics.")).toBeTruthy();
  });

  it("shows the request pool size beside completion rate, since that rate divides by it", () => {
    render(<MetricsPanel diff={diff} />);

    const row = screen.getByText("Completion rate").closest("tr");
    expect(row?.textContent).toContain("40% (of 5)");
    expect(row?.textContent).toContain("60% (of 5)");
  });

  it("renders churn and coverage as not applicable when null, not as zero or a perfect score", () => {
    render(<MetricsPanel diff={diff} />);

    const churnRow = screen.getByText("Plan churn").closest("tr");
    expect(churnRow?.textContent).toContain("N/A");
    expect(churnRow?.textContent).not.toContain("0%");

    const coverageRow = screen.getByText("Explanation coverage").closest("tr");
    expect(coverageRow?.textContent).toContain("N/A");
  });

  it("renders the after plan's churn and coverage as scores once they exist", () => {
    render(<MetricsPanel diff={diff} />);

    const churnRow = screen.getByText("Plan churn").closest("tr");
    expect(churnRow?.textContent).toContain("25%");

    const coverageRow = screen.getByText("Explanation coverage").closest("tr");
    expect(coverageRow?.textContent).toContain("100%");
  });

  it("flags a comparison whose two sides used different request pools", () => {
    render(<MetricsPanel diff={{ ...diff, request_pool_mismatch: true }} />);

    expect(screen.getByRole("alert").textContent).toContain("different request pools");
  });

  it("raises no mismatch flag when the two sides agree", () => {
    render(<MetricsPanel diff={diff} />);

    expect(screen.queryByRole("alert")).toBeNull();
  });
});
