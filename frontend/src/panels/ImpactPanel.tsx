import type { ImpactSchema, MissionEventSchema, MissionPlanSchema } from "../api/client";
import { eventSummary } from "../state/missionEvent";
import { planLabel } from "../state/planContext";
import { clockTime, shortPlanId } from "./format";
import { PanelFrame } from "./PanelFrame";

type ImpactKind = "invalid" | "frozen" | "valid";

const KIND_STYLE: Record<ImpactKind, { label: string; className: string }> = {
  invalid: { label: "invalid", className: "text-red-400" },
  frozen: { label: "frozen", className: "text-neutral-400" },
  valid: { label: "still valid", className: "text-emerald-400" },
};

interface ImpactRow {
  actionId: string;
  /** Null when the evaluated plan is not one the session holds. */
  requestId: string | null;
  windowId: string | null;
  kind: ImpactKind;
  reasons: string[];
}

/**
 * The impact's action ids, read back to requests and windows through the plan
 * the event evaluated. That plan, not whichever is current, owns those actions.
 */
function impactRows(impact: ImpactSchema, evaluatedPlan: MissionPlanSchema | undefined): ImpactRow[] {
  const row = (actionId: string, kind: ImpactKind): ImpactRow => {
    const action = evaluatedPlan?.actions.find((candidate) => candidate.id === actionId);
    return {
      actionId,
      requestId: action?.request_id ?? null,
      windowId: action?.window_id ?? null,
      kind,
      reasons: impact.reason_codes[actionId] ?? [],
    };
  };
  return [
    ...impact.invalid_unfrozen_action_ids.map((id) => row(id, "invalid")),
    ...impact.frozen_action_ids.map((id) => row(id, "frozen")),
    ...impact.valid_unfrozen_action_ids.map((id) => row(id, "valid")),
  ];
}

/**
 * The persisted impact of the last injected event on the plan it evaluated:
 * what became invalid because of the disruption. What changed after a replan
 * is the plan comparison's job, not this panel's.
 */
export function ImpactPanel({
  impact,
  events,
  plans,
  earlier,
  selectedRequestId,
  selectedWindowId = null,
  selectedEventId = null,
  onSelectRequest,
  onSelectWindow,
  onSelectEvent,
  className,
}: {
  impact: ImpactSchema | null;
  events: MissionEventSchema[];
  /** The plan versions the session holds, to name and read the evaluated plan. */
  plans: readonly MissionPlanSchema[];
  /**
   * The impact belongs to a plan a later replan has already moved past, so it
   * is no longer part of the transition the rest of the workspace shows.
   */
  earlier: boolean;
  selectedRequestId: string | null;
  selectedWindowId?: string | null;
  selectedEventId?: string | null;
  onSelectRequest: (requestId: string | null) => void;
  onSelectWindow?: (windowId: string | null) => void;
  onSelectEvent?: (eventId: string | null) => void;
  className?: string;
}) {
  if (impact === null) {
    return (
      <PanelFrame title="Impact" className={className}>
        <p className="text-xs text-neutral-500">
          No event yet. Use Event in the mission bar to inject a cloud block, battery drop or
          emergency request; what it invalidates in the current plan appears here.
        </p>
      </PanelFrame>
    );
  }

  const evaluatedPlan = plans.find((candidate) => candidate.id === impact.evaluated_plan_id);
  const event = events.find((candidate) => candidate.id === impact.event_id);
  const rows = impactRows(impact, evaluatedPlan);
  const evaluatedLabel = planLabel(impact.evaluated_plan_id, plans);

  return (
    <PanelFrame
      title="Impact"
      meta={`${impact.event_id} on ${evaluatedLabel}${earlier ? " · earlier transition" : ""}`}
      bodyClassName="flex flex-col"
      className={className}
    >
      <div className="shrink-0 border-b border-[var(--amis-border)] px-2 py-1 text-[11px] text-neutral-400">
        <p aria-label="Impact event">
          {event === undefined ? (
            impact.event_id
          ) : (
            <>
              <span className="text-red-300">{`${event.event_type} · ${event.id}`}</span>
              {` · ${eventSummary(event)} · ${clockTime(event.event_time)} UTC`}
            </>
          )}
        </p>
        {onSelectEvent === undefined ? null : (
          <button
            type="button"
            aria-pressed={selectedEventId === impact.event_id}
            onClick={() => onSelectEvent(selectedEventId === impact.event_id ? null : impact.event_id)}
            className="text-rose-300 hover:text-rose-100"
          >
            Follow event {impact.event_id}
          </button>
        )}
        <p className="text-neutral-500">
          {`What became invalid in ${evaluatedLabel} because of this event · `}
          <span className="text-neutral-600" title={impact.evaluated_plan_id}>
            {`evaluated ${shortPlanId(impact.evaluated_plan_id)} · ${impact.id}`}
          </span>
        </p>
        {earlier ? (
          <p className="text-amber-300/80">
            A later replan has superseded the plan this event evaluated.
          </p>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {rows.length === 0 ? (
          <p className="px-2 py-1.5 text-xs text-neutral-500">The evaluated plan had no actions.</p>
        ) : (
          <ul aria-label="Event impact" className="text-xs">
            {rows.map((row) => {
              const selected = row.windowId !== null
                ? row.windowId === selectedWindowId
                : row.requestId !== null && row.requestId === selectedRequestId;
              const related = !selected && row.requestId !== null && row.requestId === selectedRequestId;
              return (
                <li key={row.actionId} data-impact={row.kind}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    disabled={row.requestId === null}
                    onClick={() => {
                      if (selected) onSelectRequest(null);
                      else if (row.windowId !== null && onSelectWindow !== undefined) onSelectWindow(row.windowId);
                      else onSelectRequest(row.requestId);
                    }}
                    title={`${row.actionId}${row.windowId === null ? "" : ` · ${row.windowId}`}`}
                    className={`grid w-full grid-cols-[5.5rem_4.5rem_minmax(0,1fr)] gap-x-2 border-b border-l-2 border-b-white/[0.03] px-2 py-0.5 text-left enabled:hover:bg-white/[0.04] ${
                      selected ? "border-l-fuchsia-400 bg-fuchsia-400/10" : related ? "border-l-fuchsia-900" : "border-l-transparent"
                    } ${row.kind === "invalid" && !selected ? "bg-red-500/[0.06]" : ""}`}
                  >
                    <span
                      className={`truncate ${
                        row.kind === "invalid" ? "font-semibold text-neutral-100" : "text-neutral-300"
                      }`}
                    >
                      {row.requestId ?? row.actionId}
                    </span>
                    <span className={`text-[10px] uppercase tracking-wide ${KIND_STYLE[row.kind].className}`}>
                      {KIND_STYLE[row.kind].label}
                    </span>
                    <span className="truncate text-[10px] text-neutral-400">
                      {[row.reasons.join(", "), row.actionId, row.windowId]
                        .filter((part) => part !== null && part !== "")
                        .join(" · ")}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {impact.invalid_unfrozen_action_ids.length === 0 ? (
          <p className="px-2 py-1 text-xs text-emerald-400">No scheduled actions became invalid.</p>
        ) : null}
      </div>
    </PanelFrame>
  );
}
