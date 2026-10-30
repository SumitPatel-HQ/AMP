import { cleanup, fireEvent, render as testingRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MissionBar } from "./MissionBar";
// jsdom does not implement the browser's native dialog methods.
HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
const render = (ui: import("react").ReactNode) => {
  const view = testingRender(ui);
  fireEvent.click(screen.getByRole("button", { name: "Mission & settings" }));
  return view;
};
import type {
  MissionPlanSchema,
  MissionStateSchema,
  ScenarioSchema,
} from "../api/client";

const baseScenario: ScenarioSchema = {
  id: "SCN-TEST",
  name: "Test Mission",
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
  requests: [],
};

const baseMissionState: MissionStateSchema = {
  scenario_id: baseScenario.id,
  simulated_time: baseScenario.start_time,
  satellite_id: baseScenario.satellite.id,
  battery_wh: 500,
  storage_usage_mb: 0,
  available: true,
  active_event_ids: [],
  completed_request_ids: [],
  mission_complete: false,
};

const basePlan: MissionPlanSchema = {
  id: "SCN-TEST:PLAN-1",
  scenario_id: baseScenario.id,
  version: 1,
  parent_plan_id: null,
  created_at: baseScenario.start_time,
  actions: [],
  unscheduled: [],
  planner_name: "greedy",
  planning_policy: "utility",
  policy_version: "requester-utility-v1",
  mission_utility: 0,
  violation_count: 0,
  planning_time_ms: 0,
};

afterEach(() => {
  cleanup();
});

describe("MissionBar reset button", () => {
  it("renders with the expected title and is disabled when no scenario is loaded", () => {
    const onReset = vi.fn();
    render(
      <MissionBar
        scenario={null}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={null}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={onReset}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button).toBeTruthy();
    expect(button.disabled).toBe(true);
    expect(button.title).toBe(
      "Reset mission clock, plans, and events back to the initial scenario",
    );
  });

  it("is disabled when pristine (no plan, no events, clock at start)", () => {
    render(
      <MissionBar
        scenario={baseScenario}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("is disabled while loading even if reset would otherwise be enabled", () => {
    render(
      <MissionBar
        scenario={baseScenario}
        plan={basePlan}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[]}
        loading={true}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("is enabled when a plan exists", async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(
      <MissionBar
        scenario={baseScenario}
        plan={basePlan}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={onReset}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);

    await user.click(button);
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("is enabled when clock has stepped even without a plan", () => {
    render(
      <MissionBar
        scenario={baseScenario}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={{ ...baseMissionState, simulated_time: "2026-09-21T10:05:00Z" }}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("is enabled when events exist even without a plan", () => {
    render(
      <MissionBar
        scenario={baseScenario}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[
          {
            id: "EVT-1",
            scenario_id: baseScenario.id,
            event_time: baseScenario.start_time,
            event_type: "BATTERY_DROP",
            payload: { satellite_id: "SAT-001", new_battery_wh: 100 },
          },
        ]}
        loading={false}
        replanning={false}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Reset mission" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });
});


describe("MissionBar planner and policy controls", () => {
  it("renders planner and policy selects with correct options", async () => {
    render(
      <MissionBar
        scenario={baseScenario}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        planner="greedy"
        policy="utility"
        onPlannerChange={vi.fn()}
        onPolicyChange={vi.fn()}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const plannerSelect = screen.getByRole("combobox", { name: "Planner selection" }) as HTMLSelectElement;
    expect(plannerSelect.value).toBe("greedy");

    const policySelect = screen.getByRole("combobox", { name: "Planning policy" }) as HTMLSelectElement;
    expect(policySelect.value).toBe("utility");

    const fairnessOption = screen.getByRole("option", { name: "Utility-then-Fairness" }) as HTMLOptionElement;
    expect(fairnessOption.disabled).toBe(true);
  });

  it("enables Utility-then-Fairness when planner is cp_sat", async () => {
    const user = userEvent.setup();
    const onPlannerChange = vi.fn();
    const onPolicyChange = vi.fn();

    render(
      <MissionBar
        scenario={baseScenario}
        plan={null}
        previousVersion={null}
        awaitingReplan={false}
        missionState={baseMissionState}
        windows={[]}
        events={[]}
        loading={false}
        replanning={false}
        planner="cp_sat"
        policy="utility"
        onPlannerChange={onPlannerChange}
        onPolicyChange={onPolicyChange}
        onLoadDemo={vi.fn()}
        onNewMission={vi.fn()}
        onLoadMission={vi.fn()}
        onExamples={vi.fn()}
        onFeasibility={vi.fn()}
        onGeneratePlan={vi.fn()}
        onResetMission={vi.fn()}
        onStep={vi.fn()}
        onInjectEvent={vi.fn()}
        onReplan={vi.fn()}
      />,
    );

    const fairnessOption = screen.getByRole("option", { name: "Utility-then-Fairness" }) as HTMLOptionElement;
    expect(fairnessOption.disabled).toBe(false);

    const policySelect = screen.getByRole("combobox", { name: "Planning policy" });
    await user.selectOptions(policySelect, "utility_then_fairness");
    expect(onPolicyChange).toHaveBeenCalledWith("utility_then_fairness");

    const plannerSelect = screen.getByRole("combobox", { name: "Planner selection" });
    await user.selectOptions(plannerSelect, "greedy");
    expect(onPlannerChange).toHaveBeenCalledWith("greedy");
  });
});
