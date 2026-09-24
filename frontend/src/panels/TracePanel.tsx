import type { DecisionTraceSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

/** Every changed request's decision, in the chronological order it was made. */
export function TracePanel({
  traces,
  planContext = null,
  selectedRequestId,
  onSelectRequest,
}: {
  traces: DecisionTraceSchema[];
  /** The replan these traces explain, named as the plan versions it ran between. */
  planContext?: string | null;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  return (
    <PanelFrame
      title="Decision trace"
      meta={
        [planContext, traces.length === 0 ? null : `${traces.length} entries`]
          .filter((part) => part !== null)
          .join(" · ") || undefined
      }
    >
      {traces.length === 0 ? (
        <p className="text-xs text-neutral-500">
          {planContext === null
            ? "Replan to see why each request moved, was inserted, or was dropped."
            : "This replan changed no request, so it recorded no decision traces."}
        </p>
      ) : (
        <ol aria-label="Decision trace" className="text-xs">
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
                  className={`grid w-full grid-cols-[4.5rem_auto_minmax(0,1fr)] items-baseline gap-x-2 border-b border-l-2 border-b-white/[0.03] px-2 py-0.5 text-left disabled:cursor-default ${
                    requestId === null ? "" : "cursor-pointer hover:bg-white/[0.04]"
                  } ${selected ? "border-l-fuchsia-400 bg-fuchsia-400/10" : "border-l-transparent"}`}
                >
                  <span className="truncate text-neutral-200">{trace.request_id}</span>
                  <span className="rounded-sm bg-amber-500/10 px-1 text-[10px] text-amber-400">
                    {trace.reason_code}
                  </span>
                  <span className="text-[11px] text-neutral-400">{trace.message}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </PanelFrame>
  );
}
