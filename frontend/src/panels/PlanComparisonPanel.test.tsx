import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MissionPlanSchema, PlanDiffSchema } from "../api/client";
import type { ReplanResult } from "../state/types";
import { PlanComparisonPanel } from "./PlanComparisonPanel";

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
  ],
  unscheduled: [{ request_id: "OBS-C", reason_code: "WINDOW_INVALIDATED" }],
  mission_utility: 9,
} satisfies MissionPlanSchema;

const replanResult: ReplanResult = {
  initialPlan,
  revisedPlan,
  diff: {
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
        request_id: "OBS-C",
        change_type: "DROPPED",
        reason_code: "WINDOW_INVALIDATED",
        old_start: "2026-09-21T12:00:00Z",
        new_start: null,
      },
      {
        request_id: "OBS-B",
        change_type: "UNCHANGED",
        reason_code: "REQUEST_UNCHANGED",
        old_start: null,
        new_start: null,
      },
    ],
    metrics_before: null,
    metrics_after: null,
    request_pool_mismatch: false,
  } satisfies PlanDiffSchema,
  traces: [
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
  ],
};

const plans = [initialPlan, revisedPlan];

function renderComparison(overrides: Partial<Parameters<typeof PlanComparisonPanel>[0]> = {}) {
  const onSelectRequest = vi.fn();
  const onSelectWindow = vi.fn();
  const result = render(
    <PlanComparisonPanel
      replanResult={replanResult}
      plans={plans}
      selectedRequestId={null}
      onSelectRequest={onSelectRequest}
      onSelectWindow={onSelectWindow}
      {...overrides}
    />,
  );
  return { ...result, onSelectRequest, onSelectWindow };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("plan comparison panel", () => {
  it("asks for a replan before it can compare anything", () => {
    renderComparison({ replanResult: null });

    expect(
      screen.getByText(/Each changed request shows its previous placement/),
    ).toBeTruthy();
  });

  it("names the compared versions and the changed count", () => {
    renderComparison();

    expect(screen.getByRole("region", { name: "Plan comparison" }).textContent).toContain(
      "V1 → V2 · 2 changed · 1 unchanged",
    );
  });

  it("shows previous state, new state, classification and backend reason per changed request", () => {
    renderComparison();

    const list = screen.getByRole("list", { name: "Plan comparison" });
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(2);
    const moved = within(list).getByRole("button", { name: /OBS-A/ });
    expect(moved.getAttribute("data-change")).toBe("MOVED");
    expect(moved.textContent).toContain("2026-09-21 10:10 UTC");
    expect(moved.textContent).toContain("2026-09-21 11:00 UTC");
    expect(moved.textContent).toContain("WIN-OBS-A-1 → WIN-OBS-A-2");
    expect(moved.textContent).toContain("ALTERNATIVE_WINDOW_AVAILABLE");
    expect(moved.textContent).toContain("Alternative window available");
    expect(moved.textContent).toContain("OBS-A moved because an alternative window was available.");
    expect(moved.textContent).toContain("decision for EVT-1");
  });

  it("keeps dropped requests visible with no new placement", () => {
    renderComparison();

    const dropped = within(screen.getByRole("list", { name: "Plan comparison" })).getByRole(
      "button",
      { name: /OBS-C/ },
    );
    expect(dropped.getAttribute("data-change")).toBe("DROPPED");
    expect(dropped.textContent).toContain("WINDOW_INVALIDATED");
    expect(dropped.textContent).toContain("WIN-OBS-C-1");
  });

  it("keeps unchanged entries quieter in their own section", () => {
    renderComparison();

    const unchanged = within(
      screen.getByRole("list", { name: "Unchanged plan entries" }),
    ).getByRole("button", { name: /OBS-B/ });
    expect(unchanged.getAttribute("data-change")).toBe("UNCHANGED");
    expect(unchanged.textContent).toContain("Unchanged, so the backend recorded no decision trace.");
  });

  it("lists clock-completed requests once, under their own heading and header count", () => {
    renderComparison({
      replanResult: {
        ...replanResult,
        diff: {
          ...replanResult.diff,
          entries: [
            {
              request_id: "OBS-A",
              change_type: "COMPLETED",
              reason_code: "REQUEST_UNCHANGED",
              old_start: "2026-09-21T10:10:00Z",
              new_start: "2026-09-21T10:10:00Z",
            },
          ],
        },
        traces: [],
      },
    });

    expect(screen.getByRole("region", { name: "Plan comparison" }).textContent).toContain(
      "V1 → V2 · 0 changed · 1 completed · 0 unchanged",
    );
    const completed = within(
      screen.getByRole("list", { name: "Completed plan entries" }),
    ).getByRole("button", { name: /OBS-A/ });
    expect(completed.textContent?.match(/2026-09-21 10:10 UTC/g)).toHaveLength(1);
    expect(completed.textContent).toContain(
      "Completed by the mission clock, not a replan decision, so no trace.",
    );
  });

  it("selects request and focus window together, and clears on a second click", async () => {
    const user = userEvent.setup();
    const { onSelectRequest, onSelectWindow, rerender } = renderComparison();

    await user.click(screen.getByRole("button", { name: /OBS-A/ }));
    expect(onSelectRequest).toHaveBeenCalledWith("OBS-A");
    expect(onSelectWindow).toHaveBeenCalledWith("WIN-OBS-A-2");

    rerender(
      <PlanComparisonPanel
        replanResult={replanResult}
        plans={plans}
        selectedRequestId="OBS-A"
        onSelectRequest={onSelectRequest}
        onSelectWindow={onSelectWindow}
      />,
    );
    expect(screen.getByRole("button", { name: /OBS-A/ }).getAttribute("data-selected")).toBe(
      "true",
    );
    await user.click(screen.getByRole("button", { name: /OBS-A/ }));
    expect(onSelectRequest).toHaveBeenLastCalledWith(null);
  });

  it("follows the event named by a decision trace", async () => {
    const onSelectEvent = vi.fn();
    renderComparison({ onSelectEvent });

    await userEvent.setup().click(screen.getByRole("button", { name: "Follow event EVT-1" }));
    expect(onSelectEvent).toHaveBeenCalledWith("EVT-1");
  });
});
