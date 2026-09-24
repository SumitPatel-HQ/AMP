import type { ImpactSchema, MissionEventSchema, MissionPlanSchema } from "../api/client";
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
  requestId: string;
  kind: ImpactKind;
  reasons: string[];
}

/**
 * The impact's action ids, read back to requests through the plan the event
 * evaluated. That plan, not whichever is current, owns those actions.
 */
function impactRows(impact: ImpactSchema, evaluatedPlan: MissionPlanSchema | undefined): ImpactRow[] {
  const row = (actionId: string, kind: ImpactKind): ImpactRow => ({
    actionId,
    requestId:
      evaluatedPlan?.actions.find((action) => action.id === actionId)?.request_id ?? actionId,
    kind,
    reasons: impact.reason_codes[actionId] ?? [],
  });
  return [
    ...impact.invalid_unfrozen_action_ids.map((id) => row(id, "invalid")),
    ...impact.frozen_action_ids.map((id) => row(id, "frozen")),
    ...impact.valid_unfrozen_action_ids.map((id) => row(id, "valid")),
  ];
}

/** The persisted impact of the last injected event on the plan it evaluated. */
export function ImpactPanel({
  impact,
  events,
  plans,
  earlier,
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
}) {
  if (impact === null) {
    return (
      <PanelFrame title="Impact">
        <p className="text-xs text-neutral-500">
          No event yet. Use Event in the mission bar to inject a cloud block; its impact on the
          current plan appears here.
        </p>
      </PanelFrame>
    );
  }

  const evaluatedPlan = plans.find((candidate) => candidate.id === impact.evaluated_plan_id);
  const event = events.find((candidate) => candidate.id === impact.event_id);
  const rows = impactRows(impact, evaluatedPlan);

  return (
    <PanelFrame
      title="Impact"
      meta={`${impact.event_id} on ${planLabel(impact.evaluated_plan_id, plans)}${
        earlier ? " · earlier transition" : ""
      }`}
      bodyClassName="flex flex-col"
    >
      <p className="shrink-0 border-b border-[var(--amis-border)] px-2 py-1 text-[11px] text-neutral-400">
        {event === undefined ? (
          impact.event_id
        ) : (
          <>
            <span className="text-red-300">{`${event.event_type} · ${event.id}`}</span>
            {` · ${event.payload.request_id} / ${event.payload.window_id} · ${clockTime(event.event_time)} UTC`}
          </>
        )}
        <span className="text-neutral-600">{` · evaluated ${shortPlanId(impact.evaluated_plan_id)}`}</span>
        {earlier ? (
          <span className="block text-amber-300/80">
            A later replan has superseded the plan this event evaluated.
          </span>
        ) : null}
      </p>
      <div className="min-h-0 flex-1 overflow-auto">
        {rows.length === 0 ? (
          <p className="px-2 py-1.5 text-xs text-neutral-500">The evaluated plan had no actions.</p>
        ) : (
          <ul aria-label="Event impact" className="text-xs">
            {rows.map((row) => (
              <li
                key={row.actionId}
                data-impact={row.kind}
                className={`grid grid-cols-[4.5rem_5rem_minmax(0,1fr)] gap-x-2 border-b border-white/[0.03] px-2 py-0.5 ${
                  row.kind === "invalid" ? "bg-red-500/[0.06]" : ""
                }`}
              >
                <span className={row.kind === "invalid" ? "font-semibold text-neutral-100" : "text-neutral-300"}>
                  {row.requestId}
                </span>
                <span className={`text-[10px] uppercase tracking-wide ${KIND_STYLE[row.kind].className}`}>
                  {KIND_STYLE[row.kind].label}
                </span>
                <span className="truncate text-[10px] text-neutral-400">
                  {row.reasons.length === 0 ? row.actionId : row.reasons.join(", ")}
                </span>
              </li>
            ))}
          </ul>
        )}
        {impact.invalid_unfrozen_action_ids.length === 0 ? (
          <p className="px-2 py-1 text-xs text-emerald-400">No scheduled actions became invalid.</p>
        ) : null}
      </div>
    </PanelFrame>
  );
}
