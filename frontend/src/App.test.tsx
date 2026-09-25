import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { fakeMap } from "./test/fakeMapEngine";
import { ApiError } from "./api/amis";
import type {
  DecisionTraceSchema,
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  PlanDiffSchema,
  ScenarioSchema,
} from "./api/client";

const api = vi.hoisted(() => ({
  createPlan: vi.fn(),
  createScenario: vi.fn(),
  fetchDemoScenario: vi.fn(),
  fetchEvents: vi.fn(),
  fetchImpact: vi.fn(),
  fetchMetrics: vi.fn(),
  fetchPlan: vi.fn(),
  fetchRequests: vi.fn(),
  fetchState: vi.fn(),
  fetchTraces: vi.fn(),
  generateWindows: vi.fn(),
  comparePlans: vi.fn(),
  fetchWindows: vi.fn(),
  injectEvent: vi.fn(),
  replan: vi.fn(),
  stepSimulation: vi.fn(),
}));

vi.mock("./api/amis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api/amis")>()),
  ...api,
}));

const scenario = {
  id: "SCN-002",
  name: "Cloud block replanning demo",
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
  requests: [
    {
      id: "OBS-A",
      target_lat: 12.97,
      target_lon: 77.59,
      priority: 5,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
    {
      id: "OBS-B",
      target_lat: 28.61,
      target_lon: 77.21,
      priority: 4,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
    {
      id: "OBS-C",
      target_lat: 19.08,
      target_lon: 72.88,
      priority: 3,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
  ],
} satisfies ScenarioSchema;

const missionState = {
  scenario_id: scenario.id,
  simulated_time: scenario.start_time,
  satellite_id: scenario.satellite.id,
  battery_wh: 500,
  storage_usage_mb: 0,
  available: true,
  active_event_ids: [],
  completed_request_ids: [],
  mission_complete: false,
} satisfies MissionStateSchema;

const plan = {
  id: "SCN-002:PLAN-1",
  scenario_id: scenario.id,
  version: 1,
  parent_plan_id: null,
  created_at: scenario.start_time,
  actions: [
    {
      id: "ACT-OBS-A-1",
      request_id: "OBS-A",
      satellite_id: scenario.satellite.id,
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
      satellite_id: scenario.satellite.id,
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
  ...plan,
  id: "SCN-002:PLAN-2",
  version: 2,
  parent_plan_id: plan.id,
  actions: [
    { ...plan.actions[0], id: "ACT-OBS-A-2", start: "2026-09-21T11:00:00Z", end: "2026-09-21T11:10:00Z" },
    {
      id: "ACT-OBS-B-1",
      request_id: "OBS-B",
      satellite_id: scenario.satellite.id,
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

const planDiff = {
  from_plan_id: plan.id,
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
  ],
  metrics_before: {
    plan_id: plan.id,
    mission_utility: 8,
    completion_rate: 0,
    violation_count: 1,
    planning_time_ms: 1,
    battery_utilisation: 0,
    storage_utilisation: 0,
    request_pool_size: 3,
    request_pool_ids: ["OBS-A", "OBS-B", "OBS-C"],
    measured_at: "2026-09-21T10:00:00Z",
    plan_churn: null,
    explanation_coverage: null,
  },
  metrics_after: {
    plan_id: revisedPlan.id,
    mission_utility: 9,
    completion_rate: 0,
    violation_count: 1,
    planning_time_ms: 1,
    battery_utilisation: 0,
    storage_utilisation: 0,
    request_pool_size: 3,
    request_pool_ids: ["OBS-A", "OBS-B", "OBS-C"],
    measured_at: "2026-09-21T10:00:00Z",
    plan_churn: 2 / 3,
    explanation_coverage: 1,
  },
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

const traces = [
  {
    id: "TRACE-0001",
    plan_id: revisedPlan.id,
    event_id: null,
    request_id: "OBS-A",
    reason_code: "ALTERNATIVE_WINDOW_AVAILABLE",
    previous_action: null,
    new_action: null,
    constraint_name: null,
    message: "OBS-A moved from 2026-09-21 10:10 to 2026-09-21 11:00 because an alternative window was available.",
    metadata: {},
  },
] satisfies DecisionTraceSchema[];

const window_: ObservationWindowSchema = {
  id: "WIN-OBS-A-1",
  request_id: "OBS-A",
  satellite_id: scenario.satellite.id,
  start: "2026-09-21T10:10:00Z",
  end: "2026-09-21T10:20:00Z",
  valid: true,
  invalid_reason: null,
};

function installSuccessfulApi(): void {
  api.fetchDemoScenario.mockResolvedValue(scenario);
  api.createScenario.mockResolvedValue(scenario);
  api.fetchState.mockResolvedValue(missionState);
  api.fetchEvents.mockResolvedValue([]);
  api.generateWindows.mockResolvedValue([window_]);
  api.fetchWindows.mockResolvedValue([window_]);
  api.createPlan.mockResolvedValue(plan);
  api.fetchPlan.mockResolvedValue(plan);
  api.replan.mockResolvedValue(revisedPlan);
  api.comparePlans.mockResolvedValue(planDiff);
  api.fetchTraces.mockResolvedValue(traces);
  api.fetchRequests.mockResolvedValue(scenario.requests);
  api.fetchMetrics.mockImplementation(async (planId: string) =>
    planId === revisedPlan.id
      ? planDiff.metrics_after
      : { ...planDiff.metrics_before, plan_id: planId },
  );
}

async function loadDemoAndGeneratePlan(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
  await screen.findByText(scenario.name);
  await user.click(screen.getByRole("button", { name: "Generate plan" }));
  await screen.findByLabelText("Current plan V1");
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("mission dashboard", () => {
  it("loads the demo and draws a generated plan only after user actions", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);

    expect(api.fetchDemoScenario).toHaveBeenCalledTimes(0);
    expect(api.fetchState).toHaveBeenCalledTimes(0);
    expect(screen.getByText("No scenario loaded.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));

    expect(await screen.findByText(scenario.name)).toBeTruthy();
    expect(screen.getByText("500.0 Wh")).toBeTruthy();
    expect(api.fetchDemoScenario).toHaveBeenCalledTimes(1);
    expect(api.fetchState).toHaveBeenCalledTimes(1);
    expect(api.fetchEvents).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Generate plan" }));

    expect(await screen.findByLabelText("Current plan V1")).toBeTruthy();
    expect(
      screen.getByRole("group", {
        name: "Mission plan timeline of observation windows, scheduled actions, mission events, and mission time",
      }),
    ).toBeTruthy();
    await waitFor(() => expect(api.fetchState).toHaveBeenCalledTimes(2));
    expect(api.fetchEvents).toHaveBeenCalledTimes(2);
    expect(document.querySelector("svg[aria-label*='timeline']")).toBeNull();
  });

  it("disables Generate plan once a plan exists, so it cannot be clicked twice", async () => {
    // Regression for GAP-05: the button used to stay enabled after a
    // plan was generated, letting a second click reach the backend
    // (which used to accept it and silently duplicate plan history).
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
    await screen.findByText(scenario.name);
    expect(
      (screen.getByRole("button", { name: "Generate plan" }) as HTMLButtonElement).disabled,
    ).toBe(false);

    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    await screen.findByLabelText("Current plan V1");

    expect(
      (screen.getByRole("button", { name: "Generate plan" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(api.createPlan).toHaveBeenCalledTimes(1);
  });

  it("creates a clean scenario id for each demo session", async () => {
    installSuccessfulApi();
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000011",
    );
    const demoSessionId = `${scenario.id}-00000000-0000-4000-8000-000000000011`;
    api.createScenario.mockImplementation(async (createdScenario: ScenarioSchema) =>
      createdScenario,
    );
    api.fetchState.mockImplementation(async (scenarioId: string) => ({
      ...missionState,
      scenario_id: scenarioId,
    }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));

    expect(await screen.findByText(demoSessionId)).toBeTruthy();
    expect(api.createScenario).toHaveBeenCalledWith({
      ...scenario,
      id: demoSessionId,
    });
    expect(api.fetchState).toHaveBeenCalledWith(demoSessionId);
    expect(screen.queryByRole("button", { name: "Dismiss error" })).toBeNull();
  });

  it("clears the old mission state when a new scenario refresh fails", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    expect(screen.getByText("500.0 Wh")).toBeTruthy();

    api.fetchState.mockRejectedValueOnce(new Error("state unavailable"));
    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
    await screen.findByRole("alert");

    expect(screen.queryByText("500.0 Wh")).toBeNull();
    expect(screen.queryByLabelText("Current plan V1")).toBeNull();
    expect(screen.getByRole("region", { name: "Mission state" }).textContent).toContain("Load a scenario");
  });

  it("shows an API error message with its code", async () => {
    installSuccessfulApi();
    api.fetchDemoScenario.mockRejectedValue(
      new ApiError({
        error: {
          code: "RESOURCE_NOT_FOUND",
          message: "demo scenario is unavailable",
          details: {},
        },
      }),
    );
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));

    expect(await screen.findByText("RESOURCE_NOT_FOUND")).toBeTruthy();
    expect(screen.getByText(/demo scenario is unavailable/)).toBeTruthy();
  });

  it("steps the simulation, updates the state panel, and refreshes the timeline's action statuses", async () => {
    installSuccessfulApi();
    api.stepSimulation.mockResolvedValue({
      ...missionState,
      simulated_time: "2026-09-21T10:15:00Z",
      battery_wh: 490,
    } satisfies MissionStateSchema);
    api.fetchPlan.mockResolvedValue({
      ...plan,
      actions: [{ ...plan.actions[0], status: "started" }],
    } satisfies MissionPlanSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Step" }));

    expect(api.stepSimulation).toHaveBeenCalledWith(scenario.id, 300);
    expect(await screen.findByText("490.0 Wh")).toBeTruthy();
    expect(api.fetchPlan).toHaveBeenCalledWith(plan.id);
  });

  it("shows mission complete and disables actions that cannot run past the end", async () => {
    installSuccessfulApi();
    api.stepSimulation.mockResolvedValueOnce({
      ...missionState,
      simulated_time: scenario.end_time,
      mission_complete: true,
    } satisfies MissionStateSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Event" }));
    expect(screen.getByRole("dialog", { name: "Configure event" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Step" }));
    expect(await screen.findByText("Mission complete.")).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: "Configure event" })).toBeNull();

    for (const name of ["Step", "Event", "Replan"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(api.stepSimulation).toHaveBeenCalledTimes(1);
  });

  it("injects a cloud block chosen from request and window dropdowns and shows the impact, without replanning", async () => {
    installSuccessfulApi();
    api.injectEvent.mockResolvedValue({
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: [],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      reason_codes: { "ACT-OBS-A-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    // The backend, not the client, marks the blocked window invalid.
    api.fetchWindows.mockResolvedValue([
      { ...window_, valid: false, invalid_reason: "WINDOW_INVALIDATED" },
    ]);

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));

    expect(api.injectEvent).toHaveBeenCalledWith(scenario.id, {
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    });
    const impactRow = within(await screen.findByRole("list", { name: "Event impact" })).getByText(
      "OBS-A",
    ).closest("li");
    expect(impactRow?.getAttribute("data-impact")).toBe("invalid");
    expect(impactRow?.textContent).toContain("WINDOW_INVALIDATED");
    expect(screen.getByLabelText("Current plan V1")).toBeTruthy();
    expect(api.createPlan).toHaveBeenCalledTimes(1);
    expect(api.fetchWindows).toHaveBeenCalledWith(scenario.id);
    // The dialog closes once the backend accepts the event.
    expect(screen.queryByRole("dialog", { name: "Configure event" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    expect(
      (screen.getByRole("option", { name: /WIN-OBS-A-1/ }) as HTMLOptionElement).textContent,
    ).toContain("invalid · WINDOW_INVALIDATED");
  });
  it("replans against the displayed version and keeps one current mission timeline", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));

    expect(await screen.findByLabelText("Current plan V2")).toBeTruthy();
    expect(api.replan).toHaveBeenCalledWith(scenario.id, plan.id);
    expect(api.comparePlans).toHaveBeenCalledWith(plan.id, revisedPlan.id);

    const timelines = Array.from(container.querySelectorAll(".amis-vis-timeline[aria-label]")).map(
      (timeline) => timeline.getAttribute("aria-label"),
    );
    expect(timelines).toEqual([
      "Mission plan timeline of observation windows, scheduled actions, mission events, and mission time",
    ]);
  });

  it("sends the newest plan version on a second replan", async () => {
    installSuccessfulApi();
    const thirdPlan = { ...revisedPlan, id: "SCN-002:PLAN-3", version: 3, parent_plan_id: revisedPlan.id };
    api.replan.mockResolvedValueOnce(revisedPlan).mockResolvedValueOnce(thirdPlan);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");
    await waitFor(() => expect((screen.getByRole("button", { name: "Step" }) as HTMLButtonElement).disabled).toBe(false));
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V3");

    expect(api.replan).toHaveBeenNthCalledWith(1, scenario.id, plan.id);
    expect(api.replan).toHaveBeenNthCalledWith(2, scenario.id, revisedPlan.id);
    await user.click(screen.getByRole("tab", { name: /Plans/ }));
    const history = screen.getByRole("list", { name: "Mission plans" });
    for (const version of ["V1", "V2", "V3"]) {
      expect(within(history).getByRole("button", { name: new RegExp(version) })).toBeTruthy();
    }
    await user.click(within(history).getByRole("button", { name: /V1/ }));
    const focus = screen.getByRole("status", { name: "Mission focus" });
    expect(focus.textContent).toContain("Selected V1");
    expect(focus.textContent).toContain("Timeline shows current V3");
  });

  it("lists the current plan's unscheduled request and never draws it on the timeline", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const currentEntries = within(
      screen.getByRole("list", { name: "Mission plan unscheduled requests" }),
    ).getAllByRole("listitem");
    expect(currentEntries).toHaveLength(1);
    expect(currentEntries[0].textContent).toContain(
      "OBS-C · priority 3 · WINDOW_INVALIDATED",
    );

    const timeline = container.querySelector('[aria-label="Mission plan"]') as HTMLElement;
    expect(timeline.querySelector('.vis-item.amis-action [data-request-id="OBS-C"]')).toBeNull();
  });

  it("shows a plan version conflict, refreshes to the backend's current plan, and replans against it next", async () => {
    installSuccessfulApi();
    const serverPlan = {
      ...revisedPlan,
      id: "SCN-002:PLAN-9",
      version: 9,
      parent_plan_id: "SCN-002:PLAN-8",
    } satisfies MissionPlanSchema;
    api.replan.mockRejectedValueOnce(
      new ApiError({
        error: {
          code: "PLAN_VERSION_CONFLICT",
          message: "replan named a plan version that is no longer current",
          details: { expected_parent_plan_id: plan.id, current_plan_id: serverPlan.id },
        },
      }),
    );
    api.fetchPlan.mockImplementation(async (planId: string) =>
      planId === serverPlan.id ? serverPlan : plan,
    );
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));

    expect(await screen.findByText("PLAN_VERSION_CONFLICT")).toBeTruthy();
    // One notice for one conflict: no generic error banner beside it.
    expect(screen.queryByRole("alert")).toBeNull();
    // No silent retry: one replan call, then the plan context refreshes.
    expect(api.replan).toHaveBeenCalledTimes(1);
    expect(await screen.findByLabelText("Current plan V9")).toBeTruthy();
    expect(api.fetchWindows).toHaveBeenCalledWith(scenario.id);
    expect(api.fetchImpact).toHaveBeenCalledWith(scenario.id);
    const stale = screen.getByRole("status", { name: "Stale plan" });
    expect(stale.textContent).toContain("replan named a plan version that is no longer current");
    expect(stale.textContent).toContain("PLAN-1");
    expect(stale.textContent).toContain("PLAN-9");
    expect(stale.textContent).toContain("refreshed to V9");
    expect(api.comparePlans).not.toHaveBeenCalled();

    api.replan.mockResolvedValueOnce({ ...serverPlan, id: "SCN-002:PLAN-10", version: 10, parent_plan_id: serverPlan.id });
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V10");
    expect(api.replan).toHaveBeenLastCalledWith(scenario.id, serverPlan.id);
    expect(screen.queryByRole("status", { name: "Stale plan" })).toBeNull();
  });
  it("keeps the revised timeline current when the clock moves after a replan", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const steppedState = {
      ...missionState,
      simulated_time: "2026-09-21T11:05:00Z",
    } satisfies MissionStateSchema;
    api.stepSimulation.mockResolvedValue(steppedState);
    api.fetchState.mockResolvedValue(steppedState);
    api.fetchPlan.mockResolvedValue({
      ...revisedPlan,
      actions: [
        { ...revisedPlan.actions[0], status: "started" },
        revisedPlan.actions[1],
      ],
    } satisfies MissionPlanSchema);

    await waitFor(() => expect((screen.getByRole("button", { name: "Step" }) as HTMLButtonElement).disabled).toBe(false));
    await user.click(screen.getByRole("button", { name: "Step" }));

    expect(await screen.findByText("2026-09-21 11:05:00 UTC")).toBeTruthy();
    expect(api.fetchPlan).toHaveBeenCalledWith(revisedPlan.id);
    await waitFor(() => expect(api.comparePlans).toHaveBeenCalledTimes(2));
  });
  it("marks the request the replan dropped in the revised unscheduled list", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const timeline = container.querySelector('[aria-label="Mission plan"]') as HTMLElement;
    const dropped = timeline.querySelector('li[data-request-id="OBS-C"]');
    expect(dropped?.getAttribute("data-change")).toBe("DROPPED");
    expect(dropped?.textContent).toContain("DROPPED");
  });

  it("compares the two plan versions' metrics side by side after a replan", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    // Before any replan the current plan is evaluated on its own.
    const evaluation = () => screen.getByRole("region", { name: "Mission evaluation" });
    expect(api.fetchMetrics).toHaveBeenCalledWith(plan.id);
    expect(within(evaluation()).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "Metric",
      "V1",
    ]);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    expect(within(evaluation()).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "Metric",
      "V1",
      "V2",
      "Δ",
    ]);
    const churnRow = screen.getByText("Plan churn").closest("tr");
    expect(churnRow?.textContent).toContain("N/A");
    expect(churnRow?.textContent).toContain("67%");
  });

  it("compares the two plan versions after a replan, with placement, classification and backend reason", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    expect(
      screen.getByText(/Each changed request shows its previous placement/),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const entry = within(screen.getByRole("list", { name: "Plan comparison" })).getByRole(
      "button",
      { name: /OBS-A/ },
    );
    expect(entry.getAttribute("data-change")).toBe("MOVED");
    expect(entry.textContent).toContain("2026-09-21 10:10 UTC");
    expect(entry.textContent).toContain("2026-09-21 11:00 UTC");
    expect(entry.textContent).toContain("WIN-OBS-A-1");
    expect(entry.textContent).toContain("ALTERNATIVE_WINDOW_AVAILABLE");
    expect(entry.textContent).toContain(traces[0].message);

    const dropped = within(screen.getByRole("list", { name: "Plan comparison" })).getByRole(
      "button",
      { name: /OBS-C/ },
    );
    expect(dropped.getAttribute("data-change")).toBe("DROPPED");
    expect(dropped.textContent).toContain("WINDOW_INVALIDATED");
  });

  it("highlights the matching request on the mission timeline when a comparison row is clicked", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    await user.click(
      within(screen.getByRole("list", { name: "Plan comparison" })).getByRole("button", {
        name: /OBS-A/,
      }),
    );

    const timeline = container.querySelector('[aria-label="Mission plan"]') as HTMLElement;
    expect(
      timeline
        .querySelector('.amis-timeline-group-button[data-request-id="OBS-A"]')
        ?.getAttribute("data-selected"),
    ).toBe("true");
  });

  it("keeps the selected mission request through replanning", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const requestList = screen.getByRole("list", { name: "Observation requests" });
    await user.click(within(requestList).getByRole("button", { name: /^OBS-A/ }));
    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");
    expect(screen.getByRole("status", { name: "Mission focus" }).textContent).toContain("OBS-A");
  });

  it("toggles a timeline action with Enter and Space", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);
    const action = () => container.querySelector<HTMLElement>('.vis-item[data-kind="action"][data-window-id="WIN-OBS-A-1"]');
    await waitFor(() => expect(action()).not.toBeNull());

    action()?.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(action()?.dataset.selected).toBe("true"));
    expect(document.activeElement).toBe(action());
    await user.keyboard(" ");
    await waitFor(() => expect(action()?.dataset.selected).toBe("false"));
  });

  it("refreshes the metrics panel's battery and storage figures after a step, since they read live mission state", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const readings = () => screen.getByLabelText("Mission state readings").textContent;
    expect(readings()).toContain("battery used 0%");

    api.comparePlans.mockResolvedValueOnce({
      ...planDiff,
      metrics_after: {
        ...planDiff.metrics_after!,
        battery_utilisation: 0.5,
        measured_at: "2026-09-21T11:05:00Z",
      },
    } satisfies PlanDiffSchema);
    api.stepSimulation.mockResolvedValue({
      ...missionState,
      simulated_time: "2026-09-21T11:05:00Z",
      battery_wh: 250,
    } satisfies MissionStateSchema);
    api.fetchPlan.mockResolvedValue(revisedPlan);

    await user.click(screen.getByRole("button", { name: "Step" }));

    await waitFor(() => expect(readings()).toContain("battery used 50%"));
    expect(readings()).toContain("11:05 UTC");
  });

  it("still evaluates the revised plan when the replan's comparison cannot be fetched", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    api.comparePlans.mockRejectedValueOnce(new Error("comparison unavailable"));
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const evaluation = screen.getByRole("region", { name: "Mission evaluation" });
    await waitFor(() =>
      expect(
        within(evaluation).getAllByRole("columnheader").map((cell) => cell.textContent),
      ).toEqual(["Metric", "V2"]),
    );
    expect(api.fetchMetrics).toHaveBeenCalledWith(revisedPlan.id);
  });

  it("pauses mission mutations and retries current-plan recovery after a stale conflict", async () => {
    installSuccessfulApi();
    api.replan.mockRejectedValueOnce(new ApiError({
      error: { code: "PLAN_VERSION_CONFLICT", message: "stale plan", details: { current_plan_id: "SCN-002:PLAN-9" } },
    }));
    api.fetchPlan.mockRejectedValueOnce(new Error("plan unavailable")).mockResolvedValueOnce({
      ...revisedPlan,
      id: "SCN-002:PLAN-9",
      version: 9,
    });
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByRole("status", { name: "Stale plan" });
    for (const name of ["Step", "Event", "Replan"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    await user.click(screen.getByRole("button", { name: "Retry loading current plan" }));
    expect(await screen.findByLabelText("Current plan V9")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Replan" }) as HTMLButtonElement).disabled).toBe(false);
    expect(api.replan).toHaveBeenCalledTimes(1);
  });

  it("can retry the comparison after the revised plan was saved", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    api.comparePlans.mockRejectedValueOnce(new Error("comparison unavailable"));
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    await user.click(await screen.findByRole("button", { name: "Retry comparison" }));
    expect(await screen.findByRole("list", { name: "Plan comparison" })).toBeTruthy();
  });

  it("retries failed post-replan mission context together with the comparison", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    api.fetchMetrics.mockRejectedValueOnce(new Error("metrics unavailable"));
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");
    expect(screen.getByText("Evaluating V2…")).toBeTruthy();

    await user.click(await screen.findByRole("button", { name: "Retry comparison" }));
    expect(await screen.findByRole("list", { name: "Plan comparison" })).toBeTruthy();
    expect(
      within(screen.getByRole("region", { name: "Mission evaluation" }))
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent),
    ).toEqual(["Metric", "V1", "V2", "Δ"]);
    expect(api.fetchMetrics).toHaveBeenCalledTimes(3);
  });

  it("marks a request the backend expired, which the immutable scenario never reports", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    api.stepSimulation.mockResolvedValue({
      ...missionState,
      simulated_time: "2026-09-21T14:00:00Z",
    } satisfies MissionStateSchema);
    api.fetchRequests.mockResolvedValue(
      scenario.requests.map((request) =>
        request.id === "OBS-B" ? { ...request, status: "expired" as const } : request,
      ),
    );
    await user.click(screen.getByRole("button", { name: "Step" }));

    const requestList = screen.getByRole("list", { name: "Observation requests" });
    await waitFor(() =>
      expect(
        within(requestList).getByRole("button", { name: /^OBS-B/ }).getAttribute("data-plan-status"),
      ).toBe("expired"),
    );
  });

  it("keeps mission identity, time, status and every lifecycle action in the mission bar", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const bar = screen.getByRole("banner");
    expect(within(bar).getByText(scenario.name)).toBeTruthy();
    expect(within(bar).getByText("2026-09-21 10:00:00 UTC")).toBeTruthy();
    expect(within(bar).getByText("T+00:00:00 / 04:00:00")).toBeTruthy();
    expect(within(bar).getByText("In progress")).toBeTruthy();
    for (const name of ["Step", "Event", "Replan"]) {
      expect(within(bar).getByRole("button", { name })).toBeTruthy();
    }
  });

  it("lists each request with the status the current plan gives it", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const rows = within(screen.getByRole("list", { name: "Observation requests" })).getAllByRole(
      "button",
    );
    expect(rows.map((row) => row.getAttribute("data-plan-status"))).toEqual([
      "planned",
      "unscheduled",
      "planned",
    ]);
    expect(rows[1].textContent).toContain("DEADLINE_VIOLATION");
  });

  it("highlights a request on the map and timeline when it is picked from the request list", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    const list = screen.getByRole("list", { name: "Observation requests" });
    await user.click(within(list).getByRole("button", { name: /^OBS-A/ }));

    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");
    expect(
      container
        .querySelector('.amis-timeline-group-button[data-request-id="OBS-A"]')
        ?.getAttribute("data-selected"),
    ).toBe("true");
  });

  it("selects a window's request along with the window, and marks the window the plan uses", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("tab", { name: /Windows/ }));
    const row = within(screen.getByRole("list", { name: "Observation windows" })).getByRole(
      "button",
      { name: /WIN-OBS-A-1/ },
    );
    expect(row.textContent).toContain("in plan");
    await user.click(row);

    expect(row.getAttribute("data-selected")).toBe("true");
    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");
  });

  it("lets the timeline select a window with the keyboard through shared selection", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const timeline = screen.getByRole("group", {
      name: "Mission plan timeline of observation windows, scheduled actions, mission events, and mission time",
    });
    const timelineWindow = document.createElement("div");
    timelineWindow.className = "vis-item";
    timelineWindow.dataset.kind = "window";
    timelineWindow.dataset.windowId = "WIN-OBS-A-1";
    timelineWindow.tabIndex = 0;
    timelineWindow.setAttribute("role", "button");
    timeline.append(timelineWindow);
    timelineWindow.focus();
    await user.keyboard("{Enter}");

    await user.click(screen.getByRole("tab", { name: /Windows/ }));
    const row = within(screen.getByRole("list", { name: "Observation windows" })).getByRole(
      "button",
      { name: /WIN-OBS-A-1/ },
    );
    expect(row.getAttribute("data-selected")).toBe("true");
    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");
  });

  it("lists both plan versions after a replan and marks the revised one current", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    await user.click(screen.getByRole("tab", { name: /Plans/ }));
    const rows = within(screen.getByRole("list", { name: "Mission plans" })).getAllByRole(
      "button",
    );
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain(plan.id);
    expect(rows[1].textContent).toContain(revisedPlan.id);
    expect(rows[1].textContent).toContain("current");
    expect(rows[0].textContent).not.toContain("current");
  });

  it("lists injected events with their payload and whether they are active", async () => {
    installSuccessfulApi();
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema;
    api.fetchEvents.mockResolvedValue([event]);
    api.fetchState.mockResolvedValue({ ...missionState, active_event_ids: ["EVT-1"] });
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("tab", { name: /Events/ }));
    const row = within(screen.getByRole("list", { name: "Mission events" })).getByRole(
      "button",
      { name: /EVT-1/ },
    );
    expect(row.textContent).toContain("CLOUD_BLOCK");
    expect(row.textContent).toContain("WIN-OBS-A-1");
    expect(row.textContent).toContain("active");
    await user.click(row);
    expect(row.getAttribute("data-selected")).toBe("true");
  });

  it("marks a request completed from live mission state and says so before any plan exists", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
    await screen.findByText(scenario.name);
    expect(within(screen.getByRole("banner")).getByText("No plan")).toBeTruthy();

    api.fetchState.mockResolvedValue({ ...missionState, completed_request_ids: ["OBS-A"] });
    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    await screen.findByLabelText("Current plan V1");

    const rows = within(screen.getByRole("list", { name: "Observation requests" })).getAllByRole(
      "button",
    );
    expect(rows[0].textContent).toContain("completed");
    expect(rows[1].textContent).not.toContain("completed");
  });
  it("says completed once for a request both the clock and its plan report completed", async () => {
    installSuccessfulApi();
    api.createPlan.mockResolvedValue({
      ...plan,
      actions: [{ ...plan.actions[0], status: "completed" }, plan.actions[1]],
    } satisfies MissionPlanSchema);
    api.fetchState.mockResolvedValue({ ...missionState, completed_request_ids: ["OBS-A"] });
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const row = within(screen.getByRole("list", { name: "Observation requests" })).getAllByRole(
      "button",
    )[0];
    expect(row.textContent?.match(/completed/g)).toHaveLength(1);
  });

  it("summarises the mission transition from plan through event and impact to the revised plan", async () => {
    installSuccessfulApi();
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: "2026-09-21T10:05:00Z",
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema;
    api.injectEvent.mockResolvedValue(event);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: ["ACT-OBS-C-1"],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      reason_codes: { "ACT-OBS-A-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    const summary = () => screen.getByRole("region", { name: "Mission transition" });
    expect(summary().textContent).toContain("Plan V1");
    expect(summary().textContent).toContain("2 / 3 scheduled");
    expect(summary().textContent).not.toContain("CLOUD_BLOCK");

    api.fetchEvents.mockResolvedValue([event]);
    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));

    await waitFor(() => expect(summary().textContent).toContain("Awaiting replan"));
    expect(summary().textContent).toContain("CLOUD_BLOCK · EVT-1");
    expect(summary().textContent).toContain("OBS-A / WIN-OBS-A-1");
    expect(summary().textContent).toContain("1 scheduled action invalid");

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    expect(summary().textContent).not.toContain("Awaiting replan");
    const plans = within(summary()).getAllByRole("listitem", { name: /^Plan V/ });
    expect(plans.map((item) => item.getAttribute("aria-label"))).toEqual([
      "Plan V1 (previous)",
      "Plan V2 (current)",
    ]);
  });

  it("labels impact, trace and evaluation with the plan versions they describe", async () => {
    installSuccessfulApi();
    api.injectEvent.mockResolvedValue({
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: ["ACT-OBS-C-1"],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      reason_codes: { "ACT-OBS-A-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));
    await screen.findByRole("list", { name: "Event impact" });

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const section = (name: string) => screen.getByRole("region", { name });
    expect(section("Impact").textContent).toContain("EVT-1 on V1");
    expect(section("Plan comparison").textContent).toContain("V1 → V2");
    expect(section("Mission evaluation").textContent).toContain("V1 → V2");
    // Impact actions belong to the plan the event evaluated, not the revised one.
    const impactRow = within(section("Impact")).getByText("OBS-A").closest("li");
    expect(impactRow?.textContent).toContain("WINDOW_INVALIDATED");
  });
  it("flags an impact from an earlier transition once a second replan has moved past it", async () => {
    installSuccessfulApi();
    const thirdPlan = { ...revisedPlan, id: "SCN-002:PLAN-3", version: 3, parent_plan_id: revisedPlan.id };
    api.replan.mockResolvedValueOnce(revisedPlan).mockResolvedValueOnce(thirdPlan);
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema;
    api.injectEvent.mockResolvedValue(event);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: [],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      reason_codes: { "ACT-OBS-A-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    api.fetchEvents.mockResolvedValue([event]);
    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));
    await screen.findByRole("list", { name: "Event impact" });

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");
    expect(screen.getByRole("region", { name: "Impact" }).textContent).not.toContain(
      "earlier transition",
    );

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V3");

    expect(screen.getByRole("region", { name: "Impact" }).textContent).toContain(
      "earlier transition",
    );
    const summary = screen.getByRole("region", { name: "Mission transition" });
    expect(summary.textContent).toContain("No new event");
    expect(summary.textContent).not.toContain("No event injected");
  });

  it("drops the previous version from the plan chip once an event hits the revised plan", async () => {
    installSuccessfulApi();
    api.injectEvent.mockResolvedValue({
      id: "EVT-2",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-2",
      event_id: "EVT-2",
      evaluated_plan_id: revisedPlan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: [],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-2"],
      reason_codes: { "ACT-OBS-A-2": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    const chip = await screen.findByLabelText("Current plan V2");
    expect(chip.textContent).toBe("Plan V1 → V2");

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));
    await screen.findByRole("list", { name: "Event impact" });

    expect(screen.getByLabelText("Current plan V2").textContent).toBe("Plan V2");
  });

  it("keeps Event unavailable until a plan exists, since events are evaluated against it", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
    await screen.findByText(scenario.name);

    expect((screen.getByRole("button", { name: "Event" }) as HTMLButtonElement).disabled).toBe(true);
    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    await screen.findByLabelText("Current plan V1");
    expect((screen.getByRole("button", { name: "Event" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("follows an injected cloud block to its request and window across the workspace", async () => {
    installSuccessfulApi();
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: "2026-09-21T10:05:00Z",
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
    } satisfies MissionEventSchema;
    api.injectEvent.mockResolvedValue(event);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: [],
      invalid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      reason_codes: { "ACT-OBS-A-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);
    api.fetchEvents.mockResolvedValue([event]);

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));
    await screen.findByRole("list", { name: "Event impact" });

    const requestRow = within(screen.getByRole("list", { name: "Observation requests" })).getByRole(
      "button",
      { name: /OBS-A/ },
    );
    expect(requestRow.getAttribute("data-selected")).toBe("true");
    expect(requestRow.getAttribute("data-plan-status")).toBe("invalid");
    const timeline = container.querySelector('[aria-label="Mission plan"]') as HTMLElement;
    expect(
      timeline
        .querySelector('.amis-timeline-group-button[data-request-id="OBS-A"]')
        ?.getAttribute("data-selected"),
    ).toBe("true");
    const impactRow = within(screen.getByRole("list", { name: "Event impact" }))
      .getByText("OBS-A")
      .closest("li");
    expect(impactRow?.textContent).toContain("ACT-OBS-A-1");
    expect(impactRow?.textContent).toContain("WIN-OBS-A-1");

    await user.click(screen.getByRole("tab", { name: /Events/ }));
    const eventRow = within(screen.getByRole("list", { name: "Mission events" })).getByRole(
      "button",
      { name: /EVT-1/ },
    );
    expect(eventRow.getAttribute("data-selected")).toBe("true");
  });

  it("injects a battery drop, shows the new battery value and the backend's impact on future actions", async () => {
    installSuccessfulApi();
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "BATTERY_DROP",
      payload: { satellite_id: "SAT-001", new_battery_wh: 60 },
    } satisfies MissionEventSchema;
    api.injectEvent.mockResolvedValue(event);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      invalid_unfrozen_action_ids: ["ACT-OBS-C-1"],
      reason_codes: { "ACT-OBS-C-1": ["INSUFFICIENT_BATTERY"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(within(screen.getByRole("list", { name: "Observation requests" })).getByRole("button", { name: /^OBS-A/ }));
    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-A");
    api.fetchEvents.mockResolvedValue([event]);
    api.fetchState.mockResolvedValue({ ...missionState, battery_wh: 60, active_event_ids: ["EVT-1"] });

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.click(screen.getByRole("radio", { name: "Battery drop" }));
    expect(screen.getByRole("dialog", { name: "Configure event" }).textContent).toContain(
      "SAT-001 battery now 500.0 Wh of 500 Wh",
    );
    await user.type(screen.getByLabelText("New battery (Wh)"), "60");
    await user.click(screen.getByRole("button", { name: "Inject battery drop" }));

    expect(api.injectEvent).toHaveBeenCalledWith(scenario.id, {
      event_type: "BATTERY_DROP",
      payload: { satellite_id: "SAT-001", new_battery_wh: 60 },
    });
    expect(await screen.findByText("60.0 Wh")).toBeTruthy();
    const impactRow = within(await screen.findByRole("list", { name: "Event impact" }))
      .getByText("OBS-C")
      .closest("li");
    expect(impactRow?.getAttribute("data-impact")).toBe("invalid");
    expect(impactRow?.textContent).toContain("INSUFFICIENT_BATTERY");
    const state = screen.getByRole("region", { name: "Mission state" });
    expect(state.textContent).toContain("BATTERY_DROP · EVT-1");
    expect(state.textContent).toContain("SAT-001 battery → 60.0 Wh");
    const summary = screen.getByRole("region", { name: "Mission transition" });
    expect(summary.textContent).toContain("SAT-001 battery → 60.0 Wh");
    expect(summary.textContent).toContain("Awaiting replan");
    expect(fakeMap.lastScene().selectedRequestId).toBeNull();
    expect(screen.getByRole("status", { name: "Mission focus" }).textContent).not.toContain("OBS-A");
  });

  it("injects an emergency request through the event log and lists it without touching the scenario", async () => {
    installSuccessfulApi();
    const emergencyWindow = {
      id: "WIN-OBS-EMERGENCY-1-1",
      request_id: "OBS-EMERGENCY-1",
      satellite_id: "SAT-001",
      start: "2026-09-21T10:10:00Z",
      end: "2026-09-21T10:25:00Z",
      valid: true,
      invalid_reason: null,
    } satisfies ObservationWindowSchema;
    const event = {
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "EMERGENCY_TASK",
      payload: {
        request: {
          id: "OBS-EMERGENCY-1",
          target_lat: 34.05,
          target_lon: -118.24,
          priority: 5,
          duration_s: 600,
          deadline: "2026-09-21T10:25:00Z",
          energy_cost_wh: 40,
          storage_cost_mb: 100,
          status: "pending",
        },
        windows: [emergencyWindow],
      },
    } satisfies MissionEventSchema;
    api.injectEvent.mockResolvedValue(event);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: ["ACT-OBS-A-1", "ACT-OBS-C-1"],
      invalid_unfrozen_action_ids: [],
      reason_codes: {},
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    api.fetchEvents.mockResolvedValue([event]);
    api.fetchWindows.mockResolvedValue([window_, emergencyWindow]);

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.click(screen.getByRole("radio", { name: "Emergency request" }));
    const inject = screen.getByRole("button", { name: "Inject emergency request" });
    expect((inject as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText("Target lat"), "34.05");
    await user.type(screen.getByLabelText("Target lon"), "-118.24");
    await user.click(inject);

    expect(api.injectEvent).toHaveBeenCalledWith(scenario.id, {
      event_type: "EMERGENCY_TASK",
      payload: {
        request: event.payload.request,
        windows: [emergencyWindow],
      },
    });
    const requestRow = await within(
      screen.getByRole("list", { name: "Observation requests" }),
    ).findByRole("button", { name: /OBS-EMERGENCY-1/ });
    expect(requestRow.getAttribute("data-emergency")).toBe("true");
    expect(requestRow.textContent).toContain("emergency · EVT-1");
    expect(requestRow.getAttribute("data-selected")).toBe("true");
    // The scenario stays immutable: it was created once and never re-sent.
    expect(api.createScenario).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("tab", { name: /Requests/ }).textContent).toContain("4");

    await user.click(screen.getByRole("tab", { name: /Windows/ }));
    expect(
      within(screen.getByRole("list", { name: "Observation windows" })).getByRole("button", {
        name: /WIN-OBS-EMERGENCY-1-1/,
      }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: "Impact" }).textContent).toContain(
      "No scheduled actions became invalid.",
    );
  });

  it("shows a rejected event's backend code and details and keeps the dialog open", async () => {
    installSuccessfulApi();
    api.injectEvent.mockRejectedValue(
      new ApiError({
        error: {
          code: "INVALID_EVENT",
          message: "battery drop value must be between zero and battery capacity",
          details: { new_battery_wh: 900, battery_capacity_wh: 500 },
        },
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.click(screen.getByRole("radio", { name: "Battery drop" }));
    await user.type(screen.getByLabelText("New battery (Wh)"), "900");
    await user.click(screen.getByRole("button", { name: "Inject battery drop" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("INVALID_EVENT");
    expect(alert.textContent).toContain("battery drop value must be between zero and battery capacity");
    expect(alert.textContent).toContain("battery_capacity_wh=500");
    expect(screen.getByRole("dialog", { name: "Configure event" })).toBeTruthy();
    expect(api.fetchImpact).not.toHaveBeenCalled();
  });

  it("shows replanning while the replan request runs, then the new version", async () => {
    installSuccessfulApi();
    let finish: (value: MissionPlanSchema) => void = () => undefined;
    api.replan.mockReturnValue(
      new Promise<MissionPlanSchema>((resolve) => {
        finish = resolve;
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    const summary = screen.getByRole("region", { name: "Mission transition" });
    expect(within(summary).getByRole("listitem", { name: "Replanning" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Replan" }).getAttribute("aria-busy")).toBe("true");

    finish(revisedPlan);
    await screen.findByLabelText("Current plan V2");
    expect(within(summary).queryByRole("listitem", { name: "Replanning" })).toBeNull();
  });

  it("keeps the evaluated plan's impact and compares the replan's dropped requests beside it", async () => {
    installSuccessfulApi();
    api.injectEvent.mockResolvedValue({
      id: "EVT-1",
      scenario_id: scenario.id,
      event_time: scenario.start_time,
      event_type: "CLOUD_BLOCK",
      payload: { request_id: "OBS-C", window_id: "WIN-OBS-C-1" },
    } satisfies MissionEventSchema);
    api.fetchImpact.mockResolvedValue({
      id: "IMPACT-1",
      event_id: "EVT-1",
      evaluated_plan_id: plan.id,
      frozen_action_ids: [],
      valid_unfrozen_action_ids: ["ACT-OBS-A-1"],
      invalid_unfrozen_action_ids: ["ACT-OBS-C-1"],
      reason_codes: { "ACT-OBS-C-1": ["WINDOW_INVALIDATED"] },
    } satisfies ImpactSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));
    await screen.findByRole("list", { name: "Event impact" });

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const impact = screen.getByRole("region", { name: "Impact" });
    expect(impact.textContent).toContain("What became invalid in V1 because of this event");
    // The replan's comparison sits beside Impact, not inside it.
    expect(within(impact).queryByRole("region", { name: "Plan comparison" })).toBeNull();
    const comparison = screen.getByRole("region", { name: "Plan comparison" });
    expect(comparison.textContent).toContain("V1 → V2");
    const dropped = within(screen.getByRole("list", { name: "Plan comparison" })).getByRole(
      "button",
      { name: /OBS-C/ },
    );
    expect(dropped.getAttribute("data-change")).toBe("DROPPED");
    expect(dropped.textContent).toContain("WINDOW_INVALIDATED");
    // Plan V1 stays available after V2 exists.
    await user.click(screen.getByRole("tab", { name: /Plans/ }));
    const plans = within(screen.getByRole("list", { name: "Mission plans" })).getAllByRole("button");
    expect(plans.map((row) => row.textContent?.slice(0, 2))).toEqual(["V1", "V2"]);
  });
});
