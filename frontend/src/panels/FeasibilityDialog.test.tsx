import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { FeasibilitySchema } from "../api/client";
import { scenario } from "../test/mapFixtures";
import { FeasibilityDialog } from "./FeasibilityDialog";

const fetchMock = vi.hoisted(() => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  return fetch;
});

afterEach(() => { cleanup(); fetchMock.mockReset(); });

const answer: FeasibilitySchema = {
  scenario_id: scenario.id, scope: "window_only",
  target_lat: 10, target_lon: 20, duration_s: 30,
  deadline: scenario.end_time, satellite_id: null,
  search_start: scenario.start_time, search_end: scenario.end_time,
  earliest_satellite_id: "SAT-001",
  results: [
    { satellite_id: "SAT-001", window_id: "WIN-CANDIDATE-1",
      window_start: "2026-09-21T10:20:00Z", window_end: "2026-09-21T10:25:00Z",
      earliest_start: "2026-09-21T10:20:15Z", latest_finish: "2026-09-21T10:25:00Z", reason: null },
    { satellite_id: "SAT-002", window_id: null, window_start: null, window_end: null,
      earliest_start: null, latest_finish: null, reason: "no_suitable_window" },
    { satellite_id: "SAT-003", window_id: null, window_start: null, window_end: null,
      earliest_start: null, latest_finish: null, reason: "satellite_unavailable" },
  ],
};

async function fill() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Latitude"), "10");
  await user.type(screen.getByLabelText("Longitude"), "20");
  await user.type(screen.getByLabelText("Duration (s)"), "30");
  return user;
}

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

it("compares through a read-only GET and shows every satellite, UTC seconds, and window-only limits", async () => {
  fetchMock.mockResolvedValue(reply(answer));
  render(<FeasibilityDialog scenario={scenario} onClose={() => {}} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  const results = await screen.findByLabelText("Feasibility results");
  expect(results.textContent).toContain("Earliest suitable satellite: SAT-001");
  expect(results.textContent).toContain("No suitable window");
  expect(results.textContent).toContain("Satellite unavailable");
  expect(results.textContent).toContain("2026-09-21 10:20:15 UTC");
  expect(screen.getByLabelText("Time basis").textContent).toContain("independent of the mission clock");
  const scope = screen.getByLabelText("Feasibility scope").textContent;
  expect(scope).toContain("pairwise slew, active outages, and reservations");
  expect(scope).toContain("Nothing is submitted or reserved");
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(request.method).toBe("GET");
  const url = new URL(request.url);
  expect(url.pathname).toBe(`/scenarios/${scenario.id}/feasibility`);
  expect(url.searchParams.get("duration")).toBe("30");
  expect(url.searchParams.get("deadline")).toBe("2026-09-21T14:00:00.000Z");
  expect(fetchMock.mock.calls).toHaveLength(1);
});

it("drops an old answer as soon as the candidate changes, including an in-flight answer", async () => {
  let resolve!: (value: Response) => void;
  fetchMock.mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  render(<FeasibilityDialog scenario={scenario} onClose={() => {}} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await user.type(screen.getByLabelText("Latitude"), "1");
  await act(async () => { resolve(reply(answer)); });
  expect(screen.queryByLabelText("Feasibility results")).toBeNull();
  expect((screen.getByRole("button", { name: "Compare windows" }) as HTMLButtonElement).disabled).toBe(false);
  fetchMock.mockResolvedValue(reply({ ...answer, target_lat: 101 }));
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await screen.findByLabelText("Feasibility results");
  await user.clear(screen.getByLabelText("Duration (s)"));
  expect(screen.queryByLabelText("Feasibility results")).toBeNull();
});

it("clears results and ignores pending replies when a scenario changes, even with the same id", async () => {
  fetchMock.mockResolvedValueOnce(reply(answer));
  const view = render(<FeasibilityDialog scenario={scenario} onClose={() => {}} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await screen.findByLabelText("Feasibility results");
  let resolve!: (value: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  const changed = { ...scenario, end_time: "2026-09-21T12:00:00Z" };
  view.rerender(<FeasibilityDialog scenario={changed} onClose={() => {}} />);
  await act(async () => { resolve(reply(answer)); });
  expect(screen.queryByLabelText("Feasibility results")).toBeNull();
  expect((screen.getByLabelText("Deadline (UTC)") as HTMLInputElement).value).toBe("2026-09-21T12:00");
  expect((screen.getByLabelText("Latitude") as HTMLInputElement).value).toBe("");
});

it("keeps deadline seconds when initializing the candidate form", async () => {
  fetchMock.mockResolvedValue(reply(answer));
  render(<FeasibilityDialog scenario={{ ...scenario, end_time: "2026-09-21T14:00:37Z" }} onClose={() => {}} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await screen.findByLabelText("Feasibility results");
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(new URL(request.url).searchParams.get("deadline")).toBe("2026-09-21T14:00:37.000Z");
});

it("uses the Scenario's satellites for filtering and reports an explicit unserved comparison", async () => {
  fetchMock.mockResolvedValue(reply({ ...answer, satellite_id: "SAT-002", earliest_satellite_id: null, results: [answer.results[1]] }));
  const multi = { ...scenario, satellites: [scenario.satellite, { ...scenario.satellite, id: "SAT-002" }] };
  render(<FeasibilityDialog scenario={multi} onClose={() => {}} />);
  const user = await fill();
  await user.selectOptions(screen.getByLabelText("Satellite"), "SAT-002");
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  const results = await screen.findByLabelText("Feasibility results");
  expect(results.textContent).toContain("No satellite has a suitable window.");
  expect(within(results).getAllByRole("row")).toHaveLength(2);
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(new URL(request.url).searchParams.get("satellite_id")).toBe("SAT-002");
});

it("shows the API's validation error details and never keeps an old result beside an error", async () => {
  fetchMock.mockResolvedValueOnce(reply(answer));
  render(<FeasibilityDialog scenario={scenario} onClose={() => {}} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await screen.findByLabelText("Feasibility results");
  fetchMock.mockResolvedValueOnce(reply({ error: { code: "INVALID_SCENARIO", message: "deadline must be after the scenario start", details: { deadline: scenario.start_time } } }, 400));
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  expect((await screen.findByRole("alert")).textContent).toContain("deadline must be after the scenario start");
  expect(screen.queryByLabelText("Feasibility results")).toBeNull();
  fireEvent.change(screen.getByLabelText("Deadline (UTC)"), { target: { value: "" } });
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  expect(screen.getByRole("alert").textContent).toContain("Enter a deadline in UTC.");
  expect(fetchMock.mock.calls).toHaveLength(2);
});

it("preserves a comparison for unchanged Scenario inputs and drops it on reset to another Scenario", async () => {
  fetchMock.mockResolvedValue(reply(answer));
  const onClose = vi.fn();
  const view = render(<FeasibilityDialog scenario={scenario} onClose={onClose} />);
  const user = await fill();
  await user.click(screen.getByRole("button", { name: "Compare windows" }));
  await screen.findByLabelText("Feasibility results");
  view.rerender(<FeasibilityDialog scenario={{ ...scenario }} onClose={onClose} />);
  expect(screen.getByLabelText("Feasibility results").textContent).toContain("SAT-001");
  view.rerender(<FeasibilityDialog scenario={{ ...scenario, id: "SCN-OTHER" }} onClose={onClose} />);
  expect(screen.queryByLabelText("Feasibility results")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Close" }));
  expect(onClose).toHaveBeenCalledOnce();
});
