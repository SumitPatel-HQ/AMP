import { useMemo, useState, type ReactNode } from "react";
import type {
  MissionEventRequest,
  MissionEventSchema,
  MissionEventType,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import {
  buildEmergencyRequestEvent,
  CUE_ALERT_LEVELS,
  CUE_POLICY_NOTICE,
  emergencyEvidence,
  emergencyRequestDefaults,
  emergencyWindowId,
  missionRequestPool,
  type EmergencyRequestForm,
} from "../state/missionEvent";
import { CONTROL_BUTTON, CONTROL_INPUT, EVENT_BUTTON_OPEN } from "./controls";
import { clockTime } from "./format";

const EVENT_TYPES: { type: MissionEventType; label: string }[] = [
  { type: "CLOUD_BLOCK", label: "Cloud block" },
  { type: "BATTERY_DROP", label: "Battery drop" },
  { type: "EMERGENCY_TASK", label: "Emergency request" },
  { type: "SATELLITE_UNAVAILABLE", label: "Payload outage" },
  { type: "COMMUNICATION_OUTAGE", label: "Comm outage" },
];

const INJECT_LABEL: Record<MissionEventType, string> = {
  CLOUD_BLOCK: "Inject cloud block",
  BATTERY_DROP: "Inject battery drop",
  EMERGENCY_TASK: "Inject emergency request",
  SATELLITE_UNAVAILABLE: "Inject payload outage",
  COMMUNICATION_OUTAGE: "Inject comm outage",
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-0.5 text-[10px] uppercase tracking-wide text-neutral-500">
      {label}
      {children}
    </label>
  );
}

/** Request, then one of that request's real windows: the cloud block the API accepts. */
function CloudBlockFields({
  requestIds,
  windows,
  onChange,
}: {
  requestIds: string[];
  windows: ObservationWindowSchema[];
  onChange: (event: MissionEventRequest | null) => void;
}) {
  const [requestId, setRequestId] = useState("");
  const [windowId, setWindowId] = useState("");
  const windowsForRequest = windows.filter((window) => window.request_id === requestId);

  const update = (nextRequestId: string, nextWindowId: string) => {
    setRequestId(nextRequestId);
    setWindowId(nextWindowId);
    onChange(
      nextRequestId === "" || nextWindowId === ""
        ? null
        : {
            event_type: "CLOUD_BLOCK",
            payload: { request_id: nextRequestId, window_id: nextWindowId },
          },
    );
  };

  return (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Request">
        <select
          aria-label="Request"
          value={requestId}
          onChange={(event) => update(event.target.value, "")}
          className={CONTROL_INPUT}
        >
          <option value="">Select request</option>
          {requestIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Observation window">
        <select
          aria-label="Window"
          value={windowId}
          onChange={(event) => update(requestId, event.target.value)}
          disabled={requestId === ""}
          className={`${CONTROL_INPUT} max-w-80`}
        >
          <option value="">
            {requestId !== "" && windowsForRequest.length === 0
              ? "No windows for this request"
              : "Select window"}
          </option>
          {windowsForRequest.map((window) => (
            <option key={window.id} value={window.id}>
              {`${window.id} (${clockTime(window.start)}–${clockTime(window.end)} UTC${
                window.valid ? "" : `, invalid · ${window.invalid_reason ?? "unknown"}`
              })`}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );
}

/** The one value BATTERY_DROP carries: the battery level the satellite drops to. */
function BatteryDropFields({
  satelliteId,
  batteryWh,
  capacityWh,
  onChange,
}: {
  satelliteId: string;
  batteryWh: number;
  capacityWh: number;
  onChange: (event: MissionEventRequest | null) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-3">
      <p className="text-[11px] text-neutral-400">
        {`${satelliteId} battery now `}
        <span className="tabular-nums text-neutral-200">{`${batteryWh.toFixed(1)} Wh`}</span>
        {` of ${capacityWh.toFixed(0)} Wh`}
      </p>
      <Field label="New battery (Wh)">
        <input
          aria-label="New battery (Wh)"
          type="number"
          min={0}
          max={capacityWh}
          step="any"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            const parsed = Number(event.target.value);
            onChange(
              event.target.value.trim() === "" || !Number.isFinite(parsed)
                ? null
                : {
                    event_type: "BATTERY_DROP",
                    payload: { satellite_id: satelliteId, new_battery_wh: parsed },
                  },
            );
          }}
          className={`${CONTROL_INPUT} w-28`}
        />
      </Field>
    </div>
  );
}

/**
 * An outage over an interval. Without station ids it is a payload outage:
 * the instrument cannot observe inside it. With station ids it is a
 * communication outage: that station's overlapping contacts are lost.
 */
function SatelliteOutageFields({
  satelliteId,
  simulatedTime,
  missionEnd,
  stationIds,
  onChange,
}: {
  satelliteId: string;
  simulatedTime: string;
  missionEnd: string;
  stationIds?: string[];
  onChange: (event: MissionEventRequest | null) => void;
}) {
  const [stationId, setStationId] = useState(stationIds?.[0] ?? "");
  const toInput = (iso: string) => iso.slice(0, 16);
  const fromInput = (value: string): string | null => {
    const iso = `${value}:00Z`;
    return Number.isNaN(Date.parse(iso)) ? null : iso;
  };
  const [start, setStart] = useState(toInput(simulatedTime));
  const [end, setEnd] = useState(toInput(missionEnd));

  const update = (nextStart: string, nextEnd: string, nextStation = stationId) => {
    setStart(nextStart);
    setEnd(nextEnd);
    setStationId(nextStation);
    const outageStart = fromInput(nextStart);
    const outageEnd = fromInput(nextEnd);
    if (outageStart === null || outageEnd === null) {
      onChange(null);
    } else if (stationIds) {
      onChange(
        nextStation === ""
          ? null
          : {
              event_type: "COMMUNICATION_OUTAGE",
              payload: { station_id: nextStation, outage_start: outageStart, outage_end: outageEnd },
            },
      );
    } else {
      onChange({
        event_type: "SATELLITE_UNAVAILABLE",
        payload: { satellite_id: satelliteId, outage_start: outageStart, outage_end: outageEnd },
      });
    }
  };

  return (
    <div className="flex flex-wrap items-end gap-2">
      {stationIds ? (
        <Field label="Station">
          <select
            aria-label="Station"
            value={stationId}
            onChange={(event) => update(start, end, event.target.value)}
            className={CONTROL_INPUT}
          >
            {stationIds.length === 0 ? <option value="">No mission stations</option> : null}
            {stationIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </Field>
      ) : null}
      <Field label="Outage start (UTC)">
        <input
          aria-label="Outage start (UTC)"
          type="datetime-local"
          value={start}
          onChange={(event) => update(event.target.value, end)}
          className={CONTROL_INPUT}
        />
      </Field>
      <Field label="Outage end (UTC)">
        <input
          aria-label="Outage end (UTC)"
          type="datetime-local"
          value={end}
          onChange={(event) => update(start, event.target.value)}
          className={CONTROL_INPUT}
        />
      </Field>
      <p className="text-[10px] text-neutral-500">
        {stationIds
          ? "Contacts at the station overlapping the span are lost; their downlinks fail validation."
          : `Actions overlapping the span on ${satelliteId} fail validation; frozen actions stay exempt.`}
      </p>
    </div>
  );
}

const EMERGENCY_FIELDS: { key: keyof EmergencyRequestForm; label: string; type: "text" | "number" | "datetime-local" }[] = [
  { key: "requestId", label: "Request id", type: "text" },
  { key: "priority", label: "Priority (1–5)", type: "number" },
  { key: "targetLat", label: "Target lat", type: "number" },
  { key: "targetLon", label: "Target lon", type: "number" },
  { key: "durationS", label: "Duration (s)", type: "number" },
  { key: "deadline", label: "Deadline (UTC)", type: "datetime-local" },
  { key: "energyCostWh", label: "Energy (Wh)", type: "number" },
  { key: "storageCostMb", label: "Storage (MB)", type: "number" },
  { key: "windowStart", label: "Window start (UTC)", type: "datetime-local" },
  { key: "windowEnd", label: "Window end (UTC)", type: "datetime-local" },
];

/** Optional cue evidence; blank for a manual arrival. */
const EVIDENCE_FIELDS: { key: keyof EmergencyRequestForm; label: string; type: "text" | "number" }[] = [
  { key: "source", label: "Evidence source", type: "text" },
  { key: "sourceEventId", label: "Source event id", type: "text" },
  { key: "mag", label: "Magnitude", type: "number" },
  { key: "sig", label: "Significance", type: "number" },
];

/** The new request and its one explicit window, as the EMERGENCY_TASK payload carries them. */
function EmergencyRequestFields({
  initial,
  satelliteId,
  orbital = false,
  onChange,
}: {
  initial: EmergencyRequestForm;
  satelliteId: string;
  orbital?: boolean;
  onChange: (event: MissionEventRequest | null) => void;
}) {
  const [form, setForm] = useState(initial);
  const windowId = emergencyWindowId(form.requestId.trim() || "…");
  const update = (key: keyof EmergencyRequestForm, value: string) => {
    const next = { ...form, [key]: value };
    setForm(next);
    onChange(buildEmergencyRequestEvent(next, satelliteId, orbital));
  };
  const evidence = emergencyEvidence(form);
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
        {EMERGENCY_FIELDS.filter(({ key }) => !orbital || (key !== "windowStart" && key !== "windowEnd")).map(({ key, label, type }) => (
          <Field key={key} label={label}>
            <input
              aria-label={label}
              type={type}
              step={type === "number" ? "any" : undefined}
              value={form[key] ?? ""}
              onChange={(event) => update(key, event.target.value)}
              className={CONTROL_INPUT}
            />
          </Field>
        ))}
      </div>
      <fieldset className="grid grid-cols-2 gap-x-2 gap-y-1.5 border-t border-[var(--amis-border)] pt-1.5">
        <legend className="text-[10px] uppercase tracking-wide text-neutral-500">Cue evidence (optional)</legend>
        {EVIDENCE_FIELDS.slice(0, 2).map(({ key, label, type }) => (
          <Field key={key} label={label}>
            <input aria-label={label} type={type} value={form[key] ?? ""} onChange={(event) => update(key, event.target.value)} className={CONTROL_INPUT} />
          </Field>
        ))}
        <Field label="Alert level">
          <select aria-label="Alert level" value={form.alertLevel ?? ""} onChange={(event) => update("alertLevel", event.target.value)} className={CONTROL_INPUT}>
            <option value="">none</option>
            {CUE_ALERT_LEVELS.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </Field>
        {EVIDENCE_FIELDS.slice(2).map(({ key, label, type }) => (
          <Field key={key} label={label}>
            <input aria-label={label} type={type} step="any" value={form[key] ?? ""} onChange={(event) => update(key, event.target.value)} className={CONTROL_INPUT} />
          </Field>
        ))}
      </fieldset>
      <p className={`text-[10px] ${"problem" in evidence ? "text-amber-300" : "text-neutral-500"}`}>
        {"problem" in evidence
          ? evidence.problem
          : "Leave blank for a manual arrival. With evidence: " + CUE_POLICY_NOTICE}
      </p>
      <p className="text-[10px] text-neutral-500">
        {orbital ? "Observation windows are computed from the stored orbit before the event is recorded." : `Enters through the event log with window ${windowId} on ${satelliteId}; the scenario itself stays unchanged.`}
      </p>
    </div>
  );
}

/**
 * The compact event dialog opened from the mission bar. It configures one of
 * the event types the backend accepts, injects it, and closes once the
 * backend has accepted it. Validation beyond "every field is readable" stays
 * with the backend, whose error code and message the workspace shows.
 */
export function EventControl({
  scenario,
  plan,
  missionState,
  windows,
  events,
  loading,
  onInjectEvent,
  onInjected,
}: {
  scenario: ScenarioSchema;
  plan: MissionPlanSchema;
  missionState: MissionStateSchema;
  windows: ObservationWindowSchema[];
  events: MissionEventSchema[];
  loading: boolean;
  onInjectEvent: (event: MissionEventRequest) => Promise<boolean>;
  onInjected: () => void;
}) {
  const [type, setType] = useState<MissionEventType>("CLOUD_BLOCK");
  const [configured, setConfigured] = useState<MissionEventRequest | null>(null);

  const requestIds = useMemo(
    () => missionRequestPool(scenario, events).map((request) => request.id),
    [scenario, events],
  );
  const [emergencyDefaults] = useState(() =>
    scenario.window_policy?.provider === "orbital"
      ? { ...emergencyRequestDefaults(missionState.simulated_time, requestIds), durationS: "30", deadline: scenario.end_time }
      : emergencyRequestDefaults(missionState.simulated_time, requestIds),
  );

  const chooseType = (next: MissionEventType) => {
    setType(next);
    setConfigured(null);
  };

  return (
    <div role="dialog" aria-label="Configure event" className="flex w-[30rem] flex-col gap-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[10px] uppercase tracking-wider text-neutral-400">Configure event</h3>
        <span className="text-[10px] text-neutral-500">
          {`evaluated against Plan V${plan.version} at ${clockTime(missionState.simulated_time)} UTC`}
        </span>
      </div>
      <div role="radiogroup" aria-label="Event type" className="flex gap-1">
        {EVENT_TYPES.map((option) => (
          <button
            key={option.type}
            type="button"
            role="radio"
            aria-checked={type === option.type}
            onClick={() => chooseType(option.type)}
            className={type === option.type ? EVENT_BUTTON_OPEN : CONTROL_BUTTON}
          >
            {option.label}
          </button>
        ))}
      </div>
      {type === "CLOUD_BLOCK" ? (
        <CloudBlockFields requestIds={requestIds} windows={windows} onChange={setConfigured} />
      ) : type === "BATTERY_DROP" ? (
        <BatteryDropFields
          satelliteId={missionState.satellite_id}
          batteryWh={missionState.battery_wh}
          capacityWh={scenario.satellite.battery_capacity_wh}
          onChange={setConfigured}
        />
      ) : type === "SATELLITE_UNAVAILABLE" ? (
        <SatelliteOutageFields
          satelliteId={missionState.satellite_id}
          simulatedTime={missionState.simulated_time}
          missionEnd={scenario.end_time}
          onChange={setConfigured}
        />
      ) : type === "COMMUNICATION_OUTAGE" ? (
        <SatelliteOutageFields
          key="comm"
          satelliteId={missionState.satellite_id}
          simulatedTime={missionState.simulated_time}
          missionEnd={scenario.end_time}
          stationIds={scenario.window_policy?.ground_station_ids ?? []}
          onChange={setConfigured}
        />
      ) : (
        <EmergencyRequestFields
          initial={emergencyDefaults}
          satelliteId={scenario.satellite.id}
          orbital={scenario.window_policy?.provider === "orbital"}
          onChange={setConfigured}
        />
      )}
      <div className="flex items-center justify-between gap-2 border-t border-[var(--amis-border)] pt-2">
        <span className="text-[10px] text-neutral-500">
          {configured === null ? "Complete the event to inject it." : "Event configured."}
        </span>
        <button
          type="button"
          onClick={async () => {
            if (configured !== null && (await onInjectEvent(configured))) {
              onInjected();
            }
          }}
          disabled={loading || configured === null}
          className={CONTROL_BUTTON}
        >
          {INJECT_LABEL[type]}
        </button>
      </div>
    </div>
  );
}
