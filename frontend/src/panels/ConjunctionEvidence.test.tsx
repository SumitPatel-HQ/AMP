import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ImpactPanel } from "./ImpactPanel";
import type { MissionEventSchema } from "../api/client";
import { missionState, plan, scenario } from "../test/mapFixtures";
import { MissionNavPanel } from "./MissionNavPanel";
import { StatePanel } from "./StatePanel";
import { PlanComparisonPanel } from "./PlanComparisonPanel";

afterEach(cleanup);

const conjunctionEvent: MissionEventSchema = {
  id: "EVT-001", scenario_id: "SCN-001", event_type: "SATELLITE_UNAVAILABLE",
  event_time: "2026-09-21T10:00:00Z",
  payload: {
    satellite_id: "SAT-001", outage_start: "2026-09-21T10:20:00Z", outage_end: "2026-09-21T10:30:00Z",
    conjunction: {
      source: "synthetic training fixture", encounter_id: "synthetic-1", matched_norad_id: 39084,
      counterpart_norad_id: 99999, tca: "2026-09-21T10:25:00Z", miss_distance_km: 0.25,
      maximum_probability: 0.0002, threshold: 0.0001, policy_version: "socrates-outage-v1",
      pre_padding_s: 300, post_padding_s: 300,
    },
  },
};

it("shows recorded prediction, assumed interval and limitations with event impact", () => {
  render(<ImpactPanel impact={{ id: "IMP-001", event_id: "EVT-001", evaluated_plan_id: "PLAN-001",
    frozen_action_ids: [], valid_unfrozen_action_ids: [], invalid_unfrozen_action_ids: [], reason_codes: {} }}
    events={[conjunctionEvent]} plans={[]} earlier={false} selectedRequestId={null} onSelectRequest={() => {}} />);
  const details = screen.getByLabelText("Conjunction evidence");
  for (const value of ["99999", "0.25 km", "0.0002", "0.0001", "10:25:00", "10:20:00", "10:30:00",
    "synthetic training fixture", "socrates-outage-v1", "not modeled", "simulation policy"])
    expect(details.textContent).toContain(value);
});

it("shows selected event evidence and retains it across a plan transition", () => {
  const props = { scenario, plan, plans: [plan], replanResult: null, impact: null, missionState,
    windows: [], events: [conjunctionEvent], requestPool: scenario.requests,
    selection: { requestId: null, windowId: null, eventId: conjunctionEvent.id, planId: null },
    onSelectRequest: () => {}, onSelectWindow: () => {}, onSelectEvent: () => {}, onSelectPlan: () => {} };
  const view = render(<MissionNavPanel {...props} />);
  fireEvent.click(screen.getByRole("tab", { name: /Events/ }));
  expect(screen.getByLabelText("Conjunction evidence").textContent).toContain("99999");
  view.rerender(<MissionNavPanel {...props} plan={{ ...plan, version: 2 }} />);
  expect(screen.getByLabelText("Conjunction evidence").textContent).toContain("synthetic-1");
});

it("shows conjunction evidence for the inspected Satellite only", () => {
  const props = { state: { ...missionState, satellite_id: "SAT-001", active_event_ids: [conjunctionEvent.id] },
    events: [conjunctionEvent], plan, replanned: true, satelliteCapacityWh: 200, storageCapacityMb: 500, requestCount: 2 };
  const view = render(<StatePanel {...props} />);
  expect(screen.getByLabelText("Conjunction evidence").textContent).toContain("99999");
  view.rerender(<StatePanel {...props} state={{ ...props.state, satellite_id: "SAT-002" }} />);
  expect(screen.queryByLabelText("Conjunction evidence")).toBeNull();
});

it("renders every recorded encounter alongside the causal comparison trace", () => {
  const previous = plan.actions[0];
  const revisedPlan = { ...plan, id: "PLAN-002", parent_plan_id: plan.id, version: 2 };
  const result = {
    initialPlan: plan, revisedPlan,
    diff: { from_plan_id: plan.id, to_plan_id: revisedPlan.id, request_pool_mismatch: false, entries: [{ request_id: previous.request_id!,
      change_type: "MOVED" as const, reason_code: "COLLISION_AVOIDANCE_OUTAGE" as const,
      old_start: previous.start, new_start: "2026-09-21T11:00:00Z" }] },
    traces: [{ id: "TRACE-001", plan_id: revisedPlan.id, event_id: conjunctionEvent.id,
      request_id: previous.request_id!, reason_code: "COLLISION_AVOIDANCE_OUTAGE" as const,
      previous_action: previous, new_action: previous, constraint_name: "satellite_availability",
      message: "Moved because conjunction-derived unavailability blocked previous imaging.",
      metadata: { conjunction_events: [
        { event_id: conjunctionEvent.id, ...conjunctionEvent.payload },
        { event_id: "EVT-002", ...conjunctionEvent.payload, conjunction: {
          ...conjunctionEvent.payload.conjunction!, encounter_id: "synthetic-2", counterpart_norad_id: 88888 } },
      ] } }],
  };
  render(<PlanComparisonPanel replanResult={result} plans={[plan, revisedPlan]} selectedRequestId={null}
    onSelectRequest={() => {}} onSelectWindow={() => {}} />);
  const evidence = screen.getAllByLabelText("Conjunction evidence");
  expect(evidence).toHaveLength(2);
  expect(evidence[0].textContent).toContain("10:25:00");
  expect(evidence[0].textContent).toContain("0.0001");
  expect(evidence[1].textContent).toContain("88888");
  expect(evidence[1].textContent).toContain("synthetic training fixture");
});
