import { useMemo, useState } from "react";
import type { ObservationWindowSchema, ScenarioSchema } from "../api/client";
import { CONTROL_BUTTON, CONTROL_INPUT } from "./controls";

/** Request then window, then inject: the cloud-block event the API accepts. */
export function CloudBlockControl({
  scenario,
  windows,
  loading,
  onInjectCloudBlock,
}: {
  scenario: ScenarioSchema;
  windows: ObservationWindowSchema[];
  loading: boolean;
  onInjectCloudBlock: (requestId: string, windowId: string) => void;
}) {
  const [requestId, setRequestId] = useState("");
  const [windowId, setWindowId] = useState("");

  const windowsForRequest = useMemo(
    () => windows.filter((window) => window.request_id === requestId),
    [windows, requestId],
  );

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[10px] uppercase tracking-wider text-neutral-500">
        Cloud block event
      </h3>
      <div className="flex flex-wrap items-center gap-1.5">
        <select
          aria-label="Request"
          value={requestId}
          onChange={(event) => {
            setRequestId(event.target.value);
            setWindowId("");
          }}
          className={CONTROL_INPUT}
        >
          <option value="">Select request</option>
          {scenario.requests.map((request) => (
            <option key={request.id} value={request.id}>
              {request.id}
            </option>
          ))}
        </select>
        <select
          aria-label="Window"
          value={windowId}
          onChange={(event) => setWindowId(event.target.value)}
          disabled={requestId === ""}
          className={`${CONTROL_INPUT} max-w-72`}
        >
          <option value="">Select window</option>
          {windowsForRequest.map((window) => (
            <option key={window.id} value={window.id}>
              {window.id} ({window.start}–{window.end}
              {window.valid ? "" : ", invalid"})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => onInjectCloudBlock(requestId, windowId)}
          disabled={loading || requestId === "" || windowId === ""}
          className={CONTROL_BUTTON}
        >
          Inject cloud block
        </button>
      </div>
    </div>
  );
}
