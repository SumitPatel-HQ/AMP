import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { MissionMapPanel } from "./MissionMapPanel";
import { fakeMap } from "../test/fakeMapEngine";
import { missionState, plan, scenario } from "../test/mapFixtures";
import type { MissionEventSchema } from "../api/client";

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

async function renderMap(overrides: Partial<Parameters<typeof MissionMapPanel>[0]> = {}) {
  const onSelectRequest = vi.fn();
  const props = {
    scenario,
    plan,
    missionState,
    events: [] as MissionEventSchema[],
    selectedRequestId: null,
    onSelectRequest,
    ...overrides,
  };
  const result = render(<MissionMapPanel {...props} />);
  await waitFor(() => expect(fakeMap.handlers).not.toBeNull());
  return { ...result, props, onSelectRequest };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("mission map", () => {
  it("draws a target for every observation request and the satellite", async () => {
    await renderMap();

    const { model } = fakeMap.lastScene();
    expect(model.targets.map((target) => target.requestId)).toEqual(["OBS-A", "OBS-B"]);
    expect(model.satellite?.satelliteId).toBe("SAT-001");
  });

  it("passes the request selected elsewhere to the map", async () => {
    await renderMap({ selectedRequestId: "OBS-B" });

    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-B");
  });

  it("selects a request when its target is picked and clears it when picked again", async () => {
    const { onSelectRequest, rerender, props } = await renderMap();

    act(() => fakeMap.handlers?.onPickTarget("OBS-A"));
    expect(onSelectRequest).toHaveBeenCalledWith("OBS-A");

    rerender(<MissionMapPanel {...props} selectedRequestId="OBS-A" />);
    act(() => fakeMap.handlers?.onPickTarget("OBS-A"));
    expect(onSelectRequest).toHaveBeenLastCalledWith(null);
  });

  it("asks for a scenario before it can show anything, and draws nothing", async () => {
    await renderMap({ scenario: null });

    expect(screen.getByText("Load a scenario to see its observation targets.")).toBeTruthy();
    expect(fakeMap.scenes).toHaveLength(0);
  });

  it("switches an overlay off from the layers box", async () => {
    const user = userEvent.setup();
    await renderMap();

    const layers = screen.getByRole("list", { name: "Map layers" });
    await user.click(within(layers).getByRole("checkbox", { name: /Plan sequence/ }));

    expect(fakeMap.lastScene().visibility.sequence).toBe(false);
    expect(fakeMap.lastScene().visibility.labels).toBe(true);
  });

  it("zooms and refits from the map controls", async () => {
    const user = userEvent.setup();
    await renderMap();

    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    await user.click(screen.getByRole("button", { name: "Zoom out" }));
    await user.click(screen.getByRole("button", { name: "Fit targets" }));

    expect(fakeMap.zooms).toEqual([1, -1]);
    expect(fakeMap.fits).toBe(1);
  });

  it("shows a hovered target's plan placement and events", async () => {
    await renderMap({
      events: [
        {
          id: "EVT-001",
          scenario_id: scenario.id,
          event_time: scenario.start_time,
          event_type: "CLOUD_BLOCK",
          payload: { request_id: "OBS-A", window_id: "WIN-OBS-A-1" },
        },
      ],
    });

    act(() => fakeMap.handlers?.onHover({ kind: "target", id: "OBS-A", x: 10, y: 10 }));

    const card = screen.getByRole("tooltip");
    expect(card.textContent).toContain("OBS-A");
    expect(card.textContent).toContain("Scheduled");
    expect(card.textContent).toContain("10:10–10:20");
    expect(card.textContent).toContain("EVT-001");
  });

  it("names the basemap it is drawing on", async () => {
    await renderMap();

    act(() => fakeMap.handlers?.onBasemap("OpenFreeMap"));

    expect(screen.getByText("2 targets · OpenFreeMap")).toBeTruthy();
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

    expect(fakeMap.lastScene().selectedRequestId).toBe("OBS-B");
  });

  it("highlights the timeline row of a request selected on the map", async () => {
    const user = userEvent.setup();
    const { container } = await renderLoadedDashboard(user);

    await waitFor(() => expect(fakeMap.handlers).not.toBeNull());
    act(() => fakeMap.handlers?.onPickTarget("OBS-A"));

    expect(
      container
        .querySelector('svg [data-request-id="OBS-A"]')
        ?.getAttribute("data-selected"),
    ).toBe("true");
  });
});
