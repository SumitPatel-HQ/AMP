import type { MissionPlanSchema, PlanChangeType } from "../api/client";
import {
  comparisonMeta,
  comparisonRows,
  comparisonSummary,
  isChangedDecision,
  type PlanComparisonRow,
} from "../state/planComparison";
import { planLabel } from "../state/planContext";
import type { ReplanResult } from "../state/types";
import { fullTime } from "./format";
import { PanelFrame } from "./PanelFrame";

const CHANGE_STYLE: Record<PlanChangeType, string> = {
  MOVED: "text-sky-300",
  INSERTED: "text-emerald-300",
  DROPPED: "text-red-400",
  COMPLETED: "text-neutral-400",
  UNCHANGED: "text-neutral-500",
};

/**
 * Old → new placement, with an em dash wherever the backend records no time.
 * A row the backend reports at one placement on both sides (a completed
 * action) names it once instead of drawing a redundant arrow.
 */
function placement(row: PlanComparisonRow): string {
  const sameStart = row.oldStart !== null && row.oldStart === row.newStart;
  const starts = sameStart
    ? fullTime(row.oldStart)
    : `${row.oldStart === null ? "—" : fullTime(row.oldStart)} → ${row.newStart === null ? "—" : fullTime(row.newStart)}`;
  if (row.oldWindowId === null && row.newWindowId === null) {
    return starts;
  }
  const windows =
    row.oldWindowId !== null && row.oldWindowId === row.newWindowId
      ? row.oldWindowId
      : `${row.oldWindowId ?? "—"} → ${row.newWindowId ?? "—"}`;
  return `${starts} · ${windows}`;
}

/**
 * The trace line for a row. A trace the backend linked to an event names it;
 * a trace without one is a planning decision, not an event response. Rows
 * without a trace say so instead of implying an explanation exists.
 */
function TraceLine({ row }: { row: PlanComparisonRow }) {
  if (row.trace === null) {
    return (
      <span className="text-[11px] text-neutral-500">
        {row.changeType === "COMPLETED"
          ? "Completed by the mission clock, not a replan decision, so no trace."
          : row.changeType === "UNCHANGED"
            ? "Unchanged, so the backend recorded no decision trace."
            : "No decision trace recorded for this change."}
      </span>
    );
  }
  const origin =
    row.traceEventId === null
      ? "planning decision · no triggering event"
      : `decision for ${row.traceEventId}`;
  return (
    <span className="text-[11px] text-neutral-400">
      <span className="text-neutral-300">{row.trace.message}</span>
      <span className="text-neutral-500">
        {` · ${row.trace.id} · ${origin}`}
        {row.trace.constraint_name === null ? "" : ` · ${row.trace.constraint_name}`}
      </span>
    </span>
  );
}

function ComparisonRowButton({
  row,
  selected,
  quiet,
  onPick,
}: {
  row: PlanComparisonRow;
  selected: boolean;
  /** Unchanged and completed rows render dimmer so changed rows dominate. */
  quiet: boolean;
  onPick: (row: PlanComparisonRow) => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      data-request-id={row.requestId}
      data-change={row.changeType}
      data-selected={selected ? "true" : undefined}
      onClick={() => onPick(row)}
      className={`grid w-full grid-cols-[4.5rem_auto_minmax(0,1fr)] items-baseline gap-x-2 border-b border-l-2 border-b-white/[0.03] px-2 py-1 text-left hover:bg-white/[0.04] ${
        selected ? "border-l-fuchsia-400 bg-fuchsia-400/10" : "border-l-transparent"
      } ${quiet ? "opacity-55" : ""}`}
    >
      <span className={`truncate font-semibold ${quiet ? "text-neutral-400" : "text-neutral-100"}`}>
        {row.requestId}
      </span>
      <span className={`text-[10px] font-semibold uppercase tracking-wide ${CHANGE_STYLE[row.changeType]}`}>
        {row.changeType}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[11px] text-neutral-300">
          {placement(row)}
          {row.newlyArrivedUnscheduled ? (
            <span className="text-amber-300"> · new in pool · still unscheduled</span>
          ) : null}
        </span>
        <span className="block truncate text-[11px]">
          <span className="text-neutral-400">{row.reasonLabel}</span>
          <span className="ml-1 rounded-sm bg-amber-500/10 px-1 text-[10px] text-amber-400">
            {row.reasonCode}
          </span>
        </span>
        <span className="block">
          <TraceLine row={row} />
        </span>
      </span>
    </button>
  );
}

/**
 * What replanning changed between two immutable plan versions, and why: every
 * backend diff entry with its old/new placement, canonical reason code and the
 * decision trace the backend paired with it. Impact (what the event
 * invalidated) stays in its own panel; this surface is what changed after the
 * replan. Selecting a row follows the shared selection, so the timeline group
 * and item plus the map target highlight together.
 */
export function PlanComparisonPanel({
  replanResult,
  plans,
  selectedRequestId,
  onSelectRequest,
  onSelectWindow,
}: {
  replanResult: ReplanResult | null;
  plans: readonly MissionPlanSchema[];
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow: (windowId: string | null) => void;
}) {
  if (replanResult === null) {
    return (
      <PanelFrame title="Plan comparison">
        <p className="text-xs text-neutral-500">
          Replan to compare plan versions. Each changed request shows its previous
          placement, new placement, change classification and the backend reason.
        </p>
      </PanelFrame>
    );
  }
  const rows = comparisonRows(replanResult);
  const summary = comparisonSummary(rows);
  const changed = rows.filter((row) => isChangedDecision(row.changeType));
  const completed = rows.filter((row) => row.changeType === "COMPLETED");
  const unchanged = rows.filter((row) => row.changeType === "UNCHANGED");
  const context = `${planLabel(replanResult.initialPlan.id, plans)} → ${planLabel(replanResult.revisedPlan.id, plans)}`;

  // The request carries the map and timeline-group highlight; the window, when
  // the plans name one, carries the timeline-item highlight. The window lookup
  // falls back to the request alone, so a dropped row still selects correctly.
  const onPick = (row: PlanComparisonRow) => {
    if (row.requestId === selectedRequestId) {
      onSelectRequest(null);
      return;
    }
    onSelectRequest(row.requestId);
    const focus = row.newWindowId ?? row.oldWindowId;
    if (focus !== null) {
      onSelectWindow(focus);
    }
  };

  return (
    <PanelFrame title="Plan comparison" meta={`${context} · ${comparisonMeta(summary)}`}>
      <p className="px-2 pb-1 text-[10px] text-neutral-600">
        What replanning changed. Impact, beside this panel, says what the event invalidated.
      </p>
      {changed.length === 0 ? (
        <p className="px-2 py-1 text-xs text-neutral-500">
          This replan changed no request, so it recorded no decision traces.
        </p>
      ) : (
        <ul aria-label="Plan comparison" className="text-xs">
          {changed.map((row) => (
            <li key={row.requestId} data-change={row.changeType}>
              <ComparisonRowButton
                row={row}
                selected={row.requestId === selectedRequestId}
                quiet={false}
                onPick={onPick}
              />
            </li>
          ))}
        </ul>
      )}
      {completed.length === 0 ? null : (
        <div className="mt-1 border-t border-white/[0.04] pt-1">
          <h3 className="px-2 text-[10px] uppercase tracking-widest text-neutral-600">
            Completed by the mission clock
          </h3>
          <ul aria-label="Completed plan entries" className="text-xs">
            {completed.map((row) => (
              <li key={row.requestId} data-change={row.changeType}>
                <ComparisonRowButton
                  row={row}
                  selected={row.requestId === selectedRequestId}
                  quiet
                  onPick={onPick}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
      {unchanged.length === 0 ? null : (
        <div className="mt-1 border-t border-white/[0.04] pt-1">
          <h3 className="px-2 text-[10px] uppercase tracking-widest text-neutral-600">
            Unchanged
          </h3>
          <ul aria-label="Unchanged plan entries" className="text-xs">
            {unchanged.map((row) => (
              <li key={row.requestId} data-change={row.changeType}>
                <ComparisonRowButton
                  row={row}
                  selected={row.requestId === selectedRequestId}
                  quiet
                  onPick={onPick}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
    </PanelFrame>
  );
}
