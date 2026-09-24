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
  fetchPlan: vi.fn(),
  fetchState: vi.fn(),
  fetchTraces: vi.fn(),
  generateWindows: vi.fn(),
  comparePlans: vi.fn(),
  injectCloudBlock: vi.fn(),
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
  api.createPlan.mockResolvedValue(plan);
  api.fetchPlan.mockResolvedValue(plan);
  api.replan.mockResolvedValue(revisedPlan);
  api.comparePlans.mockResolvedValue(planDiff);
  api.fetchTraces.mockResolvedValue(traces);
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

    expect(await screen.findByLabelText("Current plan V1")).toBeTruthy();
    expect(
      screen.getByRole("group", { name: "Mission timeline of scheduled actions" }),
    ).toBeTruthy();
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

    await user.click(screen.getByRole("button", { name: "Event" }));
    await user.selectOptions(screen.getByLabelText("Request"), "OBS-A");
    await user.selectOptions(screen.getByLabelText("Window"), "WIN-OBS-A-1");
    await user.click(screen.getByRole("button", { name: "Inject cloud block" }));

    expect(api.injectCloudBlock).toHaveBeenCalledWith(scenario.id, "OBS-A", "WIN-OBS-A-1");
    const impactRow = within(await screen.findByRole("list", { name: "Event impact" })).getByText(
      "OBS-A",
    ).closest("li");
    expect(impactRow?.getAttribute("data-impact")).toBe("invalid");
    expect(impactRow?.textContent).toContain("WINDOW_INVALIDATED");
    expect(screen.getByLabelText("Current plan V1")).toBeTruthy();
    expect(api.createPlan).toHaveBeenCalledTimes(1);
    expect(
      (screen.getByRole("option", { name: /WIN-OBS-A-1/ }) as HTMLOptionElement).textContent,
    ).toContain("invalid");
  });
  it("replans against the plan version currently displayed and stacks initial above revised", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));

    expect(await screen.findByLabelText("Current plan V2")).toBeTruthy();
    expect(api.replan).toHaveBeenCalledWith(scenario.id, plan.id);
    expect(api.comparePlans).toHaveBeenCalledWith(plan.id, revisedPlan.id);

    const timelines = Array.from(container.querySelectorAll("svg[aria-label]")).map(
      (svg) => svg.getAttribute("aria-label"),
    );
    expect(timelines).toEqual([
      "Initial plan timeline of scheduled actions",
      "Revised plan timeline of scheduled actions",
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
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V3");

    expect(api.replan).toHaveBeenNthCalledWith(1, scenario.id, plan.id);
    expect(api.replan).toHaveBeenNthCalledWith(2, scenario.id, revisedPlan.id);
  });

  it("marks changed requests on the revised timeline and leaves the initial timeline unmarked", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    const initial = container.querySelector('[aria-label="Initial plan"]') as HTMLElement;
    expect(
      revised.querySelector('[data-request-id="OBS-A"]')?.getAttribute("data-change"),
    ).toBe("MOVED");
    expect(
      revised.querySelector('[data-request-id="OBS-B"]')?.getAttribute("data-change"),
    ).toBe("INSERTED");
    expect(within(revised).getByText("OBS-A · MOVED")).toBeTruthy();
    expect(
      initial.querySelector('[data-request-id="OBS-A"]')?.getAttribute("data-change"),
    ).toBeNull();
  });

  it("draws frozen actions differently from unfrozen ones", async () => {
    installSuccessfulApi();
    const steppedState = {
      ...missionState,
      simulated_time: "2026-09-21T11:30:00Z",
    } satisfies MissionStateSchema;
    api.stepSimulation.mockResolvedValue(steppedState);
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);
    api.fetchState.mockResolvedValue(steppedState);
    await user.click(screen.getByRole("button", { name: "Step" }));
    await waitFor(() => expect(api.stepSimulation).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    const frozen = revised.querySelector('[data-request-id="OBS-A"]');
    const unfrozen = revised.querySelector('[data-request-id="OBS-B"]');
    expect(frozen?.getAttribute("data-frozen")).toBe("true");
    expect(unfrozen?.getAttribute("data-frozen")).toBe("false");
    expect(frozen?.querySelector("rect")?.getAttribute("stroke")).not.toBe(
      unfrozen?.querySelector("rect")?.getAttribute("stroke"),
    );
  });

  it("lists every unscheduled request under its own timeline and never draws it on one", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const initialEntries = within(
      screen.getByRole("list", { name: "Initial plan unscheduled requests" }),
    ).getAllByRole("listitem");
    expect(initialEntries).toHaveLength(1);
    expect(initialEntries[0].textContent).toBe("OBS-B · priority 4 · DEADLINE_VIOLATION");

    const revisedEntries = within(
      screen.getByRole("list", { name: "Revised plan unscheduled requests" }),
    ).getAllByRole("listitem");
    expect(revisedEntries).toHaveLength(1);
    expect(revisedEntries[0].textContent).toContain(
      "OBS-C · priority 3 · WINDOW_INVALIDATED",
    );

    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    expect(revised.querySelector('svg [data-request-id="OBS-C"]')).toBeNull();
    const initial = container.querySelector('[aria-label="Initial plan"]') as HTMLElement;
    expect(initial.querySelector('svg [data-request-id="OBS-B"]')).toBeNull();
  });

  it("shows a plan version conflict as a readable message and keeps the displayed plan", async () => {
    installSuccessfulApi();
    api.replan.mockRejectedValue(
      new ApiError({
        error: {
          code: "PLAN_VERSION_CONFLICT",
          message: "replan named a plan version that is no longer current",
          details: { current_plan_id: "SCN-002:PLAN-9" },
        },
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));

    expect(await screen.findByText("PLAN_VERSION_CONFLICT")).toBeTruthy();
    expect(
      screen.getByText(/replan named a plan version that is no longer current/),
    ).toBeTruthy();
    expect(screen.getByLabelText("Current plan V1")).toBeTruthy();
    expect(api.comparePlans).not.toHaveBeenCalled();
  });
  it("keeps the revised timeline current when the clock moves after a replan", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
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

    await user.click(screen.getByRole("button", { name: "Step" }));

    const revised = () => container.querySelector('[aria-label="Revised plan"]');
    await waitFor(() =>
      expect(
        revised()?.querySelector('[data-request-id="OBS-A"] rect')?.getAttribute("fill"),
      ).toBe("#f59e0b"),
    );
    // The clock moved past 11:00, but the replan ran at 10:00 and was free to
    // move this action, so it must not acquire frozen styling after the fact.
    expect(
      revised()?.querySelector('[data-request-id="OBS-A"]')?.getAttribute("data-frozen"),
    ).toBe("false");
  });
  it("marks the request the replan dropped in the revised unscheduled list", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    const dropped = revised.querySelector('li[data-request-id="OBS-C"]');
    expect(dropped?.getAttribute("data-change")).toBe("DROPPED");
    expect(dropped?.textContent).toContain("DROPPED");

    const initial = container.querySelector('[aria-label="Initial plan"]') as HTMLElement;
    expect(
      initial.querySelector('li[data-request-id="OBS-B"]')?.getAttribute("data-change"),
    ).toBeNull();
  });

  it("does not mark a request the clock completed as one the replan changed", async () => {
    installSuccessfulApi();
    api.comparePlans.mockResolvedValue({
      ...planDiff,
      entries: [
        {
          request_id: "OBS-A",
          change_type: "COMPLETED",
          reason_code: "REQUEST_UNCHANGED",
          old_start: "2026-09-21T10:10:00Z",
          new_start: "2026-09-21T10:10:00Z",
        },
      ],
    } satisfies PlanDiffSchema);
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    expect(
      revised.querySelector('[data-request-id="OBS-A"]')?.getAttribute("data-change"),
    ).toBeNull();
  });

  it("lets a keyboard user select a request from the timeline", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    const row = screen.getByRole("button", { name: /^OBS-A, / });
    row.focus();
    await user.keyboard("{Enter}");

    expect(
      container.querySelector('svg [data-request-id="OBS-A"]')?.getAttribute("data-selected"),
    ).toBe("true");
  });

  it("compares the two plan versions' metrics side by side after a replan", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    expect(screen.getByText("Replan to compare plan metrics.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const churnRow = screen.getByText("Plan churn").closest("tr");
    expect(churnRow?.textContent).toContain("N/A");
    expect(churnRow?.textContent).toContain("67%");
  });

  it("lists each decision trace with its reason code and generated sentence after a replan", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);

    expect(
      screen.getByText("Replan to see why each request moved, was inserted, or was dropped."),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    const entry = within(screen.getByRole("list", { name: "Decision trace" })).getByRole(
      "button",
      { name: /OBS-A/ },
    );
    expect(entry.textContent).toContain("ALTERNATIVE_WINDOW_AVAILABLE");
    expect(entry.textContent).toContain(traces[0].message);
  });

  it("highlights the matching request on both timelines when a trace entry is clicked", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    await user.click(
      within(screen.getByRole("list", { name: "Decision trace" })).getByRole("button", {
        name: /OBS-A/,
      }),
    );

    const initial = container.querySelector('[aria-label="Initial plan"]') as HTMLElement;
    const revised = container.querySelector('[aria-label="Revised plan"]') as HTMLElement;
    expect(
      revised.querySelector('svg [data-request-id="OBS-A"]')?.getAttribute("data-selected"),
    ).toBe("true");
    expect(
      initial.querySelector('svg [data-request-id="OBS-A"]')?.getAttribute("data-selected"),
    ).toBe("true");
  });

  it("clears the selected request when replanning, since it may not exist in the new trace", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    const { container } = render(<App />);
    await loadDemoAndGeneratePlan(user);

    await user.click(screen.getByRole("button", { name: /^OBS-A, / }));
    expect(
      container.querySelector('svg [data-request-id="OBS-A"]')?.getAttribute("data-selected"),
    ).toBe("true");

    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    expect(container.querySelector('[data-selected="true"]')).toBeNull();
  });

  it("refreshes the metrics panel's battery and storage figures after a step, since they read live mission state", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    render(<App />);
    await loadDemoAndGeneratePlan(user);
    await user.click(screen.getByRole("button", { name: "Replan" }));
    await screen.findByLabelText("Current plan V2");

    expect(screen.getByText("Battery used").closest("tr")?.textContent).toContain("0%");

    api.comparePlans.mockResolvedValueOnce({
      ...planDiff,
      metrics_after: { ...planDiff.metrics_after!, battery_utilisation: 0.5 },
    } satisfies PlanDiffSchema);
    api.stepSimulation.mockResolvedValue({
      ...missionState,
      simulated_time: "2026-09-21T11:05:00Z",
      battery_wh: 250,
    } satisfies MissionStateSchema);
    api.fetchPlan.mockResolvedValue(revisedPlan);

    await user.click(screen.getByRole("button", { name: "Step" }));

    await waitFor(() =>
      expect(screen.getByText("Battery used").closest("tr")?.textContent).toContain("50%"),
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
      container.querySelector('svg [data-request-id="OBS-A"]')?.getAttribute("data-selected"),
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
    api.injectCloudBlock.mockResolvedValue(event);
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
    expect(section("Decision trace").textContent).toContain("V1 → V2");
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
    api.injectCloudBlock.mockResolvedValue(event);
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
    api.injectCloudBlock.mockResolvedValue({
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
});
