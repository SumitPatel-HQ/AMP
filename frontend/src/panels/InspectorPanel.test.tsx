import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InspectorPanel } from "./InspectorPanel";
import { PanelFrame } from "./PanelFrame";

afterEach(cleanup);

it.each(["Mission state", "Impact", "Plan comparison", "Mission evaluation"])("keeps complete %s content and callbacks in both presentations", title => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); };
  const select = vi.fn();
  render(<InspectorPanel title={title}><PanelFrame title={title}><p>Complete evidence and metadata</p><button onClick={select}>Select request</button></PanelFrame></InspectorPanel>);
  const expand = screen.getByRole("button", { name: "Expand panel" });
  expand.focus();
  fireEvent.click(expand);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Complete evidence and metadata")).toBeTruthy();
  fireEvent.click(within(dialog).getByText("Select request"));
  expect(select).toHaveBeenCalledOnce();
  expect(screen.getAllByText("Complete evidence and metadata")).toHaveLength(2);
  fireEvent.click(within(dialog).getByRole("button", { name: `Close ${title} full view` }));
  expect(document.activeElement).toBe(expand);
  expect(screen.getAllByText("Complete evidence and metadata")).toHaveLength(1);
});
