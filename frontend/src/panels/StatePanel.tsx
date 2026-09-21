import type { MissionEventSchema, MissionStateSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

function batteryColor(fraction: number): string {
  if (fraction < 0.2) return "text-red-400";
  if (fraction < 0.5) return "text-amber-400";
  return "text-emerald-400";
}

export function StatePanel({
  state,
  events,
  satelliteCapacityWh,
}: {
  state: MissionStateSchema | null;
  events: MissionEventSchema[];
  satelliteCapacityWh: number | null;
}) {
  if (state === null) {
    return (
      <PanelFrame title="State">
        <p className="text-sm text-neutral-500">No mission state yet.</p>
      </PanelFrame>
    );
  }

  const activeEvents = events.filter((event) => state.active_event_ids.includes(event.id));
  const batteryFraction =
    satelliteCapacityWh === null || satelliteCapacityWh === 0
      ? null
      : state.battery_wh / satelliteCapacityWh;

  return (
    <PanelFrame title="State">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-neutral-500">simulated time</dt>
        <dd className="text-neutral-200">
          {new Date(state.simulated_time).toISOString()}
        </dd>
        <dt className="text-neutral-500">battery</dt>
        <dd className={batteryFraction === null ? "text-neutral-200" : batteryColor(batteryFraction)}>
          {state.battery_wh.toFixed(1)} Wh
        </dd>
        <dt className="text-neutral-500">storage</dt>
        <dd className="text-neutral-200">{state.storage_usage_mb.toFixed(1)} MB</dd>
        <dt className="text-neutral-500">available</dt>
        <dd className={state.available ? "text-emerald-400" : "text-red-400"}>
          {state.available ? "yes" : "no"}
        </dd>
      </dl>
      <div>
        <h3 className="mb-1 text-xs uppercase tracking-widest text-neutral-500">
          Active event
        </h3>
        {activeEvents.length === 0 ? (
          <p className="text-sm text-neutral-500">none</p>
        ) : (
          <ul className="space-y-1 text-sm text-neutral-200">
            {activeEvents.map((event) => (
              <li key={event.id}>
                {event.event_type}: {event.id}
              </li>
            ))}
          </ul>
        )}
      </div>
    </PanelFrame>
  );
}
