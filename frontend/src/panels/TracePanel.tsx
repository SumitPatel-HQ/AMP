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
    <PanelFrame
      title="Decision trace"
      meta={traces.length === 0 ? undefined : `${traces.length} entries`}
    >
      {traces.length === 0 ? (
        <p className="text-xs text-neutral-500">
          Replan to see why each request moved, was inserted, or was dropped.
        </p>
      ) : (
        <ol aria-label="Decision trace" className="space-y-1 text-xs">
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
                  className={`w-full border-l-2 px-2 py-1 text-left disabled:cursor-default ${
                    requestId === null ? "" : "cursor-pointer"
                  } ${selected ? "border-fuchsia-400 bg-fuchsia-400/10" : "border-neutral-700"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-neutral-200">{trace.request_id}</span>
                    <span className="font-mono text-[10px] text-amber-400">
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
