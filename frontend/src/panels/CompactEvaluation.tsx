import type { ReactNode } from "react";
import type { MetricsSchema } from "../api/client";
import type { MetricRow, MetricsSubject, MetricsView } from "../state/metricsView";
import { fullTime } from "./format";
import "./compactEvaluation.css";

// Display precision only; backend measurements and definitions stay unchanged.
const numberText = (value: number) => String(Number(value.toPrecision(15)));
const percent = (value: number | null) => value == null ? "N/A" : `${numberText(value * 100)}%`;
function reading(key: string, metrics: MetricsSchema): { value: number | null; text: string; unit: string } | null {
  switch (key) {
    case "utility": return { value: metrics.mission_utility, text: numberText(metrics.mission_utility), unit: "priority units" };
    case "completion": return { value: metrics.request_pool_size ? metrics.completion_rate * 100 : null, text: metrics.request_pool_size ? percent(metrics.completion_rate) : "N/A", unit: "pp" };
    case "violations": return { value: metrics.violation_count, text: String(metrics.violation_count), unit: "violations" };
    case "planning-time": return { value: metrics.planning_time_ms, text: `${numberText(metrics.planning_time_ms)} ms`, unit: "ms" };
    case "churn": return { value: null, text: percent(metrics.plan_churn), unit: "" };
    case "coverage": return { value: null, text: percent(metrics.explanation_coverage), unit: "" };
    default: return null;
  }
}

function Metric({ row, subject, label, poolsDiffer, small = false }: { row: MetricRow; subject: MetricsSubject; label: (id: string) => string; poolsDiffer: boolean; small?: boolean }) {
  const current = reading(row.key, subject.after);
  const previous = subject.before ? reading(row.key, subject.before) : null;
  const delta = current?.value != null && previous?.value != null ? Number((current.value - previous.value).toPrecision(15)) : null;
  const unjudged = poolsDiffer && ["utility", "completion"].includes(row.key);
  const trend = delta === null || unjudged ? null : delta === 0 ? "same" : (row.key === "violations" || row.key === "planning-time" ? delta < 0 : delta > 0) ? "better" : "worse";
  const titles: Record<string, string> = { utility: "Mission Utility", completion: "Completion", violations: "Constraint Violations", churn: "Plan Churn", coverage: "Explanation Coverage", "planning-time": "Planning Time" };
  return <section className={`compact-metric ${small ? "compact-metric-row" : ""}`} aria-label={`${titles[row.key] ?? row.label} metric`}>
    <h3>{titles[row.key] ?? row.label}</h3>
    <strong data-warning={row.warn}>{current?.text ?? row.after}</strong>
    {subject.before && <p className="compact-comparison"><span>{label(subject.before.plan_id)}: {previous?.text ?? row.before} → {label(subject.after.plan_id)}: {current?.text ?? row.after}</span>{delta !== null && <span data-trend={trend ?? undefined}>Δ {delta > 0 ? "+" : ""}{numberText(delta)} {current?.unit}{trend ? ` · ${{ better: "improved", worse: "degraded", same: "unchanged" }[trend]}` : ""}</span>}{unjudged && <span className="compact-caution">Different request pools; not directly comparable</span>}</p>}
  </section>;
}

function Resource({ title, value }: { title: string; value: number | null }) {
  return <div className="compact-resource"><div><span>{title}</span><strong>{percent(value)}</strong></div>{value == null ? <p>N/A</p> : <progress aria-label={title} aria-valuetext={percent(value)} max={100} value={Math.max(0, Math.min(100, value * 100))} />}</div>;
}

export function CompactEvaluation({ subject, view, historical, label, requester, emergency, resourceProfile }: { subject: MetricsSubject; view: MetricsView; historical: boolean; label: (id: string) => string; requester: ReactNode; emergency: ReactNode; resourceProfile?: ReactNode }) {
  const { after, before } = subject;
  const poolsDiffer = view.pool.mismatch || view.pool.onlyBefore.length > 0 || view.pool.onlyAfter.length > 0;
  const completed = Math.round(after.completion_rate * after.request_pool_size);
  const metric = (key: string, small = false) => <Metric key={key} row={view.rows.find(row => row.key === key)!} subject={subject} label={label} poolsDiffer={poolsDiffer} small={small} />;
  return <div className="compact-evaluation" aria-label="Compact mission evaluation">
    <header className="compact-context"><span>{historical ? "Historical plan" : "Current plan"} · {label(after.plan_id)}</span><time dateTime={view.measuredAt}>Measured {fullTime(view.measuredAt)}</time>{before && <span>Comparing {label(before.plan_id)} → {label(after.plan_id)}</span>}</header>
    {poolsDiffer && before && <p className="compact-caution">Request pools differ: utility and completion are not directly comparable.</p>}
    <div className="compact-kpis">{["utility", "completion", "violations", "churn"].map(key => metric(key))}</div>
    <div className="compact-secondary">{metric("coverage", true)}{metric("planning-time", true)}</div>
    <section className="compact-block" aria-label="Resource utilization"><h3>Resource utilization</h3><Resource title="Battery used" value={after.battery_utilisation} /><Resource title="Storage used" value={after.storage_utilisation} /><p>Mission state at the measurement instant.</p></section>
    <section className="compact-block" aria-label="Archive and total fulfillment"><h3>Fulfillment</h3><dl className="compact-facts"><div><dt>Request pool</dt><dd>{after.request_pool_size} requests</dd></div><div><dt>Completed imaging requests</dt><dd>{completed} of {after.request_pool_size}</dd></div><div><dt>Total fulfilled</dt><dd>{after.total_fulfilled_count ?? "N/A"} requests · {after.total_fulfilled_utility ?? "N/A"} utility</dd></div><div><dt>Archive fulfillment</dt><dd>{after.archive_satisfied_count ?? "N/A"} requests · {after.archive_satisfied_utility ?? "N/A"} utility</dd></div></dl><p>Total fulfillment counts unique planned/completed imaging plus archive. Archive is separate from imaging completion and adds no acquisition utility or resource consumption.</p></section>
    <details className="compact-disclosure"><summary>Requester Service</summary>{requester}</details>
    <details className="compact-disclosure"><summary>Emergency Response</summary><dl className="compact-facts">{view.rows.filter(row => ["planned-response", "achieved-response"].includes(row.key)).map(row => <div key={row.key}><dt>{row.label}</dt><dd>{row.after}{before && <small>{label(before.plan_id)}: {row.before} → {label(after.plan_id)}: {row.after}</small>}</dd></div>)}</dl>{emergency}</details>
    <details className="compact-disclosure"><summary>Metric Details &amp; Methodology</summary><div className="compact-methodology">{view.rows.map(row => <section key={row.key}><h4>{row.label}</h4><p>{row.hint}</p><p>{label(after.plan_id)}: {reading(row.key, after)?.text ?? row.after}{before && ` · ${label(before.plan_id)}: ${reading(row.key, before)?.text ?? row.before}`}</p></section>)}<section><h4>Request pool membership</h4><p>{after.request_pool_ids.join(", ") || "Empty request pool"}</p>{before && <><p>{label(before.plan_id)} pool: {before.request_pool_ids.join(", ") || "Empty request pool"}</p><p>Only in {label(before.plan_id)}: {view.pool.onlyBefore.join(", ") || "None"}</p><p>Only in {label(after.plan_id)}: {view.pool.onlyAfter.join(", ") || "None"}</p></>}</section><p>Measured at: {view.measuredAt}. Battery and storage describe mission state, not individual plan versions.</p><p>Acquisition membership stays with the selected plan. Current fulfillment includes accepted archive arrivals since planning; historical plans exclude later archive transitions.</p>{resourceProfile}</div></details>
  </div>;
}
