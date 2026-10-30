import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useDialogHistory } from "./useDialogHistory";
function Harness() {
 const n = useDialogHistory();
 return <div onKeyDown={e => { if(e.key === "Escape") n.close(); }}><output>{n.view ?? "dashboard"}</output><button onClick={() => n.open("settings")}>Settings</button><button onClick={() => n.open("builder")}>New</button><button onClick={n.close}>Cancel</button><button onClick={n.complete}>Created</button></div>;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function move(direction: "back" | "forward") {
 await act(async () => { await new Promise<void>(resolve => { window.addEventListener("popstate", () => resolve(), {once:true}); history[direction](); }); });
}
const view = () => screen.getByRole("status").textContent;
it("Back, Forward, Escape and Cancel preserve the sequence without duplicates", async () => {
 render(<Harness/>); const push = vi.spyOn(history,"pushState");
 fireEvent.click(screen.getByText("Settings")); fireEvent.click(screen.getByText("New")); fireEvent.click(screen.getByText("New"));
 expect(push).toHaveBeenCalledTimes(2);
 await move("back"); expect(view()).toBe("settings");
 await move("forward"); expect(view()).toBe("builder");
 fireEvent.keyDown(screen.getByText("Cancel"),{key:"Escape"}); await waitFor(() => expect(view()).toBe("settings"));
 fireEvent.click(screen.getByText("Cancel")); fireEvent.click(screen.getByText("Cancel")); await waitFor(() => expect(view()).toBe("dashboard"));
 expect(push).toHaveBeenCalledTimes(2);
});
it("creation returns to dashboard and invalidates submitted dialogs", async () => {
 render(<Harness/>); fireEvent.click(screen.getByText("Settings")); fireEvent.click(screen.getByText("New"));
 await act(async () => { const popped = new Promise<void>(resolve => window.addEventListener("popstate", () => resolve(),{once:true})); fireEvent.click(screen.getByText("Created")); await popped; });
 expect(view()).toBe("dashboard"); await move("forward"); expect(view()).toBe("dashboard");
});
it("dashboard dismissal does not intercept browser history", () => {
 render(<Harness/>); const back = vi.spyOn(history,"back"); fireEvent.click(screen.getByText("Cancel")); expect(back).not.toHaveBeenCalled();
});
