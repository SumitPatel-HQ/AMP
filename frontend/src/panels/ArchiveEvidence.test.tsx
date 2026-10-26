import { readFileSync } from "node:fs";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { MissionEventSchema } from "../api/client";
import { missionState, plan, scenario } from "../test/mapFixtures";
import { ArchiveEvidenceDetails, ARCHIVE_APPROXIMATION } from "./ArchiveEvidence";
import { EventControl } from "./EventControl";
import { MissionNavPanel } from "./MissionNavPanel";

const input = JSON.parse(readFileSync("../amis/data/examples/archive-synthetic-fulfillment/event-input.json", "utf8"));
const event: MissionEventSchema = {
  id: "EVT-ARCHIVE", scenario_id: scenario.id, event_time: "2026-09-21T10:05:00Z", ...input,
};

afterEach(cleanup);

it("shows the source, explicit thresholds, approximation, credit and fulfillment outcome", () => {
  render(<ArchiveEvidenceDetails event={event} />);
  const evidence = within(screen.getByLabelText("Archive fulfillment evidence"));
  expect(evidence.getByText("Satisfied by archive imagery · OBS-B")).toBeTruthy();
  expect(evidence.getByText(/synthetic-optical \/ synthetic-scene-001/)).toBeTruthy();
  expect(evidence.getByText(/Cloud 12% ≤ 20% · GSD 10 m ≤ 10 m/)).toBeTruthy();
  expect(evidence.getByText(ARCHIVE_APPROXIMATION)).toBeTruthy();
  expect(evidence.getByText(/Credit: Synthetic fixture/)).toBeTruthy();
  expect(evidence.getByText(/synthetic-profile-v1 · policy archive-point-v1/)).toBeTruthy();
  expect(evidence.getByRole("link", { name: "Source item" }).getAttribute("href")).toBe("https://example.org/synthetic-scene-001");
});

it("records the supplied payload through the event control without a replan operation", async () => {
  const onInjectEvent = vi.fn().mockResolvedValue(true);
  const onInjected = vi.fn();
  render(<EventControl scenario={scenario} plan={plan} missionState={missionState} windows={[]} events={[]} loading={false} onInjectEvent={onInjectEvent} onInjected={onInjected} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("radio", { name: "Archive fulfillment" }));
  await user.click(screen.getByLabelText("Archive evidence payload (JSON)"));
  await user.paste(JSON.stringify(input.payload));
  await user.click(screen.getByRole("button", { name: "Record archive fulfillment" }));
  expect(onInjectEvent).toHaveBeenCalledWith(input);
  expect(onInjected).toHaveBeenCalledOnce();
});

it("keeps archive fulfillment distinct from the obsolete active imaging action in request inspection", () => {
  render(<MissionNavPanel scenario={scenario} plan={plan} plans={[plan]} replanResult={null} impact={null} missionState={missionState} windows={[]} events={[event]} requestPool={[]} selection={{ requestId: "OBS-B", eventId: null, windowId: null, planId: null }} onSelectRequest={vi.fn()} onSelectWindow={vi.fn()} onSelectEvent={vi.fn()} onSelectPlan={vi.fn()} />);
  const requests = within(screen.getByRole("list", { name: "Observation requests" }));
  expect(requests.getByText("archive fulfilled")).toBeTruthy();
  expect(requests.getByLabelText("Archive fulfillment evidence")).toBeTruthy();
});
