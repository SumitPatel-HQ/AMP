import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { MetricsSchema } from "../api/client";
import { metricsView, type MetricsSubject } from "../state/metricsView";
import { EvaluationAnalytics } from "./EvaluationAnalytics";
afterEach(cleanup);
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


function show(subject: MetricsSubject, historical = false) {
 return render(<EvaluationAnalytics subject={subject} view={metricsView(subject)} label={id => id} historical={historical} />);
}
it("shows six KPIs and keeps zero and unavailable measurements distinct", () => {
 show({ before: null, after: { ...metricsBefore, request_pool_size: 0, mission_utility: 0 }, requestPoolMismatch: false });
 expect(screen.getAllByRole("region").filter(e => e.getAttribute("aria-label")?.endsWith("KPI"))).toHaveLength(6);
 expect(screen.getByLabelText(/Completed share: N\/A/)).toBeTruthy();
 expect(screen.getByLabelText("Constraint violations KPI").textContent).toContain("0");
 expect(screen.getByLabelText("Action churn KPI").textContent).toContain("N/A");
 expect(screen.getByText("Requester service data unavailable.")).toBeTruthy();
});
it("labels pool-dependent comparisons when request pools differ", () => {
 const subject = { before: { ...metricsBefore, plan_id: "OLD" }, after: metricsBefore, requestPoolMismatch: false };
 const result = show(subject);
 expect(screen.getByText(/common request pool/)).toBeTruthy();
 expect(screen.getByLabelText("Mission utility comparison")).toBeTruthy();
 result.unmount();
 show({ ...subject, requestPoolMismatch: true });
 expect(screen.queryByText(/common request pool/)).toBeNull();
 expect(screen.getByText(/Request pools differ/)).toBeTruthy();
});
it("labels historical context without borrowing a current-plan comparison", () => {
 show({ before: null, after: metricsBefore, requestPoolMismatch: false }, true);
 expect(screen.getAllByText(/Historical plan/).length).toBeGreaterThan(0);
 expect(within(screen.getByLabelText("Acquisition utility KPI")).getByText("12")).toBeTruthy();
 expect(screen.getByText(/Single-plan measurement/)).toBeTruthy();
});

it("shows exact version deltas and judges metric direction for later replans", () => {
 const before = { ...metricsBefore, plan_id: "V2", violation_count: 2 };
 const after = { ...metricsBefore, plan_id: "V3", mission_utility: 15, violation_count: 1, planning_time_ms: 4.2 };
 show({ before, after, requestPoolMismatch: false });
 const utility = screen.getByLabelText("Mission utility comparison");
 expect(utility.textContent).toContain("Delta +3 priority units");
 expect(utility.querySelector('[data-comparison-trend="improved"]')).toBeTruthy();
 const violations = screen.getByLabelText("Constraint violations comparison");
 expect(violations.textContent).toContain("Delta -1 violations");
 expect(violations.querySelector('[data-comparison-trend="improved"]')).toBeTruthy();
 expect(screen.getByLabelText("Planning time comparison").querySelector('[data-comparison-trend="degraded"]')).toBeTruthy();
 expect(screen.getByLabelText("Request completion comparison").querySelector('[data-comparison-trend="unchanged"]')).toBeTruthy();
});
it("preserves missing completion and emergency values without creating zero bars", () => {
 show({ before: { ...metricsBefore, request_pool_size: 0 }, after: { ...metricsBefore, plan_id: "V2", time_to_first_acquisition_s: 120 }, requestPoolMismatch: true });
 expect(screen.getByLabelText("Request completion comparison").textContent).toContain("Delta N/A");
 const response = screen.getByLabelText("Planned emergency response comparison");
 expect(response.textContent).toContain("PLAN-1: N/A");
 expect(response.textContent).toContain("120 s");
 expect(screen.queryByLabelText("Achieved emergency response comparison")).toBeNull();
 expect(screen.getByLabelText("Mission utility comparison").querySelector('[data-comparison-trend="improved"]')).toBeNull();
});
it("does not render comparison charts without a previous plan", () => {
 show({ before: null, after: metricsBefore, requestPoolMismatch: false }, true);
 expect(screen.queryByLabelText("Plan Comparison Performance")).toBeNull();
 expect(screen.queryByLabelText("Mission utility comparison")).toBeNull();
});

it("marks lower utility as degraded and shorter planning as improved", () => {
 show({ before: metricsBefore, after: { ...metricsBefore, plan_id: "V2", mission_utility: 9, planning_time_ms: 2.2, plan_churn: 0.25, explanation_coverage: 0.5 }, requestPoolMismatch: false });
 expect(screen.getByLabelText("Mission utility comparison").querySelector('[data-comparison-trend="degraded"]')).toBeTruthy();
 expect(screen.getByLabelText("Planning time comparison").textContent).toContain("Delta -1 ms");
 expect(screen.getByLabelText("Planning time comparison").querySelector('[data-comparison-trend="improved"]')).toBeTruthy();
 expect(screen.getByLabelText("Changed unfrozen actions: 25%")).toBeTruthy();
 expect(screen.getByLabelText("Changes with decision traces: 50%")).toBeTruthy();
});
it("detects different pool IDs even without the backend mismatch flag", () => {
 show({ before: metricsBefore, after: { ...metricsBefore, plan_id: "V2", request_pool_ids: ["OTHER"], mission_utility: 15 }, requestPoolMismatch: false });
 expect(screen.getByText(/Request pools differ/)).toBeTruthy();
 expect(screen.getByLabelText("Mission utility comparison").querySelector('[data-comparison-trend="unjudged"]')).toBeTruthy();
});
