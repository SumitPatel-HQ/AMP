import { useMemo } from "react";
import type { MissionPlanSchema, ScenarioSchema } from "../api/client";
import { storageProfile } from "../state/storageProfile";

const WIDTH = 600;
const HEIGHT = 56;

/** Storage rising on imaging and falling on downlink across the mission (ADR-0011). */
export function StorageProfileChart({ scenario, plan }: { scenario: ScenarioSchema; plan: MissionPlanSchema }) {
  const points = useMemo(() => storageProfile(scenario, plan), [scenario, plan]);
  const capacity = scenario.satellite.storage_capacity_mb;
  const start = Date.parse(scenario.start_time);
  const span = Math.max(1, Date.parse(scenario.end_time) - start);
  const peak = Math.max(capacity, ...points.map((point) => point.usedMb), 1);
  const x = (time: string) => ((Date.parse(time) - start) / span) * WIDTH;
  const y = (mb: number) => HEIGHT - (mb / peak) * HEIGHT;
  let path = `M0,${y(points[0]?.usedMb ?? 0)}`;
  for (const point of points.slice(1)) {
    path += ` H${x(point.time).toFixed(1)} V${y(point.usedMb).toFixed(1)}`;
  }
  path += ` H${WIDTH}`;
  const downlinks = plan.actions.filter((action) => action.kind === "downlink").length;
  return (
    <figure className="flex flex-col gap-1" aria-label="Storage profile">
      <figcaption className="text-[10px] uppercase tracking-wide text-neutral-500">
        {`Storage · capacity ${capacity.toFixed(0)} MB · ${downlinks} downlink${downlinks === 1 ? "" : "s"}`}
      </figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" className="h-14 w-full">
        <line x1={0} x2={WIDTH} y1={y(capacity)} y2={y(capacity)} stroke="#737373" strokeDasharray="4 3" strokeWidth={1} />
        <path d={path} fill="none" stroke="#38bdf8" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
    </figure>
  );
}
