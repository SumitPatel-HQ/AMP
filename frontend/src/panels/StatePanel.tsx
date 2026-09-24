import type { MissionEventSchema, MissionStateSchema } from "../api/client";
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
    <div className="mt-1 h-1 w-full bg-neutral-800">
      <div className={`h-full ${className}`} style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}

function ratio(value: number, capacity: number | null): number | null {
  return capacity === null || capacity === 0 ? null : value / capacity;
}

/** Live satellite telemetry and the events currently in force. */
export function StatePanel({
  state,
  events,
  satelliteCapacityWh,
  storageCapacityMb,
  requestCount,
}: {
  state: MissionStateSchema | null;
  events: MissionEventSchema[];
  satelliteCapacityWh: number | null;
  storageCapacityMb: number | null;
  requestCount: number | null;
}) {
  if (state === null) {
    return (
      <PanelFrame title="Mission state">
        <p className="text-xs text-neutral-500">No mission state yet.</p>
      </PanelFrame>
    );
  }

  const activeEvents = events.filter((event) => state.active_event_ids.includes(event.id));
  const batteryFraction = ratio(state.battery_wh, satelliteCapacityWh);
  const storageFraction = ratio(state.storage_usage_mb, storageCapacityMb);

  return (
    <PanelFrame title="Mission state" meta={state.satellite_id}>
      <div className="flex flex-col gap-3 text-xs">
        {state.mission_complete && <p className="text-emerald-400">Mission complete.</p>}
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-wider text-neutral-500">Battery</span>
            <span
              className={`tabular-nums ${
                batteryFraction === null ? "text-neutral-200" : batteryColor(batteryFraction)
              }`}
            >
              {state.battery_wh.toFixed(1)} Wh
            </span>
          </div>
          <Gauge
            fraction={batteryFraction}
            className={batteryFraction === null ? "" : barColor(batteryFraction)}
          />
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-wider text-neutral-500">Storage</span>
            <span className="tabular-nums text-neutral-200">
              {state.storage_usage_mb.toFixed(1)} MB
            </span>
          </div>
          <Gauge fraction={storageFraction} className="bg-sky-500" />
          {storageCapacityMb === null ? null : (
            <p className="mt-0.5 text-right text-[10px] text-neutral-600">
              of {storageCapacityMb.toFixed(0)} MB
            </p>
          )}
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt className="text-neutral-500">available</dt>
          <dd className={`text-right ${state.available ? "text-emerald-400" : "text-red-400"}`}>
            {state.available ? "yes" : "no"}
          </dd>
          <dt className="text-neutral-500">completed</dt>
          <dd className="text-right tabular-nums text-neutral-200">
            {requestCount === null
              ? state.completed_request_ids.length
              : `${state.completed_request_ids.length} / ${requestCount}`}
          </dd>
        </dl>
        <div>
          <h3 className="mb-1 text-[10px] uppercase tracking-wider text-neutral-500">
            Active event
          </h3>
          {activeEvents.length === 0 ? (
            <p className="text-neutral-500">none</p>
          ) : (
            <ul className="space-y-0.5 text-amber-300">
              {activeEvents.map((event) => (
                <li key={event.id}>
                  {event.event_type}: {event.id}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </PanelFrame>
  );
}
