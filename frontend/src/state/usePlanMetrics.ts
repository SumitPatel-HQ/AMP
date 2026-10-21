import { useEffect, useState } from "react";
import type { MetricsSchema } from "../api/client";

export function usePlanMetrics(
  currentPlanId: string | null,
  metrics: MetricsSchema | null,
  selectedPlanId: string | null,
  loadPlanMetrics: (planId: string) => Promise<MetricsSchema>,
): MetricsSchema | null {
  const historicalPlanId =
    selectedPlanId !== null && currentPlanId !== null && selectedPlanId !== currentPlanId ? selectedPlanId : null;
  const [fetched, setFetched] = useState<MetricsSchema | null>(null);
  useEffect(() => {
    if (historicalPlanId === null) {
      return;
    }
    let cancelled = false;
    loadPlanMetrics(historicalPlanId).then(
      (next) => {
        if (!cancelled) setFetched(next);
      },
      () => {
        if (!cancelled) setFetched(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [historicalPlanId, metrics, loadPlanMetrics]);
  if (historicalPlanId !== null) {
    return fetched?.plan_id === historicalPlanId ? fetched : null;
  }
  // Metrics fetched for another plan describe nothing drawn here.
  return metrics !== null && currentPlanId !== null && metrics.plan_id === currentPlanId ? metrics : null;
}

