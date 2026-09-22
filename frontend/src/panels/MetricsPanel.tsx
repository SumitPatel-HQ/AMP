import type { MetricsSchema, PlanDiffSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

function formatPercent(value: number | null): string {
  return value === null ? "N/A" : `${(value * 100).toFixed(0)}%`;
}

interface MetricRow {
  label: string;
  before: string;
  after: string;
}

/**
 * completion_rate divides by request_pool_size, so the count sits beside the
 * rate rather than in a separate row a reviewer has to cross-reference.
 */
function buildRows(before: MetricsSchema, after: MetricsSchema): MetricRow[] {
  return [
    {
      label: "Mission utility",
      before: before.mission_utility.toFixed(1),
      after: after.mission_utility.toFixed(1),
    },
    {
      label: "Completion rate",
      before: `${formatPercent(before.completion_rate)} (of ${before.request_pool_size})`,
      after: `${formatPercent(after.completion_rate)} (of ${after.request_pool_size})`,
    },
    {
      label: "Violations",
      before: before.violation_count.toFixed(0),
      after: after.violation_count.toFixed(0),
    },
    {
      label: "Planning time",
      before: `${before.planning_time_ms.toFixed(1)} ms`,
      after: `${after.planning_time_ms.toFixed(1)} ms`,
    },
    {
      label: "Battery used",
      before: formatPercent(before.battery_utilisation),
      after: formatPercent(after.battery_utilisation),
    },
    {
      label: "Storage used",
      before: formatPercent(before.storage_utilisation),
      after: formatPercent(after.storage_utilisation),
    },
    {
      label: "Plan churn",
      before: formatPercent(before.plan_churn),
      after: formatPercent(after.plan_churn),
    },
    {
      label: "Explanation coverage",
      before: formatPercent(before.explanation_coverage),
      after: formatPercent(after.explanation_coverage),
    },
    {
      label: "Request pool",
      before: `${before.request_pool_size} requests`,
      after: `${after.request_pool_size} requests`,
    },
  ];
}

/** The initial and revised plan versions, compared metric by metric. */
export function MetricsPanel({ diff }: { diff: PlanDiffSchema | null }) {
  const before = diff?.metrics_before ?? null;
  const after = diff?.metrics_after ?? null;

  if (before === null || after === null) {
    return (
      <PanelFrame title="Metrics">
        <p className="text-sm text-neutral-500">Replan to compare plan metrics.</p>
      </PanelFrame>
    );
  }

  return (
    <PanelFrame title="Metrics">
      {diff?.request_pool_mismatch ? (
        <p role="alert" className="text-sm text-red-400">
          These two plans were measured against different request pools; the
          comparison above is not apples to apples.
        </p>
      ) : null}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-widest text-neutral-500">
            <th className="py-1 font-normal">Metric</th>
            <th className="py-1 font-normal">Before</th>
            <th className="py-1 font-normal">After</th>
          </tr>
        </thead>
        <tbody>
          {buildRows(before, after).map((row) => (
            <tr key={row.label}>
              <td className="py-1 pr-3 text-neutral-500">{row.label}</td>
              <td className="py-1 pr-3 font-mono text-neutral-200">{row.before}</td>
              <td className="py-1 font-mono text-neutral-200">{row.after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </PanelFrame>
  );
}
