import type { ReactNode } from "react";
import type { MissionEventSchema, MissionPlanSchema, MissionStateSchema } from "../api/client";
import { eventSummary } from "../state/missionEvent";
import { shortPlanId } from "./format";
import { PanelFrame } from "./PanelFrame";

function batteryColor(fraction: number): string {
  if (fraction < 0.2) return "text-red-400";
  if (fraction < 0.5) return "text-amber-400";
  return "text-emerald-400";
}

function barColor(fraction: number): string {
  if (fraction < 0.2) return "bg-red-500";
  if (fraction < 0.5) return "bg-amber-500";
  return "bg-emerald-500";
}

/** A thin fill bar; drawn only when the capacity it divides by is known. */
function Gauge({ fraction, className }: { fraction: number | null; className: string }) {
  if (fraction === null) {
    return null;
  }
  const clamped = Math.min(Math.max(fraction, 0), 1);
  return (
    <div className="h-1 w-full bg-neutral-800">
      <div className={`h-full ${className}`} style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}

function ratio(value: number, capacity: number | null): number | null {
  return capacity === null || capacity === 0 ? null : value / capacity;
}

/** A resource reading: value against capacity, its share, and a gauge beneath. */
function Resource({
  label,
  value,
  unit,
  capacity,
  valueClassName,
  barClassName,
}: {
  label: string;
  value: number;
  unit: string;
  capacity: number | null;
  valueClassName: string;
  barClassName: string;
}) {
  const fraction = ratio(value, capacity);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2">
        <span className="w-16 shrink-0 text-neutral-400">{label}</span>
        <span className={`tabular-nums ${valueClassName}`}>{`${value.toFixed(1)} ${unit}`}</span>
        {capacity === null ? null : (
          <span className="ml-auto truncate tabular-nums text-[10px] text-neutral-500">
            {`/ ${capacity.toFixed(0)} ${unit}`}
            {fraction === null ? "" : ` · ${Math.round(fraction * 100)}%`}
          </span>
        )}
      </div>
      <Gauge fraction={fraction} className={barClassName} />
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-neutral-400">{label}</dt>
      <dd className="min-w-0 truncate text-right tabular-nums text-neutral-200">{children}</dd>
    </>
  );
}

/** Live satellite telemetry, the events in force and the plan the clock is running. */
export function StatePanel({
  state,
  events,
  plan,
  replanned,
  satelliteCapacityWh,
  storageCapacityMb,
  requestCount,
}: {
  state: MissionStateSchema | null;
  events: MissionEventSchema[];
  plan: MissionPlanSchema | null;
  /** The current plan is the result of a replan. */
  replanned: boolean;
  satelliteCapacityWh: number | null;
  storageCapacityMb: number | null;
  requestCount: number | null;
}) {
  if (state === null) {
    return (
      <PanelFrame title="Mission state">
        <p className="text-xs text-neutral-500">Load a scenario to read satellite telemetry.</p>
      </PanelFrame>
    );
  }

  const activeEvents = events.filter((event) => state.active_event_ids.includes(event.id));
  const batteryFraction = ratio(state.battery_wh, satelliteCapacityWh);
  const iso = new Date(state.simulated_time).toISOString();

  return (
    <PanelFrame title="Mission state" meta={state.satellite_id}>
      <div className="flex flex-col gap-2 text-xs">
        {state.mission_complete && <p className="text-emerald-400">Mission complete.</p>}
        <Resource
          label="Battery"
          value={state.battery_wh}
          unit="Wh"
          capacity={satelliteCapacityWh}
          valueClassName={batteryFraction === null ? "text-neutral-200" : batteryColor(batteryFraction)}
          barClassName={batteryFraction === null ? "" : barColor(batteryFraction)}
        />
        <Resource
          label="Storage"
          value={state.storage_usage_mb}
          unit="MB"
          capacity={storageCapacityMb}
          valueClassName="text-neutral-200"
          barClassName="bg-sky-500"
        />
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 border-t border-[var(--amis-border)] pt-2">
          <Row label="Satellite">
            <span className={state.available ? "text-emerald-400" : "text-red-400"}>
              {state.available ? "available" : "unavailable"}
            </span>
          </Row>
          <Row label="Completed">
            {requestCount === null
              ? state.completed_request_ids.length
              : `${state.completed_request_ids.length} / ${requestCount}`}
          </Row>
          <Row label="Active event">
            {activeEvents.length === 0 ? (
              <span className="text-neutral-500">none</span>
            ) : (
              <span className="flex flex-col items-end">
                {activeEvents.map((event) => (
                  <span key={event.id} className="text-red-300">
                    {`${event.event_type} · ${event.id}`}
                    <span className="block text-[10px] text-neutral-500">
                      {eventSummary(event)}
                    </span>
                  </span>
                ))}
              </span>
            )}
          </Row>
          <Row label="Sim time">{`${iso.slice(0, 10)} ${iso.slice(11, 19)}`}</Row>
          <Row label="Plan">
            {plan === null ? (
              <span className="text-neutral-500">none</span>
            ) : (
              <span title={plan.id}>
                <span className={replanned ? "text-emerald-400" : "text-sky-300"}>
                  {`V${plan.version}${replanned ? " (replanned)" : ""}`}
                </span>
                <span className="block text-[10px] text-neutral-500">{shortPlanId(plan.id)}</span>
              </span>
            )}
          </Row>
        </dl>
      </div>
    </PanelFrame>
  );
}
