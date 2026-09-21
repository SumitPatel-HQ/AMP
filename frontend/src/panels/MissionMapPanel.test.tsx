import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { MissionMapPanel } from "./MissionMapPanel";
import type {
  MissionPlanSchema,
  MissionStateSchema,
  ScenarioSchema,
} from "../api/client";

const api = vi.hoisted(() => ({
  createPlan: vi.fn(),
  createScenario: vi.fn(),
  fetchDemoScenario: vi.fn(),
  fetchEvents: vi.fn(),
  fetchState: vi.fn(),
  generateWindows: vi.fn(),
}));

vi.mock("../api/amis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/amis")>()),
  ...api,
}));

const scenario = {
  id: "SCN-MAP",
  name: "Map demo",
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
      target_lat: -33.87,
      target_lon: 151.21,
      priority: 3,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
  ],
} satisfies ScenarioSchema;

const plan = {
  id: "SCN-MAP:PLAN-1",
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
      id: "ACT-OBS-B-1",
      request_id: "OBS-B",
      satellite_id: scenario.satellite.id,
      window_id: "WIN-OBS-B-1",
      start: "2026-09-21T12:00:00Z",
      end: "2026-09-21T12:10:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
  ],
  unscheduled: [],
  mission_utility: 8,
  violation_count: 0,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

const missionState = {
  scenario_id: scenario.id,
  simulated_time: "2026-09-21T10:15:00Z",
  satellite_id: scenario.satellite.id,
  battery_wh: 500,
  storage_usage_mb: 0,
  available: true,
  active_event_ids: [],
  completed_request_ids: [],
  mission_complete: false,
} satisfies MissionStateSchema;

function renderMap(overrides: Partial<Parameters<typeof MissionMapPanel>[0]> = {}) {
  const onSelectRequest = vi.fn();
  const result = render(
    <MissionMapPanel
      scenario={scenario}
      plan={plan}
      missionState={missionState}
      selectedRequestId={null}
      onSelectRequest={onSelectRequest}
      {...overrides}
    />,
  );
  return { ...result, onSelectRequest };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("mission map", () => {
  it("draws a target for every observation request and the satellite", () => {
    renderMap();

    expect(screen.getByRole("button", { name: "Target OBS-A" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Target OBS-B" })).toBeTruthy();
    expect(screen.getByLabelText("Satellite SAT-001")).toBeTruthy();
  });

  it("highlights the target of the request selected elsewhere", () => {
    const { container } = renderMap({ selectedRequestId: "OBS-B" });

    expect(
      container.querySelector('[data-request-id="OBS-B"]')?.getAttribute("data-selected"),
    ).toBe("true");
    expect(
      container.querySelector('[data-request-id="OBS-A"]')?.getAttribute("data-selected"),
    ).toBeNull();
  });

  it("selects a request when its target is clicked and clears it when clicked again", async () => {
    const user = userEvent.setup();
    const { onSelectRequest, rerender } = renderMap();

    await user.click(screen.getByRole("button", { name: "Target OBS-A" }));
    expect(onSelectRequest).toHaveBeenCalledWith("OBS-A");

    rerender(
      <MissionMapPanel
        scenario={scenario}
        plan={plan}
        missionState={missionState}
        selectedRequestId="OBS-A"
        onSelectRequest={onSelectRequest}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Target OBS-A" }));
    expect(onSelectRequest).toHaveBeenLastCalledWith(null);
  });

  it("places the satellite over the target it is observing", () => {
    renderMap();

    expect(
      screen.getByLabelText("Satellite SAT-001").getAttribute("data-over-request"),
    ).toBe("OBS-A");
  });

  it("draws targets without a plan or a mission state, so it gates nothing", () => {
    renderMap({ plan: null, missionState: null });

    expect(screen.getByRole("button", { name: "Target OBS-A" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Target OBS-B" })).toBeTruthy();
  });

  it("draws no satellite until a plan says where it is", () => {
    renderMap({ plan: null, missionState: null });

    expect(screen.queryByLabelText("Satellite SAT-001")).toBeNull();
  });

  it("leaves the satellite over the last target it observed between actions", () => {
    renderMap({
      missionState: { ...missionState, simulated_time: "2026-09-21T11:00:00Z" },
    });

    const satellite = screen.getByLabelText("Satellite SAT-001");
    expect(satellite.getAttribute("data-over-request")).toBeNull();
    expect(satellite.style.left).toBe(
      screen.getByRole("button", { name: "Target OBS-A" }).style.left,
    );
  });

  it("asks for a scenario before it can show anything", () => {
    renderMap({ scenario: null });

    expect(screen.getByText("Load a scenario to see its observation targets.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Target/ })).toBeNull();
  });

  it("keeps every target reachable from the keyboard", async () => {
    const user = userEvent.setup();
    const { onSelectRequest } = renderMap();

    const targets = screen.getByRole("group", { name: "Observation targets" });
    await user.tab();
    expect(within(targets).getByRole("button", { name: "Target OBS-A" })).toBe(
      document.activeElement,
    );
    await user.keyboard("{Enter}");
    expect(onSelectRequest).toHaveBeenCalledWith("OBS-A");
  });
});

async function renderLoadedDashboard(user: ReturnType<typeof userEvent.setup>) {
  api.fetchDemoScenario.mockResolvedValue(scenario);
  api.createScenario.mockResolvedValue(scenario);
  api.fetchState.mockResolvedValue(missionState);
  api.fetchEvents.mockResolvedValue([]);
  api.generateWindows.mockResolvedValue([]);
  api.createPlan.mockResolvedValue(plan);
  const rendered = render(<App />);

  await user.click(screen.getByRole("button", { name: "Load demo scenario" }));
  await screen.findByText(scenario.name);
  await user.click(screen.getByRole("button", { name: "Generate plan" }));
  await screen.findByText("v1 (2 scheduled)");
  return rendered;
}

// This suite proves the map is wired to the same selection the rest of the
// dashboard reads. Delete it with the map panel; no other test touches it.
describe("mission map linking", () => {
  it("highlights the target of a request selected on the timeline", async () => {
    const user = userEvent.setup();
    const { container } = await renderLoadedDashboard(user);

    const timelineRow = container.querySelector(
      'svg [data-request-id="OBS-B"]',
    ) as SVGGElement;
    await user.click(timelineRow);

    expect(
      screen.getByRole("button", { name: "Target OBS-B" }).getAttribute("data-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: "Target OBS-A" }).getAttribute("data-selected"),
    ).toBeNull();
  });

  it("highlights the timeline row of a request selected on the map", async () => {
    const user = userEvent.setup();
    const { container } = await renderLoadedDashboard(user);

    await user.click(screen.getByRole("button", { name: "Target OBS-A" }));

    expect(
      container
        .querySelector('svg [data-request-id="OBS-A"]')
        ?.getAttribute("data-selected"),
    ).toBe("true");
  });
});
