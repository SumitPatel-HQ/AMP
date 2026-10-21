import type { MetricsSchema } from "../api/client";
import { formatPercent } from "../state/metricsView";

export function RequesterService({ metrics }: { metrics: MetricsSchema }) {
  const service = metrics.requester_service;
  if (!service) return null;
  return <section aria-label="Requester service" className="mt-3 space-y-2 text-[11px] text-neutral-400">
    <h3 className="text-neutral-200">Requester service · {service.metric_version}</h3>
    <p>Identified-requester utility gap: {service.fairness_gap ?? "N/A (fewer than two requesters)"} priority units.
      {` ${service.zero_service_requester_count} identified requesters with zero service.`}</p>
    {service.no_service && <p className="text-amber-300">No service: a zero gap does not demonstrate equitable service.</p>}
    <div className="overflow-x-auto"><table className="w-full text-left">
      <caption className="text-left">Service share denominator: {service.total_served_utility} total served priority units, including unattributed service. Fulfillment: served / demand utility.</caption>
      <thead><tr>{["Requester", "Requests", "Demand utility", "Served requests", "Served utility", "Service share", "Fulfillment"].map(label => <th key={label} className="pr-2">{label}</th>)}</tr></thead>
      <tbody>{[...service.requesters, service.unattributed].map(row => <tr key={row.requester_id === null ? "unattributed" : `id:${row.requester_id}`}>
        <th scope="row" className="pr-2">{row.requester_id === null ? "Unattributed (no requester id)" : row.requester_id}</th>
        <td>{row.request_count}</td><td>{row.demand_utility}</td><td>{row.served_request_count}</td>
        <td>{row.served_utility}</td><td>{formatPercent(row.service_share)}</td><td>{formatPercent(row.fulfillment_ratio)}</td>
      </tr>)}</tbody>
    </table></div>
    <p>{service.scope}</p><p>{service.limitations}</p>
    <p>{service.measured_at_convention} Measured at: {metrics.measured_at}.</p>
    <p>Measurement only; existing planning objectives apply. Requester ids are author labels, not entitlements.</p>
  </section>;
}
