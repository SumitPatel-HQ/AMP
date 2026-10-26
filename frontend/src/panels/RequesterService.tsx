import type { MetricsSchema, MissionPlanSchema } from "../api/client";
import { formatPercent } from "../state/metricsView";

export function RequesterService({
  metrics,
  plan,
}: {
  metrics: MetricsSchema;
  plan?: MissionPlanSchema | null;
}) {
  const service = metrics.requester_service;
  if (!service) return null;

  const solverDetails = plan?.solver_details as Record<string, unknown> | undefined;
  const skipReason = solverDetails?.skip_reason as string | undefined;
  const fallbackReason = solverDetails?.fallback_reason as string | undefined;
  const achievedGap = solverDetails?.achieved_gap as number | undefined;
  const rebalancedIds = (solverDetails?.fairness_rebalanced_request_ids ?? []) as string[];
  const policy = plan?.planning_policy ?? "utility";
  const policyVersion = plan?.policy_version ?? service.metric_version;
  const isFairnessPolicy = policy === "utility_then_fairness";
  const stages = (solverDetails?.stages ?? []) as { stage: string; status: string }[];
  const primaryOptimal = stages.some((stage) => stage.stage === "utility" && stage.status === "OPTIMAL");
  const fairnessOptimal = stages.some((stage) => stage.stage === "fairness" && stage.status === "OPTIMAL");

  return (
    <section aria-label="Requester service" className="mt-3 space-y-2 text-[11px] text-neutral-400">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-white/[0.04] pb-1">
        <h3 className="font-medium text-neutral-200">Requester service &middot; {service.metric_version}</h3>
        <span className="text-[10px] text-neutral-400">
          Policy:{" "}
          <strong className="text-neutral-200">
            {isFairnessPolicy ? "Utility-then-Fairness" : "Pure Utility"}
          </strong>{" "}
          ({policyVersion}) &middot; {(plan?.planner_name ?? "greedy").replace("_", "-").toUpperCase()}
        </span>
      </div>

      <p>
        Identified-requester utility gap: {service.fairness_gap ?? "N/A (fewer than two requesters)"} priority units.
        {` ${service.zero_service_requester_count} identified requesters with zero service.`}
      </p>

      {service.no_service && (
        <p className="text-amber-300">No service: a zero gap does not demonstrate equitable service.</p>
      )}

      {solverDetails && (
        <div className="rounded border border-white/[0.06] bg-black/20 p-2 space-y-1 text-[10px]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-neutral-500">Solver status: </span>
            <span className="font-semibold text-neutral-200">{String(solverDetails.status ?? "UNKNOWN")}</span>
            {plan?.mission_utility !== undefined && (
              <span className="text-neutral-300">
                &middot; Primary utility: <strong>{plan.mission_utility}</strong>
              </span>
            )}
            {isFairnessPolicy && achievedGap !== undefined && achievedGap !== null && (
              <span className="text-neutral-300">
                &middot; Achieved gap: <strong>{achievedGap}</strong> priority units
              </span>
            )}
          </div>

          {skipReason && (
            <p className="text-amber-300">
              Fairness balancing skipped: {skipReason}.
            </p>
          )}

          {fallbackReason && (
            <p className="text-amber-300">
              Retained feasible plan: {fallbackReason}.
            </p>
          )}

          {isFairnessPolicy && !skipReason && !fallbackReason && (
            rebalancedIds.length > 0 ? (
              <p className="text-emerald-400">
                Fairness rebalanced requests ({rebalancedIds.length}): {rebalancedIds.join(", ")}.
              </p>
            ) : (
              <p className="text-neutral-400">
                {primaryOptimal && fairnessOptimal
                  ? "Primary utility held fixed; the requester utility gap is proven optimal."
                  : "No requester selection changes were attributed to fairness; optimality is not established for every stage."}
              </p>
            )
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <caption className="text-left">
            Service share denominator: {service.total_served_utility} total served priority units, including unattributed service. Fulfillment: acquisition served / demand utility. Archive count and utility are separate.
          </caption>
          <thead>
            <tr>
              {["Requester", "Archive count", "Archive utility", "Requests", "Demand utility", "Served requests", "Served utility", "Service share", "Fulfillment"].map((label) => (
                <th key={label} className="pr-2">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...service.requesters, service.unattributed].map((row) => (
              <tr key={row.requester_id === null ? "unattributed" : `id:${row.requester_id}`}>
                <th scope="row" className="pr-2">
                  {row.requester_id === null ? "Unattributed (no requester id)" : row.requester_id}
                </th>
                <td>{row.archive_satisfied_count ?? 0}</td>
                <td>{row.archive_satisfied_utility ?? 0}</td>
                <td>{row.request_count}</td>
                <td>{row.demand_utility}</td>
                <td>{row.served_request_count}</td>
                <td>{row.served_utility}</td>
                <td>{formatPercent(row.service_share)}</td>
                <td>{formatPercent(row.fulfillment_ratio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p>{service.scope}</p>
      <p>{service.limitations}</p>
      <p>{service.measured_at_convention} Measured at: {metrics.measured_at}.</p>
      {isFairnessPolicy && (
        <p className="text-[10px] text-neutral-400 italic">
          Fairness balancing runs only after primary utility is proven optimal and keeps that utility fixed.
        </p>
      )}
      <p>Requester ids are author labels, not entitlements.</p>
    </section>
  );
}
