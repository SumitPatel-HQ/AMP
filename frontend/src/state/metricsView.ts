import type { MetricsSchema, PlanDiffSchema } from "../api/client";

/**
 * A share as a whole percentage. Null is an empty denominator and reads N/A,
 * never 0%. A partial share never rounds to a full score or to nothing, so
 * 99.6% coverage cannot pass for every change being explained.
 */
export function formatPercent(value: number | null): string {
  if (value === null) {
    return "N/A";
  }
  const rounded = Math.round(value * 100);
  if (value < 1 && rounded >= 100) {
    return ">99%";
  }
  if (value > 0 && rounded <= 0) {
    return "<1%";
  }
  return `${rounded}%`;
}

/** The plans the metrics describe: the current plan and, after a replan, its parent. */
export interface MetricsSubject {
  before: MetricsSchema | null;
  after: MetricsSchema;
  requestPoolMismatch: boolean;
}

/**
 * Which metrics describe the current plan. The last replan's comparison speaks
 * for the plan only while that plan is still the one it produced; otherwise
 * the current plan's own metrics stand alone. Metrics fetched for any other
 * plan describe nothing on screen and are not shown.
 */
export function metricsSubject(
  currentPlanId: string | null,
  metrics: MetricsSchema | null,
  diff: PlanDiffSchema | null,
): MetricsSubject | null {
  if (currentPlanId === null) {
    return null;
  }
  const before = diff?.metrics_before ?? null;
  const after = diff?.metrics_after ?? null;
  if (before !== null && after !== null && after.plan_id === currentPlanId) {
    return { before, after, requestPoolMismatch: diff?.request_pool_mismatch ?? false };
  }
  if (metrics === null || metrics.plan_id !== currentPlanId) {
    return null;
  }
  return { before: null, after: metrics, requestPoolMismatch: false };
}

export type MetricKey =
  | "utility"
  | "completion"
  | "violations"
  | "churn"
  | "coverage"
  | "planning-time";

export type MetricTrend = "better" | "worse" | "same";

export interface MetricRow {
  key: MetricKey;
  label: string;
  /** What the metric measures, for a hover hint. */
  hint: string;
  /** Null when only one plan is described. */
  before: string | null;
  after: string;
  /** Signed change from before to after, or null where no delta applies. */
  delta: string | null;
  /** Whether the change is an improvement; null where that cannot be judged. */
  trend: MetricTrend | null;
  /** Why the delta cannot be read at face value. */
  deltaNote: string | null;
  /** The described plan's value needs attention on its own, delta or not. */
  warn: boolean;
}

export interface MetricsView {
  beforePlanId: string | null;
  afterPlanId: string;
  /** The simulated instant the backend read the mission state at. */
  measuredAt: string;
  rows: MetricRow[];
  /** Mission-state readings: the same for every plan measured at one instant. */
  resources: { battery: string; storage: string };
  pool: {
    before: number | null;
    after: number;
    mismatch: boolean;
    onlyBefore: string[];
    onlyAfter: string[];
  };
}

function formatCount(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function signed(value: number, unit = ""): string {
  if (value === 0) {
    return `±0${unit}`;
  }
  return `${value > 0 ? "+" : "-"}${formatCount(Math.abs(value))}${unit}`;
}

function trendOf(change: number, higherIsBetter: boolean): MetricTrend {
  if (change === 0) {
    return "same";
  }
  return change > 0 === higherIsBetter ? "better" : "worse";
}

/** Completion divides by the request pool, so an empty pool has no rate. */
function completion(metrics: MetricsSchema): number | null {
  return metrics.request_pool_size === 0 ? null : metrics.completion_rate;
}

function formatCompletion(metrics: MetricsSchema): string {
  const rate = completion(metrics);
  return rate === null ? "N/A" : `${formatPercent(rate)} of ${metrics.request_pool_size}`;
}

interface RowSpec {
  key: MetricKey;
  label: string;
  hint: string;
  format: (metrics: MetricsSchema) => string;
  /** The value a delta is taken over, or undefined for a metric with no delta. */
  value?: (metrics: MetricsSchema) => number | null;
  higherIsBetter?: boolean;
  deltaUnit?: string;
  /** The value depends on which requests are in the pool. */
  poolDependent?: boolean;
  warn?: (metrics: MetricsSchema) => boolean;
}

const ROWS: RowSpec[] = [
  {
    key: "utility",
    label: "Mission utility",
    hint: "Summed priority of the requests the plan schedules or has completed",
    format: (metrics) => formatCount(metrics.mission_utility),
    value: (metrics) => metrics.mission_utility,
    higherIsBetter: true,
    poolDependent: true,
  },
  {
    key: "completion",
    label: "Completion",
    hint: "Completed requests over the plan's request pool, expired requests included",
    format: formatCompletion,
    value: (metrics) => {
      const rate = completion(metrics);
      return rate === null ? null : Math.round(rate * 100);
    },
    higherIsBetter: true,
    deltaUnit: " pp",
    poolDependent: true,
  },
  {
    key: "violations",
    label: "Violations",
    hint: "Scheduled actions that break a constraint",
    format: (metrics) => String(metrics.violation_count),
    value: (metrics) => metrics.violation_count,
    higherIsBetter: false,
    warn: (metrics) => metrics.violation_count > 0,
  },
  {
    key: "churn",
    label: "Plan churn",
    hint: "Changed unfrozen actions over the parent plan's unfrozen actions; N/A without a parent",
    format: (metrics) => formatPercent(metrics.plan_churn),
  },
  {
    key: "coverage",
    label: "Explanation coverage",
    hint: "Changed actions carrying a decision trace over changed actions; N/A when nothing changed",
    format: (metrics) => formatPercent(metrics.explanation_coverage),
    warn: (metrics) =>
      metrics.explanation_coverage !== null && metrics.explanation_coverage < 1,
  },
  {
    key: "planning-time",
    label: "Planning time",
    hint: "Wall-clock time the planner took to build the plan",
    format: (metrics) => `${metrics.planning_time_ms.toFixed(1)} ms`,
  },
];

function buildRow(
  spec: RowSpec,
  before: MetricsSchema | null,
  after: MetricsSchema,
  poolsDiffer: boolean,
): MetricRow {
  const base = {
    key: spec.key,
    label: spec.label,
    hint: spec.hint,
    before: before === null ? null : spec.format(before),
    after: spec.format(after),
    warn: spec.warn?.(after) ?? false,
  };
  const none = { ...base, delta: null, trend: null, deltaNote: null };
  if (before === null || spec.value === undefined) {
    return none;
  }
  const from = spec.value(before);
  const to = spec.value(after);
  if (from === null || to === null) {
    return none;
  }
  const change = to - from;
  // Over different pools the change is real but not like for like, so it is
  // shown without being called an improvement or a regression.
  const unjudged = spec.poolDependent === true && poolsDiffer;
  return {
    ...base,
    delta: signed(change, spec.deltaUnit),
    trend: unjudged ? null : trendOf(change, spec.higherIsBetter ?? true),
    deltaNote: unjudged ? "pools differ" : null,
  };
}

/**
 * The metrics panel's content, read straight from the backend's metrics.
 * Nothing is recomputed: the view only formats values, takes before/after
 * deltas, and names the requests one pool holds that the other does not.
 */
export function metricsView({ before, after, requestPoolMismatch }: MetricsSubject): MetricsView {
  const beforeIds = new Set(before?.request_pool_ids ?? []);
  const afterIds = new Set(after.request_pool_ids);
  return {
    beforePlanId: before?.plan_id ?? null,
    afterPlanId: after.plan_id,
    measuredAt: after.measured_at,
    rows: ROWS.map((spec) => buildRow(spec, before, after, requestPoolMismatch)),
    resources: {
      battery: formatPercent(after.battery_utilisation),
      storage: formatPercent(after.storage_utilisation),
    },
    pool: {
      before: before?.request_pool_size ?? null,
      after: after.request_pool_size,
      mismatch: requestPoolMismatch,
      onlyBefore:
        before === null ? [] : before.request_pool_ids.filter((id) => !afterIds.has(id)),
      onlyAfter:
        before === null ? [] : after.request_pool_ids.filter((id) => !beforeIds.has(id)),
    },
  };
}
