import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { usePanelPresentation } from "./panelPresentation";
import { useMemo } from "react";
import type { MissionPlanSchema, MissionStateSchema, ScenarioSchema } from "../api/client";
import { storageProfile } from "../state/storageProfile";


/** Storage rising on imaging and falling on downlink across the mission (ADR-0011). */
export function StorageProfileChart({
  scenario,
  plan,
  missionState,
}: {
  scenario: ScenarioSchema;
  plan: MissionPlanSchema;
  missionState: MissionStateSchema | null;
}) {
  const points = useMemo(() => storageProfile(scenario, plan, missionState), [scenario, plan, missionState]);
  const { mode } = usePanelPresentation();
  const capacity = scenario.satellite.storage_capacity_mb;
  const data = [...points.map(point => ({ time: Date.parse(point.time), usedMb: point.usedMb })),
    { time: Date.parse(scenario.end_time), usedMb: points.at(-1)?.usedMb ?? 0 }];
  const expanded = mode === "expanded";
  const downlinks = plan.actions.filter((action) => action.kind === "downlink").length;
  return (
    <figure className={expanded ? "storage-projection-card evaluation-comparison" : "flex flex-col gap-1"} aria-label="Storage profile">
      <figcaption className="text-[12px]  text-neutral-400">
        {`Storage · capacity ${capacity.toFixed(0)} MB · ${downlinks} downlink${downlinks === 1 ? "" : "s"}`}
      </figcaption>
      {expanded && <dl className="storage-summary"><div><dt>Storage capacity</dt><dd>{capacity} <small>MB</small></dd></div><div><dt>Peak projected use</dt><dd>{Math.max(...data.map(point => point.usedMb), 0)} <small>MB</small></dd></div><div><dt>End-of-plan storage</dt><dd>{data.at(-1)?.usedMb ?? 0} <small>MB</small></dd></div><div><dt>Downlink actions</dt><dd>{downlinks}</dd></div></dl>}
      {expanded && <p className="text-xs text-neutral-400">Projected storage from current-plan actions and mission state; not a measured historical trend.</p>}
      <ResponsiveContainer width="100%" height={expanded ? 280 : 80} minWidth={0} initialDimension={{ width: 600, height: expanded ? 280 : 80 }}>
        <LineChart data={data} margin={{ top: 12, right: 24, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid stroke="var(--amis-border)" strokeDasharray="3 3" />
          <XAxis dataKey="time" type="number" domain={[Date.parse(scenario.start_time), Date.parse(scenario.end_time)]} tickFormatter={value => new Date(value).toISOString().slice(11, 16)} tick={{ fill: "var(--color-mission-muted)", fontSize: 11 }} hide={!expanded} />
          <YAxis unit=" MB" tick={{ fill: "var(--color-mission-muted)", fontSize: 11 }} domain={[0, Math.max(capacity, ...data.map(point => point.usedMb), 1)]} hide={!expanded} />
          <Tooltip labelFormatter={value => new Date(Number(value)).toISOString()} contentStyle={{ background: "var(--amis-surface)", borderColor: "var(--amis-border)" }} />
          <ReferenceLine y={capacity} stroke="var(--color-mission-muted)" strokeDasharray="4 3" />
          <Line type="stepAfter" dataKey="usedMb" name="Projected storage (MB)" stroke="var(--color-mission-accent)" strokeWidth={expanded ? 2 : 1} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      {expanded && <p className="storage-chart-key"><span>Projected storage · MB</span><span>Dashed line: capacity limit · Times in UTC</span></p>}
    </figure>
  );
}
