import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DecisionTraceSchema } from "../api/client";
import { TracePanel } from "./TracePanel";

const traces = [
  {
    id: "TRACE-0001",
    plan_id: "PLAN-2",
    event_id: "EVT-1",
    request_id: "OBS-B",
    reason_code: "WINDOW_INVALIDATED",
    previous_action: null,
    new_action: null,
    constraint_name: "window_containment",
    message: "OBS-B moved from 2026-09-21 10:20 to 2026-09-21 11:15 because its observation window was invalidated.",
    metadata: {},
  },
  {
    id: "TRACE-0002",
    plan_id: "PLAN-2",
    event_id: "EVT-1",
    request_id: "OBS-D",
    reason_code: "NO_ALTERNATIVE_WINDOW",
    previous_action: null,
    new_action: null,
    constraint_name: "window_containment",
    message: "OBS-D was dropped because no other window fits it.",
    metadata: {},
  },
] satisfies DecisionTraceSchema[];

function renderTrace(overrides: Partial<Parameters<typeof TracePanel>[0]> = {}) {
  const onSelectRequest = vi.fn();
  const result = render(
    <TracePanel
      traces={traces}
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

describe("decision trace panel", () => {
  it("asks for a replan before it can show anything", () => {
    renderTrace({ traces: [] });

    expect(
      screen.getByText("Replan to see why each request moved, was inserted, or was dropped."),
    ).toBeTruthy();
  });

  it("lists each trace with its reason code and generated sentence, in order", () => {
    renderTrace();

    const list = screen.getByRole("list", { name: "Decision trace" });
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("OBS-B");
    expect(items[0].textContent).toContain("WINDOW_INVALIDATED");
    expect(items[0].textContent).toContain(traces[0].message);
    expect(items[1].textContent).toContain("OBS-D");
    expect(items[1].textContent).toContain("NO_ALTERNATIVE_WINDOW");
  });

  it("selects the request a trace entry refers to when clicked, and clears it when clicked again", async () => {
    const user = userEvent.setup();
    const { onSelectRequest, rerender } = renderTrace();

    await user.click(screen.getByRole("button", { name: /OBS-B/ }));
    expect(onSelectRequest).toHaveBeenCalledWith("OBS-B");

    rerender(
      <TracePanel
        traces={traces}
        selectedRequestId="OBS-B"
        onSelectRequest={onSelectRequest}
      />,
    );
    await user.click(screen.getByRole("button", { name: /OBS-B/ }));
    expect(onSelectRequest).toHaveBeenLastCalledWith(null);
  });

  it("marks the entry matching the request selected elsewhere as selected", () => {
    renderTrace({ selectedRequestId: "OBS-D" });

    expect(
      screen.getByRole("button", { name: /OBS-D/ }).getAttribute("data-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: /OBS-B/ }).getAttribute("data-selected"),
    ).toBeNull();
  });
});
