import type { ReactElement } from "react";
import { Presentation } from "./panelPresentation";
import { cleanup, fireEvent, render as renderView, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MetricsSchema, MissionPlanSchema, PlanDiffSchema } from "../api/client";
import { MetricsPanel } from "./MetricsPanel";

// Existing detailed-content assertions exercise the dedicated details tab.
function render(element: ReactElement) {
 const result = renderView(element);
 const details = screen.queryByRole("tab", { name: /Detailed comparison|Details and methodology/ });
 if (details) {
   fireEvent.click(details);
 }
 return result;
}

const metricsBefore = {
  plan_id: "PLAN-1",
  mission_utility: 12,
  archive_satisfied_count: 0,
  archive_satisfied_utility: 0,
  total_fulfilled_count: 0,
  total_fulfilled_utility: 0,
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
  archive_satisfied_count: 0,
  archive_satisfied_utility: 0,
  total_fulfilled_count: 0,
  total_fulfilled_utility: 0,
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
    planning_policy: "utility",
    policy_version: "requester-utility-v1",
  };
}

const plans = [plan("PLAN-1", 1), plan("PLAN-2", 2)];

function metricRow(label: string): HTMLElement {
  const row = screen.getByRole("cell", { name: label }).closest("tr");
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

    const headers = screen.getAllByRole("columnheader").map(cell => cell.textContent);
    expect(headers).toEqual(["Metric", "V1"]);
    expect(metricRow("Mission utility").textContent).toContain("12");
    expect(metricRow("Plan churn").textContent).toContain("N/A");
  });

  it("names both plan versions and the change between them after a replan", () => {
    render(
      <MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />,
    );

    const headers = screen.getAllByRole("columnheader").map(cell => cell.textContent);
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
    expect(screen.getByLabelText("Battery used: 10%")).toBeTruthy();
    expect(screen.getByText("Battery used").closest("tr")).toBeNull();
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

    const headers = screen.getAllByRole("columnheader").map(cell => cell.textContent);
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


const requesterMetrics: MetricsSchema = {
  ...metricsBefore,
  requester_service: {
    requesters: [{ requester_id: "Agency", request_count: 2, demand_utility: 8,
      archive_satisfied_count: 0, archive_satisfied_utility: 0,
      served_request_count: 1, served_utility: 5, service_share: 0.5, fulfillment_ratio: 0.625 }],
    unattributed: { requester_id: null, request_count: 1, demand_utility: 5,
      archive_satisfied_count: 0, archive_satisfied_utility: 0,
      served_request_count: 1, served_utility: 5, service_share: 0.5, fulfillment_ratio: 1 },
    total_served_utility: 10, fairness_gap: null, no_service: false,
    zero_service_requester_count: 0, metric_version: "requester-utility-v1",
    scope: "Unattributed service is excluded from gap.",
    limitations: "Absolute utility is not normalized by demand, capability, or entitlement.",
    measured_at_convention: "Selected-plan membership with current completed work.",
  },
};

it("shows requester demand, shares, fulfillment, unattributed totals and scope together", () => {
  render(<MetricsPanel currentPlanId="PLAN-1" metrics={requesterMetrics} diff={null} />);
  const region = screen.getByRole("region", { name: "Requester service" });
  expect(region.textContent).toContain("10 total served priority units, including unattributed service");
  const row = within(region).getByRole("article", { name: "Agency" });
  expect(row.textContent).toContain("50%");
  expect(row.textContent).toContain("63%");
  expect(within(region).getByRole("article", { name: "Unattributed" })).toBeTruthy();
  expect(region.textContent).toContain("fewer than two requesters");
  expect(region.textContent).toContain("not normalized by demand");
  expect(region.textContent).toContain(requesterMetrics.measured_at);
});

it("shows zero service and null shares without implying equitable service", () => {
  const metrics: MetricsSchema = { ...requesterMetrics, requester_service: {
    ...requesterMetrics.requester_service!, total_served_utility: 0, fairness_gap: 0,
    no_service: true, zero_service_requester_count: 2,
    requesters: ["A", "B"].map(requester_id => ({ requester_id, request_count: 1,
      archive_satisfied_count: 0, archive_satisfied_utility: 0,
      demand_utility: 5, served_request_count: 0, served_utility: 0, service_share: null, fulfillment_ratio: 0 })),
    unattributed: { requester_id: null, request_count: 0, demand_utility: 0,
      archive_satisfied_count: 0, archive_satisfied_utility: 0,
      served_request_count: 0, served_utility: 0, service_share: null, fulfillment_ratio: null },
  }};
  render(<MetricsPanel currentPlanId="PLAN-1" metrics={metrics} diff={null} />);
  const region = screen.getByRole("region", { name: "Requester service" });
  expect(region.textContent).toContain("zero gap does not demonstrate equitable service");
  expect(region.textContent).toContain("2 identified requesters with zero service");
  expect(within(region).getAllByText("N/A").length).toBe(4);
});

it("shows requester archive credit in separate columns without changing acquisition cells", () => {
  const service = requesterMetrics.requester_service!;
  const metrics: MetricsSchema = { ...requesterMetrics, requester_service: {
    ...service, requesters: service.requesters.map(row => ({ ...row, archive_satisfied_count: 1, archive_satisfied_utility: 4 })),
  }};
  render(<MetricsPanel currentPlanId="PLAN-1" metrics={metrics} diff={null} />);
  const region = within(screen.getByRole("region", { name: "Requester service" }));
  const card = region.getByRole("article", { name: "Agency" });
  expect(card.textContent).toContain("1 requests · 4 utility");
  expect(card.textContent).toContain("5 / 8 demanded");
  expect(card.textContent).toContain("50%");
  expect(card.textContent).toContain("63%");
});

it("loads selected historical requester metrics and refreshes when live metrics change", async () => {
  const loadPlanMetrics = vi.fn().mockResolvedValue(requesterMetrics);
  const props = { currentPlanId: "PLAN-2", metrics: metricsAfter, diff, plans, selectedPlanId: "PLAN-1", loadPlanMetrics };
  const view = render(<MetricsPanel {...props} />);
  fireEvent.click(await screen.findByRole("tab", { name: /Details and methodology/ }));
  expect(await screen.findByRole("region", { name: "Requester service" })).toBeTruthy();
  expect(loadPlanMetrics).toHaveBeenCalledWith("PLAN-1");
  loadPlanMetrics.mockResolvedValue({ ...requesterMetrics, measured_at: "2026-09-21T11:10:00Z" });
  view.rerender(<MetricsPanel {...props} metrics={{ ...metricsAfter, measured_at: "2026-09-21T11:10:00Z" }} />);
  expect(await screen.findByText(/Measured at: 2026-09-21T11:10:00Z/)).toBeTruthy();
  view.rerender(<MetricsPanel {...props} selectedPlanId={null} />);
  expect(screen.queryByRole("region", { name: "Requester service" })).toBeNull();
});

it("surfaces active policy, solver status, achieved gap, and rebalancing details in RequesterService", () => {
  const fairPlan: MissionPlanSchema = {
    ...plan("PLAN-1", 1),
    planner_name: "cp_sat",
    planning_policy: "utility_then_fairness",
    policy_version: "requester-utility-v1",
    solver_details: {
      status: "OPTIMAL",
      achieved_gap: 0,
      achieved_gap_unit: "priority_utility",
      skip_reason: null,
      fallback_reason: null,
      fairness_rebalanced_request_ids: ["OBS-B1", "OBS-A2"],
    },
  };

  render(
    <MetricsPanel
      currentPlanId="PLAN-1"
      metrics={requesterMetrics}
      diff={null}
      plans={[fairPlan]}
    />,
  );

  const region = screen.getByRole("region", { name: "Requester service" });
  expect(region.textContent).toContain("Policy: Utility-then-Fairness");
  expect(region.textContent).toContain("CP-SAT");
  expect(region.textContent).toContain("Solver status: OPTIMAL");
  expect(region.textContent).toContain("Achieved gap: 0 priority units");
  expect(region.textContent).toContain("Fairness rebalanced requests (2): OBS-B1, OBS-A2");
});

it("does not claim primary optimality when a bounded solve falls back", () => {
  const boundedPlan: MissionPlanSchema = { ...plan("PLAN-1", 1),
    planner_name: "cp_sat", planning_policy: "utility_then_fairness",
    solver_details: { status: "UNKNOWN", skip_reason: "primary optimality unproven",
      fallback: true, fallback_reason: "solver_unknown", stages: [{ stage: "utility", status: "UNKNOWN" }] },
  };
  render(<MetricsPanel currentPlanId="PLAN-1" metrics={requesterMetrics} diff={null} plans={[boundedPlan]} />);
  const region = screen.getByRole("region", { name: "Requester service" });
  expect(region.textContent).toContain("primary optimality unproven");
  expect(region.textContent).not.toContain("Optimal primary utility plan retained");
  expect(region.textContent).not.toContain("Stage 1 optimal baseline");
});

it("keeps the compact inspector detailed without the expanded analytics", () => {
 render(<Presentation value={{ mode: "compact" }}><MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} /></Presentation>);
 expect(screen.queryByLabelText("Evaluation analytics")).toBeNull();
 expect(screen.getByLabelText("Mission Utility metric").textContent).toContain("14");
 expect(screen.getByLabelText("Archive and total fulfillment")).toBeTruthy();
});

it("switches between analytics and version comparison with keyboard navigation", () => {
 renderView(<MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />);
 const analytics = screen.getByRole("tab", { name: "Analytics" });
 const details = screen.getByRole("tab", { name: "Detailed comparison (V1 vs V2)" });
 expect(analytics.getAttribute("aria-selected")).toBe("true");
 expect(screen.queryByRole("columnheader", { name: "Metric" })).toBeNull();
 fireEvent.keyDown(analytics, { key: "ArrowRight" });
 expect(document.activeElement).toBe(details);
 expect(details.getAttribute("aria-selected")).toBe("true");
 expect(screen.getByRole("columnheader", { name: "Metric" })).toBeTruthy();
 fireEvent.click(analytics);
 expect(screen.queryByRole("columnheader", { name: "Metric" })).toBeNull();
 expect(screen.getByLabelText("Evaluation analytics").closest("[hidden]")).toBeNull();
});

it("shows detailed comparison sections directly without expand controls", () => {
 renderView(<MetricsPanel currentPlanId="PLAN-2" metrics={metricsAfter} diff={diff} plans={plans} />);
 fireEvent.click(screen.getByRole("tab", { name: "Detailed comparison (V1 vs V2)" }));
 const panel = screen.getByRole("tabpanel");
 expect(within(panel).getByLabelText("Mission utility comparison")).toBeTruthy();
 expect(within(panel).getByLabelText("Plan churn: 25%")).toBeTruthy();
 expect(within(panel).getByText("Measurement context & fulfillment notes").closest("details")).toBeTruthy();
 expect(within(panel).getByRole("heading", { name: "Requester service & fulfillment" })).toBeTruthy();
 expect(within(panel).getByRole("columnheader", { name: "Metric" })).toBeTruthy();
});

function compact(props: Partial<React.ComponentProps<typeof MetricsPanel>> = {}) {
 return renderView(<Presentation value={{ mode: "compact" }}><MetricsPanel currentPlanId="PLAN-1" metrics={metricsBefore} diff={null} plans={plans} {...props} /></Presentation>);
}
it("shows single-plan compact KPIs, exact resources and separate fulfillment", () => {
 compact({ metrics: { ...metricsBefore, battery_utilisation: 0.123456, archive_satisfied_count: 2, archive_satisfied_utility: 7, total_fulfilled_count: 4, total_fulfilled_utility: 19 } });
 expect(screen.queryByRole("table")).toBeNull();
 expect(screen.getByLabelText("Mission Utility metric").textContent).toContain("12");
 expect(screen.getByLabelText("Completion metric").textContent).toContain("40%");
 expect(screen.getByLabelText("Plan Churn metric").textContent).toContain("N/A");
 expect(screen.getByRole("progressbar", { name: "Battery used" }).getAttribute("aria-valuetext")).toBe("12.3456%");
 expect(screen.getByText("2 of 5")).toBeTruthy();
 expect(screen.getByText("4 requests · 19 utility")).toBeTruthy();
 expect(screen.getByText("2 requests · 7 utility")).toBeTruthy();
 expect(screen.queryByText(/Comparing/)).toBeNull();
});
it("preserves precise compact version comparisons and metric direction", () => {
 compact({ currentPlanId: "PLAN-2", diff: { ...diff, metrics_after: { ...metricsAfter, planning_time_ms: 2.75, violation_count: 1 } } });
 expect(screen.getByLabelText("Mission Utility metric").textContent).toContain("V1: 12 → V2: 14");
 expect(screen.getByLabelText("Mission Utility metric").textContent).toContain("Δ +2 priority units · improved");
 expect(screen.getByLabelText("Constraint Violations metric").textContent).toContain("degraded");
 expect(screen.getByLabelText("Planning Time metric").textContent).toContain("Δ -0.45 ms · improved");
 expect(screen.getByLabelText("Plan Churn metric").textContent).not.toContain("Δ");
});
it("does not judge pool-dependent compact changes across different pools", () => {
 compact({ currentPlanId: "PLAN-2", diff: { ...diff, request_pool_mismatch: true } });
 expect(screen.getByLabelText("Mission Utility metric").querySelector('[data-trend]')).toBeNull();
 expect(screen.getByLabelText("Mission Utility metric").textContent).toContain("not directly comparable");
});
it("keeps empty-pool completion N/A and zeros distinct from missing measurements", () => {
 compact({ metrics: { ...metricsBefore, request_pool_size: 0, request_pool_ids: [], completion_rate: 0, mission_utility: 0, battery_utilisation: 0, storage_utilisation: 0 } });
 expect(screen.getByLabelText("Completion metric").textContent).toContain("N/A");
 expect(screen.getByLabelText("Mission Utility metric").querySelector("strong")?.textContent).toBe("0");
 expect(screen.getByRole("progressbar", { name: "Storage used" }).getAttribute("value")).toBe("0");
 expect(screen.getByText("0 of 0")).toBeTruthy();
});
it("labels compact historical measurements and avoids the live comparison", async () => {
 const load = vi.fn().mockResolvedValue(metricsBefore);
 compact({ currentPlanId: "PLAN-2", metrics: metricsAfter, diff, selectedPlanId: "PLAN-1", loadPlanMetrics: load });
 expect(await screen.findByText("Historical plan · V1")).toBeTruthy();
 expect(screen.queryByText(/Comparing/)).toBeNull();
 expect(load).toHaveBeenCalledWith("PLAN-1");
});
it("exposes complete compact requester cards and methodology through disclosures", () => {
 compact({ metrics: requesterMetrics });
 const requester = screen.getByText("Requester Service", { selector: "summary" });
 expect(requester.closest("details")?.open).toBe(false);
 fireEvent.click(requester);
 const region = screen.getByRole("region", { name: "Requester service" });
 expect(within(region).getByRole("article", { name: "Agency" }).textContent).toContain("5 / 8 demanded");
 expect(region.textContent).toContain("fewer than two requesters");
 expect(region.textContent).toContain(requesterMetrics.requester_service!.limitations);
 fireEvent.click(screen.getByText("Metric Details & Methodology", { selector: "summary" }));
 expect(screen.getByText(/Only|Empty request pool|OBS-A, OBS-B/)).toBeTruthy();
 fireEvent.click(screen.getByText("Emergency Response", { selector: "summary" }));
 expect(screen.getByText("No emergency requests in this plan's pool.")).toBeTruthy();
});
it("handles a compact inspector with no plan", () => {
 compact({ currentPlanId: null, metrics: null });
 expect(screen.getByText("Generate a plan to evaluate it.")).toBeTruthy();
 expect(screen.queryByLabelText("Compact mission evaluation")).toBeNull();
});

it("keeps emergency attribution and solver evidence accessible in compact details", () => {
 const metrics: MetricsSchema = { ...requesterMetrics, emergency_request_count: 1, planned_emergency_request_count: 1, time_to_first_acquisition_s: 2100,
 emergency_response: [{ request_id: "OBS-EMG", event_id: "EVT-001", arrival_time: "2026-09-21T10:05:00Z", request_status: "scheduled", planned_start_time: "2026-09-21T10:40:00Z", planned_latency_s: 2100, planned_satellite_id: "SAT-001", achieved_start_time: null, achieved_latency_s: null, achieved_satellite_id: null }] };
 compact({ metrics, plans: [{ ...plans[0], planning_policy: "utility_then_fairness", solver_details: { status: "UNKNOWN", skip_reason: "primary optimality unproven", fallback_reason: "solver_unknown" } }] });
 fireEvent.click(screen.getByText("Emergency Response", { selector: "summary" }));
 const response = screen.getByRole("region", { name: "Emergency response" });
 expect(response.textContent).toContain("V1 planned: 10:40 UTC on SAT-001 · 35 min");
 expect(response.textContent).toContain("Achieved: not started");
 expect(within(response).getByRole("listitem").getAttribute("data-event-id")).toBe("EVT-001");
 fireEvent.click(screen.getByText("Requester Service", { selector: "summary" }));
 const requester = screen.getByRole("region", { name: "Requester service" });
 expect(requester.textContent).toContain("Solver status: UNKNOWN");
 expect(requester.textContent).toContain("primary optimality unproven");
 expect(requester.textContent).toContain("solver_unknown");
});

it("preserves the compact Expand action", () => {
 const expand = vi.fn();
 renderView(<Presentation value={{ mode: "compact", expand }}><MetricsPanel currentPlanId="PLAN-1" metrics={metricsBefore} diff={null} /></Presentation>);
 fireEvent.click(screen.getByRole("button", { name: "Expand panel" }));
 expect(expand).toHaveBeenCalledOnce();
});
