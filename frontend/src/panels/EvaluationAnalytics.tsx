import { PlanPerformanceComparison } from "./PlanPerformanceComparison";
import type { MetricsSubject, MetricsView } from "../state/metricsView";
import { formatPercent } from "../state/metricsView";
import { emergencyResponseRows } from "../state/emergencyResponse";
import { fullTime } from "./format";
import "./evaluationAnalytics.css";

import { EvaluationBar } from "./EvaluationCharts";

export function EvaluationAnalytics({ subject, view, label, historical }: { subject: MetricsSubject; view: MetricsView; label: (id: string) => string; historical: boolean }) {
  const { after, before } = subject;
  const primary = ["utility", "completion", "violations", "churn", "coverage", "planning-time"];
  const titles = ["Acquisition utility", "Request completion", "Constraint violations", "Action churn", "Trace coverage", "Planner duration"];
  const service = after.requester_service;
  const requesters = service ? [...service.requesters, service.unattributed] : [];
  const responses = emergencyResponseRows(after);
  const responseMax = Math.max(1, ...responses.flatMap(row => [row.planned_latency_s ?? 0, row.achieved_latency_s ?? 0]));
  return <div className="evaluation-analytics" aria-label="Evaluation analytics">
    <header className="evaluation-heading"><div><p>MISSION PERFORMANCE</p><h3>{label(after.plan_id)} <span>· {historical ? "Historical plan" : "Current plan"}</span></h3></div><div><p>MEASUREMENT TIME · UTC</p><time dateTime={view.measuredAt}>{view.measuredAt}</time></div></header>
    <div className="evaluation-kpis">{primary.map((key, i) => {
      const row = view.rows.find(r => r.key === key)!;
      return <section key={key} aria-label={`${titles[i]} KPI`} title={row.hint}><h4>{titles[i]}</h4><strong data-warning={row.warn}>{row.after}</strong><p>{row.before === null ? "Selected plan measurement" : `${label(before!.plan_id)}: ${row.before}${row.delta === null ? "" : ` · Δ ${row.delta}`}${row.deltaNote ? ` · ${row.deltaNote}` : ""}`}</p></section>;
    })}</div>
    <PlanPerformanceComparison subject={subject} view={view} label={label} />
    <div className="evaluation-charts">
      <section className="evaluation-section"><h3>Current-plan indicators</h3>
        <p>{before ? "Current-plan indicators. Churn is relative to the parent; coverage describes changes carrying traces." : "Single-plan measurement; no comparative utility chart."}</p>
        <EvaluationBar label="Completed share" value={after.request_pool_size === 0 ? null : after.completion_rate} text={after.request_pool_size === 0 ? "N/A · empty request pool" : `${formatPercent(after.completion_rate)} · ${Math.round(after.completion_rate * after.request_pool_size)} of ${after.request_pool_size} requests`} tone="green" />
        <EvaluationBar label="Changed unfrozen actions" value={after.plan_churn} text={formatPercent(after.plan_churn)} tone="amber" />
        <EvaluationBar label="Changes with decision traces" value={after.explanation_coverage} text={formatPercent(after.explanation_coverage)} />
      </section>
      <section className="evaluation-section"><h3>Mission resource readings</h3><p>Mission state at {fullTime(view.measuredAt)}. These readings belong to the measurement instant, not to plan-version performance.</p>
        <EvaluationBar label="Battery used" value={after.battery_utilisation} text={formatPercent(after.battery_utilisation)} tone="amber" />
        <EvaluationBar label="Storage used" value={after.storage_utilisation} text={formatPercent(after.storage_utilisation)} />
        <dl className="evaluation-stats"><div><dt>Downlink actions</dt><dd>{after.downlink_action_count ?? "N/A"}</dd></div><div><dt>Downlink volume</dt><dd>{after.downlink_volume_mb == null ? "N/A" : `${after.downlink_volume_mb} MB`}</dd></div></dl>
      </section>
      <section className="evaluation-section"><h3>Requester demand and acquisition service</h3><p>Priority units · demand and served utility share a scale within each requester. Archive utility is excluded.</p>
        {!service ? <p>Requester service data unavailable.</p> : requesters.map(row => <div className="evaluation-requester" key={row.requester_id ?? "__unattributed"}><h4>{row.requester_id ?? "Unattributed (no requester id)"}</h4><EvaluationBar label="Demand" value={row.demand_utility} maximum={Math.max(row.demand_utility, row.served_utility, 1)} text={String(row.demand_utility)} /><EvaluationBar label="Served" value={row.served_utility} maximum={Math.max(row.demand_utility, row.served_utility, 1)} text={`${row.served_utility} · ${formatPercent(row.fulfillment_ratio)} fulfilled`} tone="green" /></div>)}
      </section>
      <section className="evaluation-section"><h3>Emergency acquisition latency</h3><p>Seconds from arrival to imaging start. Planned and achieved responses remain separate; missing acquisitions have no latency.</p>
        {responses.length === 0 ? <p>No emergency requests in this plan’s pool.</p> : responses.map(row => <div className="evaluation-requester" key={row.request_id}><h4>{row.request_id} · {row.event_id}</h4><EvaluationBar label="Planned latency" value={row.planned_latency_s} maximum={responseMax} text={row.planned_latency_s === null ? "N/A · no planned acquisition" : `${row.planned_latency_s} s`} /><EvaluationBar label="Achieved latency" value={row.achieved_latency_s} maximum={responseMax} text={row.achieved_latency_s === null ? "N/A · imaging has not started" : `${row.achieved_latency_s} s`} tone="green" /></div>)}
      </section>
    </div>
    <section className="evaluation-section evaluation-archive"><h3>Archive fulfillment</h3><dl className="evaluation-stats"><div><dt>Archive requests</dt><dd>{after.archive_satisfied_count ?? "N/A"}</dd></div><div><dt>Archive utility</dt><dd>{after.archive_satisfied_utility ?? "N/A"}</dd></div><div><dt>Total unique fulfilled requests</dt><dd>{after.total_fulfilled_count ?? "N/A"}</dd></div><div><dt>Total fulfilled utility</dt><dd>{after.total_fulfilled_utility ?? "N/A"}</dd></div></dl><p>Archive adds no simulated acquisition utility, imaging completions, or resource consumption. Historical plans exclude later archive transitions.</p></section>
  </div>;
}
