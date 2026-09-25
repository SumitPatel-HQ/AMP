import type { MetricsSchema, MissionPlanSchema, PlanDiffSchema } from "../api/client";
import {
  metricsSubject,
  metricsView,
  type MetricRow,
  type MetricTrend,
  type MetricsView,
} from "../state/metricsView";
import { planLabel } from "../state/planContext";
import { clockTime, fullTime } from "./format";
import { PanelFrame } from "./PanelFrame";

const TREND_STYLE: Record<MetricTrend, string> = {
  better: "text-emerald-400",
  worse: "text-red-400",
  same: "text-neutral-500",
};

function DeltaCell({ row }: { row: MetricRow }) {
  if (row.delta === null) {
    return null;
  }
  return (
    <>
      <span
        data-trend={row.trend ?? undefined}
        className={row.trend === null ? "text-neutral-300" : TREND_STYLE[row.trend]}
      >
        {row.delta}
      </span>
      {row.deltaNote === null ? null : (
        <span className="ml-1 text-[10px] text-amber-400/80">{row.deltaNote}</span>
      )}
    </>
  );
}

/** The request pools the two plans were measured against, and which requests differ. */
function PoolMismatch({ view, label }: { view: MetricsView; label: (planId: string) => string }) {
  if (!view.pool.mismatch || view.beforePlanId === null) {
    return null;
  }
  const before = label(view.beforePlanId);
  const after = label(view.afterPlanId);
  const differences = [
    ...view.pool.onlyBefore.map((id) => `${id} only in ${before}`),
    ...view.pool.onlyAfter.map((id) => `${id} only in ${after}`),
  ];
  return (
    <p role="alert" className="mb-1 text-[11px] text-red-400">
      {`${before} and ${after} were measured against different request pools (${view.pool.before} vs ${view.pool.after} requests`}
      {differences.length === 0 ? ")" : `: ${differences.join(", ")})`}
      . Utility and completion changes are not like for like.
    </p>
  );
}

/**
 * How well the current plan does, and after a replan whether it did better
 * than the plan it replaced. Every value is the backend's metric for a named
 * plan version; battery and storage read the mission state at the instant the
 * backend measured, so they are shown once rather than per plan.
 */
export function MetricsPanel({
  currentPlanId,
  metrics,
  diff,
  plans = [],
}: {
  currentPlanId: string | null;
  /** The current plan's own metrics. */
  metrics: MetricsSchema | null;
  /** The last replan's comparison; used only while its revised plan is current. */
  diff: PlanDiffSchema | null;
  /** The plan versions the session holds, so columns name them as V1, V2. */
  plans?: readonly MissionPlanSchema[];
}) {
  const subject = metricsSubject(currentPlanId, metrics, diff);
  if (subject === null) {
    return (
      <PanelFrame title="Mission evaluation">
        <p className="text-xs text-neutral-500">Generate a plan to evaluate it.</p>
      </PanelFrame>
    );
  }

  const view = metricsView(subject);
  const label = (planId: string) => planLabel(planId, plans);
  const comparing = view.beforePlanId !== null;
  const versions =
    view.beforePlanId === null
      ? label(view.afterPlanId)
      : `${label(view.beforePlanId)} → ${label(view.afterPlanId)}`;

  return (
    <PanelFrame
      title="Mission evaluation"
      meta={`${versions} · measured ${clockTime(view.measuredAt)} UTC`}
    >
      <PoolMismatch view={view} label={label} />
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-neutral-500">
            <th className="py-0.5 font-normal">Metric</th>
            {view.beforePlanId === null ? null : (
              <th className="py-0.5 font-normal" title={view.beforePlanId}>
                {label(view.beforePlanId)}
              </th>
            )}
            <th className="py-0.5 font-normal" title={view.afterPlanId}>
              {label(view.afterPlanId)}
            </th>
            {comparing ? <th className="py-0.5 font-normal">Δ</th> : null}
          </tr>
        </thead>
        <tbody>
          {view.rows.map((row) => (
            <tr key={row.key} title={row.hint}>
              <td className="py-px pr-3 text-neutral-400">{row.label}</td>
              {row.before === null ? null : (
                <td className="py-px pr-3 tabular-nums text-neutral-400">{row.before}</td>
              )}
              <td
                className={`py-px pr-3 tabular-nums ${row.warn ? "text-amber-300" : "text-neutral-100"}`}
              >
                {row.after}
              </td>
              {comparing ? (
                <td className="py-px tabular-nums">
                  <DeltaCell row={row} />
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
      <p
        aria-label="Mission state readings"
        title={`Read from the mission state at ${fullTime(view.measuredAt)}, not from either plan`}
        className="mt-1 border-t border-white/[0.04] pt-1 text-[11px] text-neutral-500"
      >
        {`Mission state at ${clockTime(view.measuredAt)} UTC: battery used ${view.resources.battery} · storage used ${view.resources.storage}`}
      </p>
      <p className="text-[11px] text-neutral-500">
        {view.pool.before === null || view.pool.before === view.pool.after
          ? `Request pool: ${view.pool.after} requests`
          : `Request pool: ${view.pool.before} → ${view.pool.after} requests`}
      </p>
    </PanelFrame>
  );
}
