import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { ApiError } from "./api/amis";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "./api/client";

const api = vi.hoisted(() => ({
  createPlan: vi.fn(),
  createScenario: vi.fn(),
  fetchDemoScenario: vi.fn(),
  fetchEvents: vi.fn(),
  fetchImpact: vi.fn(),
  fetchPlan: vi.fn(),
  fetchState: vi.fn(),
  generateWindows: vi.fn(),
  injectCloudBlock: vi.fn(),
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
  ],
  unscheduled: [],
  mission_utility: 5,
  violation_count: 0,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

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
  api.createPlan.mockResolvedValue(plan);
  api.fetchPlan.mockResolvedValue(plan);
}

async function loadDemoAndGeneratePlan(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
  await screen.findByText(scenario.name);
  await user.click(screen.getByRole("button", { name: "Generate plan" }));
  await screen.findByText("v1 (1 scheduled)");
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
    const { container } = render(<App />);

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

    expect(await screen.findByText("v1 (1 scheduled)")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Mission timeline of scheduled actions" })).toBeTruthy();
    await waitFor(() => expect(api.fetchState).toHaveBeenCalledTimes(2));
    expect(api.fetchEvents).toHaveBeenCalledTimes(2);
    expect(container.querySelector("svg rect")?.getAttribute("fill")).toBe("#3b82f6");
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
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Step" }));

    expect(api.stepSimulation).toHaveBeenCalledWith(scenario.id, 300);
    expect(await screen.findByText("490.0 Wh")).toBeTruthy();
    await waitFor(() =>
      expect(container.querySelector("svg rect")?.getAttribute("fill")).toBe("#f59e0b"),
    );
  });

  it("shows mission complete as a readable message and surfaces a rejected step past the end", async () => {
    installSuccessfulApi();
    api.stepSimulation.mockResolvedValueOnce({
      ...missionState,
      simulated_time: scenario.end_time,
      mission_complete: true,
    } satisfies MissionStateSchema);
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Step" }));
    expect(await screen.findByText("Mission complete.")).toBeTruthy();

    api.stepSimulation.mockRejectedValueOnce(
      new ApiError({
        error: {
          code: "SIMULATION_STATE_ERROR",
          message: "mission is complete; reset the simulation before stepping again",
          details: {},
        },
      }),
    );
    await user.click(screen.getByRole("button", { name: "Step" }));

    expect(await screen.findByText("SIMULATION_STATE_ERROR")).toBeTruthy();
    expect(
      screen.getByText(/mission is complete; reset the simulation before stepping again/),
    ).toBeTruthy();
  });

  it("injects a cloud block chosen from request and window dropdowns and shows the impact, without replanning", async () => {
    installSuccessfulApi();
    api.injectCloudBlock.mockResolvedValue({
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

    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));

    expect(api.injectCloudBlock).toHaveBeenCalledWith(scenario.id, "OBS-A", "WIN-OBS-A-1");
    expect(await screen.findByText(/OBS-A: WINDOW_INVALIDATED/)).toBeTruthy();
    expect(screen.getByText("v1 (1 scheduled)")).toBeTruthy();
    expect(api.createPlan).toHaveBeenCalledTimes(1);
    expect(
      (screen.getByRole("option", { name: /WIN-OBS-A-1/ }) as HTMLOptionElement).textContent,
    ).toContain("invalid");
  });
});
