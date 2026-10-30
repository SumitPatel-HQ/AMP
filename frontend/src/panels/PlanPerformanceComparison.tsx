import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MetricsSubject, MetricsView } from "../state/metricsView";

/** One shared scale per metric; version colors do not encode a judgment. */
export function PlanPerformanceComparison({ subject, view, label }: { subject: MetricsSubject; view: MetricsView; label: (id: string) => string }) {
  const { before, after } = subject;
  if (!before) return null;
  const poolsDiffer = view.pool.mismatch || view.pool.onlyBefore.length > 0 || view.pool.onlyAfter.length > 0;
  const specs = [
    { title: "Mission utility", unit: "priority units", from: before.mission_utility, to: after.mission_utility, direction: "higher", pool: true },
    { title: "Request completion", unit: "%", from: before.request_pool_size === 0 ? null : before.completion_rate * 100, to: after.request_pool_size === 0 ? null : after.completion_rate * 100, direction: "higher", pool: true },
    { title: "Constraint violations", unit: "violations", from: before.violation_count, to: after.violation_count, direction: "lower", pool: false },
    { title: "Planning time", unit: "ms", from: before.planning_time_ms, to: after.planning_time_ms, direction: "lower", pool: false },
    ...(before.time_to_first_acquisition_s != null || after.time_to_first_acquisition_s != null ? [{ title: "Planned emergency response", unit: "s", from: before.time_to_first_acquisition_s, to: after.time_to_first_acquisition_s, direction: "neutral", pool: true }] : []),
    ...(before.achieved_time_to_first_acquisition_s != null || after.achieved_time_to_first_acquisition_s != null ? [{ title: "Achieved emergency response", unit: "s", from: before.achieved_time_to_first_acquisition_s, to: after.achieved_time_to_first_acquisition_s, direction: "neutral", pool: true }] : []),
  ];
  const previous = label(before.plan_id);
  const current = label(after.plan_id);
  return <section aria-label="Plan Comparison Performance" className="evaluation-section">
    <h3>Plan Comparison Performance</h3>
    <p>{previous} vs {current} · {poolsDiffer ? "Request pools differ: pool-dependent values are not directly comparable." : "Metrics measured over a common request pool."}</p>
    <div className="evaluation-comparison-grid">{specs.map(spec => {
      const delta = spec.from === null || spec.to === null ? null : Number((spec.to - spec.from).toPrecision(12));
      const judged = !(poolsDiffer && spec.pool) && spec.direction !== "neutral";
      const trend = delta === null ? "unavailable" : !judged ? "unjudged" : delta === 0 ? "unchanged" : (spec.direction === "lower" ? delta < 0 : delta > 0) ? "improved" : "degraded";
      const units = spec.unit === "%" ? "pp" : spec.unit;
      const value = (n: number | null) => n === null ? "N/A" : `${n} ${spec.unit}`;
      return <figure className="evaluation-comparison" key={spec.title} aria-label={`${spec.title} comparison`}>
        <figcaption><h4>{spec.title}</h4><span data-comparison-trend={trend}>{delta === null ? "Delta N/A" : `Delta ${delta > 0 ? "+" : ""}${delta} ${units}`} · {trend === "unjudged" ? "not judged" : trend}</span></figcaption>
        <p>{previous}: {value(spec.from)} · {current}: {value(spec.to)}</p>
        {spec.title === "Request completion" && <p>Request pools: {before.request_pool_size} → {after.request_pool_size}</p>}
        {spec.title.includes("emergency") && <p>{spec.title.startsWith("Planned") ? `Planned acquisitions: ${before.planned_emergency_request_count} of ${before.emergency_request_count} → ${after.planned_emergency_request_count} of ${after.emergency_request_count}` : `Started acquisitions: ${before.achieved_emergency_request_count} of ${before.emergency_request_count} → ${after.achieved_emergency_request_count} of ${after.emergency_request_count}`} · Different response populations may affect means; latency changes are not judged as improvements.</p>}
        <ResponsiveContainer width="100%" height={150} minWidth={0} initialDimension={{ width: 400, height: 150 }}>
          <BarChart layout="vertical" data={[{ metric: spec.title, previous: spec.from, current: spec.to }]} margin={{ top: 12, right: 16, left: 0, bottom: 0 }} accessibilityLayer>
            <CartesianGrid stroke="var(--amis-border)" horizontal={false} strokeDasharray="3 3" />
            <XAxis type="number" domain={[0, spec.unit === "%" ? 100 : Math.max(spec.from ?? 0, spec.to ?? 0, 1)]} tick={{ fill: "var(--color-mission-muted)", fontSize: 11 }} tickLine={false} axisLine={false} unit={spec.unit === "%" ? "%" : undefined} />
            <YAxis dataKey="metric" type="category" hide />
            <Tooltip cursor={false} formatter={v => `${v} ${spec.unit}`} contentStyle={{ background: "var(--amis-surface)", borderColor: "var(--amis-border)", color: "var(--color-mission-text)" }} />
            <Legend />
            <Bar dataKey="previous" name={previous} fill="var(--color-mission-muted)" barSize={16} isAnimationActive={false} />
            <Bar dataKey="current" name={current} fill="var(--color-mission-accent)" barSize={16} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </figure>;
    })}</div>
  </section>;
}
