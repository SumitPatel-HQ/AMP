import type { DecisionTraceSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

/** Every changed request's decision, in the chronological order it was made. */
export function TracePanel({
  traces,
  selectedRequestId,
  onSelectRequest,
}: {
  traces: DecisionTraceSchema[];
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  return (
    <PanelFrame title="Decision trace">
      {traces.length === 0 ? (
        <p className="text-sm text-neutral-500">
          Replan to see why each request moved, was inserted, or was dropped.
        </p>
      ) : (
        <ol aria-label="Decision trace" className="space-y-2 text-sm">
          {traces.map((trace) => {
            const selected =
              trace.request_id !== null && trace.request_id === selectedRequestId;
            const requestId = trace.request_id;
            return (
              <li key={trace.id}>
                <button
                  type="button"
                  disabled={requestId === null}
                  aria-pressed={requestId === null ? undefined : selected}
                  data-request-id={requestId ?? undefined}
                  data-selected={selected ? "true" : undefined}
                  onClick={() => onSelectRequest(selected ? null : requestId)}
                  className={`w-full rounded border p-2 text-left disabled:cursor-default ${
                    requestId === null ? "" : "cursor-pointer"
                  } ${selected ? "border-fuchsia-400 bg-neutral-900" : "border-neutral-800"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-neutral-200">{trace.request_id}</span>
                    <span className="font-mono text-xs text-amber-400">
                      {trace.reason_code}
                    </span>
                  </div>
                  <p className="text-neutral-400">{trace.message}</p>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </PanelFrame>
  );
}
