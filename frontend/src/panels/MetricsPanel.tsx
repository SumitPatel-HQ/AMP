import { useId, useState, type ReactNode } from "react";
import { PlanPerformanceComparison } from "./PlanPerformanceComparison";
import { EvaluationBar } from "./EvaluationCharts";
import { CompactEvaluation } from "./CompactEvaluation";
import { EvaluationAnalytics } from "./EvaluationAnalytics";
import { usePanelPresentation } from "./panelPresentation";
import { usePlanMetrics } from "../state/usePlanMetrics";
import { fetchMetrics } from "../api/amis";
import type { EmergencyResponseSchema, MetricsSchema, MissionPlanSchema, PlanDiffSchema } from "../api/client";
import {
  ACQUISITION_MEANING,
  emergencyResponseRows,
  emergencyResponseState,
  formatLatency,
  plannedDiffersFromAchieved,
  RESPONSE_STATE_LABEL,
  type EmergencyResponseState,
} from "../state/emergencyResponse";
import {
  formatPercent,
  metricsSubject,
  metricsView,
  type MetricRow,
  type MetricTrend,
  type MetricsView,
} from "../state/metricsView";
import { planLabel } from "../state/planContext";
import { clockTime, fullTime } from "./format";
import { PanelFrame } from "./PanelFrame";
import { RequesterService } from "./RequesterService";

const TREND_STYLE: Record<MetricTrend, string> = {
  better: "text-emerald-400",
  worse: "text-red-400",
  same: "text-neutral-400",
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
        <span className="ml-1 text-[12px] text-amber-400/80">{row.deltaNote}</span>
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
    <p role="alert" className="mb-1 text-[12px] text-red-400">
      {`${before} and ${after} were measured against different request pools (${view.pool.before} vs ${view.pool.after} requests`}
      {differences.length === 0 ? ")" : `: ${differences.join(", ")})`}
      . Utility and completion changes are not like for like.
    </p>
  );
}

const RESPONSE_STATE_STYLE: Record<EmergencyResponseState, string> = {
  archive: "text-violet-300",
  achieved: "text-emerald-300",
  planned: "text-sky-300",
  expired: "text-red-400",
  unserved: "text-amber-300",
};

function plannedText(row: EmergencyResponseSchema, planLabel: string): string {
  if (row.planned_start_time === null) {
    return `${planLabel} planned: no planned acquisition`;
  }
  return `${planLabel} planned: ${clockTime(row.planned_start_time)} UTC on ${row.planned_satellite_id} · ${formatLatency(row.planned_latency_s)}`;
}

function achievedText(row: EmergencyResponseSchema, state: EmergencyResponseState): string {
  if (row.achieved_start_time === null) {
    return state === "planned" ? "Achieved: not started" : "Achieved: no acquisition";
  }
  return `Achieved: ${clockTime(row.achieved_start_time)} UTC on ${row.achieved_satellite_id} · ${formatLatency(row.achieved_latency_s)}`;
}

/**
 * One line per emergency arrival the measured plan's request pool holds,
 * unserved and expired ones included. Planned values belong to that plan;
 * achieved values are the backend's record of imaging that actually began.
 */
function EmergencyResponseList({ metrics, planLabel }: { metrics: MetricsSchema; planLabel: string }) {
  const rows = emergencyResponseRows(metrics);
  if (rows.length === 0) {
    return null;
  }
  return (
    <section
      aria-label="Emergency response"
      className="mt-1 border-t border-white/[0.04] pt-1 text-[12px]"
    >
      <p className="text-neutral-400">{`Emergency response for ${planLabel}. ${ACQUISITION_MEANING}`}</p>
      <ul className="flex flex-col gap-0.5">
        {rows.map((row) => {
          const state = emergencyResponseState(row);
          return (
            <li
              key={row.request_id}
              data-request-id={row.request_id}
              data-event-id={row.event_id}
              data-response-state={state}
              title={`${row.request_id} arrived with ${row.event_id} at ${fullTime(row.arrival_time)}; request ${row.request_status}`}
              className="tabular-nums text-neutral-300"
            >
              <span className="text-neutral-100">{row.request_id}</span>
              {` · arrived ${clockTime(row.arrival_time)} UTC · `}
              <span className={RESPONSE_STATE_STYLE[state]}>{RESPONSE_STATE_LABEL[state]}</span>
              <br />
              <span className="text-neutral-400">{plannedText(row, planLabel)}</span>
              {" · "}
              <span className="text-neutral-400">{achievedText(row, state)}</span>
              {plannedDiffersFromAchieved(row) ? (
                <span className="ml-1 text-amber-300/80">(planned differs from achieved)</span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
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
  selectedPlanId = null,
  loadPlanMetrics = fetchMetrics,
  resourceProfile,
}: {
  resourceProfile?: ReactNode;
  currentPlanId: string | null;
  /** The current plan's own metrics. */
  metrics: MetricsSchema | null;
  /** The last replan's comparison; used only while its revised plan is current. */
  diff: PlanDiffSchema | null;
  /** The plan versions the session holds, so columns name them as V1, V2. */
  plans?: readonly MissionPlanSchema[];
  selectedPlanId?: string | null;
  loadPlanMetrics?: (planId: string) => Promise<MetricsSchema>;
}) {
  const { mode } = usePanelPresentation();
  const MeasurementNote = mode === "expanded" ? "details" : "div";
  const [tab, setTab] = useState(0);
  const tabId = useId();
  const label = (planId: string) => planLabel(planId, plans);
  const selectedMetrics = usePlanMetrics(currentPlanId, metrics, selectedPlanId, loadPlanMetrics);
  const historical = selectedPlanId !== null && selectedPlanId !== currentPlanId;
  const subject = metricsSubject(historical ? selectedPlanId : currentPlanId, selectedMetrics, historical ? null : diff);
  if (subject === null) {
    return (
      <PanelFrame title="Mission evaluation">
        <p className="text-xs text-neutral-400">
          {currentPlanId === null
            ? "Generate a plan to evaluate it."
            : `Evaluating ${label(mode === "compact" && historical ? selectedPlanId! : currentPlanId)}…`}
        </p>
      </PanelFrame>
    );
  }

  const view = metricsView(subject);
  const comparing = view.beforePlanId !== null;
  const versions =
    view.beforePlanId === null
      ? label(view.afterPlanId)
      : `${label(view.beforePlanId)} → ${label(view.afterPlanId)}`;

  if (mode === "compact") {
    return <PanelFrame title="Mission evaluation">
      <CompactEvaluation subject={subject} view={view} historical={historical} label={label}
        requester={subject.after.requester_service ? <RequesterService metrics={subject.after} plan={plans.find(plan => plan.id === view.afterPlanId) ?? null} compactCards /> : <p>Requester service data unavailable.</p>}
        emergency={emergencyResponseRows(subject.after).length ? <EmergencyResponseList metrics={subject.after} planLabel={label(view.afterPlanId)} /> : <p>No emergency requests in this plan's pool.</p>}
        resourceProfile={resourceProfile} />
    </PanelFrame>;
  }

  return (
    <PanelFrame
      title="Mission evaluation"
      meta={`${versions} · measured ${clockTime(view.measuredAt)} UTC`}
    >
      <PoolMismatch view={view} label={label} />
      {mode === "expanded" && <>
        <div role="tablist" aria-label="Evaluation views" className="evaluation-tabs">
          {["Analytics", comparing ? `Detailed comparison (${label(view.beforePlanId!)} vs ${label(view.afterPlanId)})` : `Details and methodology (${label(view.afterPlanId)})`].map((title, index) => <button key={index} type="button" role="tab" id={`${tabId}-tab-${index}`} aria-selected={tab === index} aria-controls={`${tabId}-panel-${index}`} tabIndex={tab === index ? 0 : -1} onClick={() => setTab(index)} onKeyDown={event => {
            const next = event.key === "ArrowRight" || event.key === "ArrowLeft" ? 1 - index : event.key === "Home" ? 0 : event.key === "End" ? 1 : null;
            if (next === null) return;
            event.preventDefault(); setTab(next); document.getElementById(`${tabId}-tab-${next}`)?.focus();
          }}>{title}</button>)}
        </div>
        <div role="tabpanel" id={`${tabId}-panel-0`} aria-labelledby={`${tabId}-tab-0`} hidden={tab !== 0} tabIndex={0}>
          <EvaluationAnalytics subject={subject} view={view} label={label} historical={historical} />
        </div>
      </>}
      <div role={mode === "expanded" ? "tabpanel" : undefined} id={`${tabId}-panel-1`} aria-labelledby={mode === "expanded" ? `${tabId}-tab-1` : undefined} hidden={mode === "expanded" && tab !== 1} tabIndex={mode === "expanded" ? 0 : undefined}>
      {mode === "expanded" && <div className="evaluation-analytics evaluation-details-overview">
        <header className="evaluation-heading"><div><p>PLAN PERFORMANCE</p><h3>{versions}</h3></div><p>Measured {fullTime(view.measuredAt)}</p></header>
        <PlanPerformanceComparison subject={subject} view={view} label={label} />
        {!comparing && <section className="evaluation-section"><h3>Selected-plan performance</h3><div className="evaluation-kpis">{view.rows.filter(row => !["churn", "coverage"].includes(row.key)).map(row => <section key={row.key}><h4>{row.label}</h4><strong data-warning={row.warn}>{row.after}</strong><p>{row.hint}</p></section>)}</div></section>}
        <section className="evaluation-section"><h3>{label(view.afterPlanId)} change indicators</h3><p>Churn describes changes from this plan’s parent. Trace coverage describes explained changes; neither has an invented previous-plan value.</p><div className="evaluation-comparison-grid">
          <EvaluationBar label="Plan churn" value={subject.after.plan_churn} text={formatPercent(subject.after.plan_churn)} tone="amber" />
          <EvaluationBar label="Explanation coverage" value={subject.after.explanation_coverage} text={formatPercent(subject.after.explanation_coverage)} />
        </div></section>
      </div>}
      <section className={mode === "expanded" ? "evaluation-open-section evaluation-system-section evaluation-measurements" : "contents"}>
      {mode === "expanded" && <header className="evaluation-section-heading"><h3>Underlying measurements &amp; definitions</h3><p>Exact values, request pools and measurement context</p></header>}
      <div className={mode === "expanded" ? "evaluation-disclosure-content evaluation-measurements-card" : undefined}>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[12px]  text-neutral-400">
            <th className="py-0.5 font-normal">Metric</th>
            {view.beforePlanId === null ? null : (
              <th className={`py-0.5 font-normal ${selectedPlanId === view.beforePlanId ? "bg-fuchsia-400/10 text-fuchsia-200" : ""}`} title={view.beforePlanId}>
                {label(view.beforePlanId)}
              </th>
            )}
            <th className={`py-0.5 font-normal ${selectedPlanId === view.afterPlanId ? "bg-fuchsia-400/10 text-fuchsia-200" : ""}`} title={view.afterPlanId}>
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
                <td className={`py-px pr-3 tabular-nums text-neutral-400 ${selectedPlanId === view.beforePlanId ? "bg-fuchsia-400/10" : ""}`}>{row.before}</td>
              )}
              <td
                className={`py-px pr-3 tabular-nums ${row.warn ? "text-amber-300" : "text-neutral-100"} ${selectedPlanId === view.afterPlanId ? "bg-fuchsia-400/10" : ""}`}
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
      <MeasurementNote className={mode === "expanded" ? "requester-accounting-note measurement-accounting-note" : undefined}>
      {mode === "expanded" && <summary>Measurement context &amp; fulfillment notes</summary>}
      <p
        aria-label="Mission state readings"
        title={`Read from the mission state at ${fullTime(view.measuredAt)}, not from either plan`}
        className="mt-1 border-t border-white/[0.04] pt-1 text-[12px] text-neutral-400"
      >
        {`Mission state at ${clockTime(view.measuredAt)} UTC: battery used ${view.resources.battery} · storage used ${view.resources.storage}`}
      </p>
      <p className="text-[12px] text-neutral-400">
        {view.pool.before === null || view.pool.before === view.pool.after
          ? `Request pool: ${view.pool.after} requests`
          : `Request pool: ${view.pool.before} → ${view.pool.after} requests`}
      </p>
      <section aria-label="Archive and total fulfillment" className="text-[11px] text-neutral-400">
        <p>Archive fulfillment: {subject.after.archive_satisfied_count ?? "N/A"} requests · utility {subject.after.archive_satisfied_utility ?? "N/A"}</p>
        <p>Total fulfilled (planned/completed imaging plus archive, unique requests): {subject.after.total_fulfilled_count ?? "N/A"} · utility {subject.after.total_fulfilled_utility ?? "N/A"}</p>
        <p>Archive adds no simulated acquisition utility, imaging completions, or resource consumption. Historical plans exclude later archive transitions.</p>
        <p>Current fulfillment includes accepted archive arrivals since planning; acquisition membership stays with the selected plan.</p>
      </section>
      </MeasurementNote>
      </div></section>
      <section className={mode === "expanded" ? "evaluation-open-section evaluation-system-section" : "contents"}>
      {mode === "expanded" && <header className="evaluation-section-heading"><h3>Requester service &amp; fulfillment</h3><p>Service breakdown, emergency acquisitions and archive accounting</p></header>}
      <div className={mode === "expanded" ? "evaluation-disclosure-content" : undefined}>
      <EmergencyResponseList metrics={subject.after} planLabel={label(view.afterPlanId)} />
      <RequesterService metrics={subject.after} plan={plans?.find((p) => p.id === view.afterPlanId) ?? null} />
      </div></section>
      {mode === "expanded" ? <section className="evaluation-open-section evaluation-system-section"><header className="evaluation-section-heading"><h3>Storage projection</h3><p>Resource capacity and downlink profile</p></header><div className="evaluation-disclosure-content">{resourceProfile ?? <p>No storage projection available.</p>}</div></section> : resourceProfile}
      </div>
    </PanelFrame>
  );
}
