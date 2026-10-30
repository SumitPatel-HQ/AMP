import { ChevronDown, ChevronRight, Download, Maximize, Orbit, Plus, Trash2, Upload, X, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CONTROL_BUTTON, CONTROL_INPUT, REPLAN_BUTTON_PRIMARY } from "./controls";
import type { MissionMapEngine } from "../map/missionMapEngine";
import { buildMissionMapModel } from "../map/missionMapModel";
import { DEFAULT_VISIBILITY } from "../map/palette";
import { fetchGroundStations, fetchOrbitalElements, parseTle, validateScenario } from "../api/amis";
import type { GroundStationSchema, ObservationRequestSchema, OrbitalElementsSchema, ScenarioPreviewSchema, ScenarioSchema } from "../api/client";

const input = `${CONTROL_INPUT} w-full`;
const button = CONTROL_BUTTON;
const utcInput = (value: string) => value.slice(0, 16);
const fromUtcInput = (value: string) => `${value}:00Z`;

function initialDraft(): ScenarioSchema {
  const start = new Date();
  start.setUTCDate(start.getUTCDate() + 1);
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(start.getTime() + 3 * 86400000);
  return {
    id: `SCN-${crypto.randomUUID()}`, name: "New Earth observation mission",
    start_time: start.toISOString(), end_time: end.toISOString(),
    window_policy: { provider: "orbital", max_off_nadir_deg: 30, min_sun_elevation_deg: 10, settling_time_s: 0, culmination_placement: false, ground_station_ids: [], downlink_rate_mb_s: 0, slew_rate_deg_s: 0, recharge_rate_w: 0 },
    satellite: { id: "SAT-EO", battery_capacity_wh: 1000, battery_charge_wh: 1000,
      storage_capacity_mb: 4000, storage_usage_mb: 0, available: true },
    requests: [],
  };
}

/** Builder-side engineering defaults: power × duration for energy, data rate × duration for storage. */
export function deriveEnergyWh(powerW: number, durationS: number): number {
  return (powerW * durationS) / 3600;
}

export function deriveStorageMb(dataRateMbps: number, durationS: number): number {
  return (dataRateMbps * durationS) / 8;
}

function requestAt(lat: number, lon: number, deadline: string, index: number, powerW: number, dataRateMbps: number): ObservationRequestSchema {
  const durationS = 30;
  return {
    id: `OBS-${index}`, target_name: `Target ${index}`,
    target_lat: Math.round(lat * 100000) / 100000,
    target_lon: Math.round(lon * 100000) / 100000,
    priority: 3, duration_s: durationS, deadline,
    energy_cost_wh: Math.round(deriveEnergyWh(powerW, durationS) * 10) / 10,
    storage_cost_mb: Math.round(deriveStorageMb(dataRateMbps, durationS) * 10) / 10,
    status: "pending",
  };
}

function BuilderMap({ draft, track, onPick, onClearTargets }: { draft: ScenarioSchema; track: ScenarioPreviewSchema["ground_track"]; onPick: (lon: number, lat: number) => void; onClearTargets: () => void }) {
  const container = useRef<HTMLDivElement>(null);
  const engine = useRef<MissionMapEngine | null>(null);
  const [showTrack, setShowTrack] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const pick = useRef(onPick);
  const model = useMemo(() => buildMissionMapModel(draft, null, null, [], new Set(), showTrack ? track : []), [draft, track, showTrack]);
  const currentModel = useRef(model);
  useEffect(() => { pick.current = onPick; }, [onPick]);
  useEffect(() => { currentModel.current = model; }, [model]);
  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => engine.current?.resize());
    observer?.observe(container.current);
    import("../map/missionMapEngine").then(({ createMissionMapEngine }) => {
      if (cancelled || !container.current) return;
      engine.current = createMissionMapEngine(container.current, {
        onPickTarget: () => {}, onPickCoordinate: (lon, lat) => pick.current(lon, lat),
        onHover: () => {}, onBasemap: () => {},
      });
      engine.current.render({ model: currentModel.current, selectedRequestId: null, visibility: DEFAULT_VISIBILITY });
    }).catch((error: unknown) => { if (!cancelled) setMapError(String(error)); });
    return () => { observer?.disconnect(); cancelled = true; engine.current?.destroy(); engine.current = null; };
  }, []);
  useEffect(() => { engine.current?.render({ model, selectedRequestId: null, visibility: DEFAULT_VISIBILITY }); }, [model]);
  return <>
    <div ref={container} className="h-full min-h-0 w-full" aria-label="Click map to add target" />
    <div className="amis-builder-map-tools">
      <button type="button" className={`${button} text-red-300`} disabled={draft.requests.length === 0} onClick={onClearTargets}><Trash2 aria-hidden="true" size={15} />Remove all targets</button>
      <button type="button" className={button} aria-pressed={showTrack} onClick={() => setShowTrack(value => !value)}><Orbit aria-hidden="true" size={15} />{showTrack ? "Hide orbit track" : "Show orbit track"}</button>
    </div>
    <div className="absolute right-4 top-4 z-10 flex flex-col items-center rounded-xl border border-[var(--amis-border)] bg-[var(--amis-surface)]/95 p-1 shadow-lg shadow-black/50 backdrop-blur-sm" role="toolbar" aria-label="Map view controls">
      <button
        type="button"
        title="Fit targets"
        aria-label="Fit targets"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-300 transition-colors hover:bg-white/[0.08] hover:text-neutral-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
        onClick={() => engine.current?.fitTargets()}
      >
        <Maximize aria-hidden="true" size={16} />
      </button>
      <div className="my-1 h-[1px] w-5 bg-[var(--amis-border)]" />
      <button
        type="button"
        title="Zoom in"
        aria-label="Zoom in"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-300 transition-colors hover:bg-white/[0.08] hover:text-neutral-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
        onClick={() => engine.current?.zoomBy(1)}
      >
        <ZoomIn aria-hidden="true" size={16} />
      </button>
      <button
        type="button"
        title="Zoom out"
        aria-label="Zoom out"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-300 transition-colors hover:bg-white/[0.08] hover:text-neutral-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
        onClick={() => engine.current?.zoomBy(-1)}
      >
        <ZoomOut aria-hidden="true" size={16} />
      </button>
    </div>
    {mapError && <p role="alert" className="absolute bottom-4 left-4 right-4 rounded bg-red-950 p-3 text-sm text-red-200">Map unavailable. Add targets using the form. {mapError}</p>}
  </>;
}

export function MissionBuilder({ onClose, onCreate, onCreated }: {
  onCreated?: () => void;
  onClose: () => void; onCreate: (draft: ScenarioSchema) => Promise<boolean>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => { if (previous instanceof HTMLElement) previous.focus(); };
  }, []);
  const [draft, setDraft] = useState<ScenarioSchema>(initialDraft);
  const [catalogue, setCatalogue] = useState<OrbitalElementsSchema[]>([]);
  const [stations, setStations] = useState<GroundStationSchema[]>([]);
  useEffect(() => {
    fetchGroundStations().then(setStations).catch(() => setStations([]));
  }, []);
  const [validatedDraft, setValidatedDraft] = useState<ScenarioSchema | null>(null);
  const [preview, setPreview] = useState<ScenarioPreviewSchema | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [tle, setTle] = useState({ name: "Custom satellite", line1: "", line2: "" });
  const [busy, setBusy] = useState(false);
  const [powerW, setPowerW] = useState(800);
  const [dataRateMbps, setDataRateMbps] = useState(20);
  const imported = useRef(false);

  useEffect(() => {
    fetchOrbitalElements().then((items) => {
      setCatalogue(items);
      if (items[0] && !imported.current) {
        const epochDay = items[0].epoch.slice(0, 10);
        const start = new Date(`${epochDay}T00:00:00Z`);
        start.setUTCDate(start.getUTCDate() + 1);
        const end = new Date(start.getTime() + 3 * 86400000);
        setDraft((current) => ({ ...current, start_time: start.toISOString(), end_time: end.toISOString(),
          satellite: { ...current.satellite, orbit: items[0] } }));
      }
    }).catch((error: unknown) => setFailure(String(error)));
  }, []);

  useEffect(() => {
    let active = true;
    const timeout = setTimeout(() => {
      validateScenario(draft).then((result) => { if (active) { setPreview(result); setValidatedDraft(draft); } })
        .catch((error: unknown) => { if (active) setFailure(String(error)); });
    }, 450);
    return () => { active = false; clearTimeout(timeout); };
  }, [draft]);

  const updateRequest = (index: number, patch: Partial<ObservationRequestSchema>) =>
    setDraft((current) => ({ ...current, requests: current.requests.map((item, at) => at === index ? { ...item, ...patch } : item) }));
  const addTarget = (lon = 77.59, lat = 12.97) => setDraft((current) => {
    const ids = new Set(current.requests.map((item) => item.id));
    let next = 1;
    while (ids.has(`OBS-${next}`)) next += 1;
    return { ...current, requests: [...current.requests, requestAt(lat, lon, current.end_time, next, powerW, dataRateMbps)] };
  });
  const applyDerivedCosts = () => setDraft((current) => ({
    ...current,
    requests: current.requests.map((item) => ({
      ...item,
      energy_cost_wh: Math.round(deriveEnergyWh(powerW, item.duration_s) * 10) / 10,
      storage_cost_mb: Math.round(deriveStorageMb(dataRateMbps, item.duration_s) * 10) / 10,
    })),
  }));
  const updateSatellite = (patch: Partial<ScenarioSchema["satellite"]>) =>
    setDraft((current) => ({ ...current, satellite: { ...current.satellite, ...patch } }));
  const updatePolicy = (patch: Partial<NonNullable<ScenarioSchema["window_policy"]>>) =>
    setDraft((current) => ({ ...current, window_policy: { ...current.window_policy!, ...patch } }));

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `${draft.id}.json`; link.click(); URL.revokeObjectURL(url);
  };

  return <div ref={dialogRef} className="amis-builder fixed inset-0 z-50 flex flex-col text-neutral-100" role="dialog" aria-modal="true" aria-label="New mission" onKeyDown={event => {
    if (event.key === "Escape" && !busy) { event.stopPropagation(); onClose(); }
    if (event.key !== "Tab") return;
    const items = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]') ?? []).filter(item => item.getClientRects().length > 0);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }}>
    <div className="amis-builder-header">
      <div className="amis-builder-heading"><h1 className="shrink-0 text-sm font-semibold">New mission</h1><p className="text-xs text-neutral-400">All times UTC · Click the map to add targets</p></div>
      <div className="ml-auto flex gap-2">
        <label className={`${button} relative inline-flex items-center overflow-hidden`}><Upload aria-hidden="true" size={15} />Import JSON<input aria-label="Import mission JSON" type="file" accept="application/json,.json" className="absolute inset-0 w-full cursor-pointer opacity-0" onChange={async (event) => {
          const file = event.target.files?.[0]; if (!file) return;
          try { imported.current = true; setDraft(JSON.parse(await file.text()) as ScenarioSchema); setFailure(null); }
          catch (error) { setFailure(`Invalid JSON: ${String(error)}`); }
        }} /></label>
        <button className={button} onClick={exportJson}><Download aria-hidden="true" size={15} />Export JSON</button>
        <button className={button} disabled={busy} onClick={onClose}>Back / Cancel</button>
        <button className={button} disabled={busy} onClick={onClose}><X aria-hidden="true" size={15} />Close</button>
      </div>
    </div>
    <div className="amis-builder-layout grid min-h-0 flex-1">
      <div className="amis-builder-sidebar flex min-h-0 flex-col">
      <div className="amis-builder-form space-y-5 overflow-y-auto p-5 text-[13px]">
        <section aria-label="Mission details" className="grid grid-cols-2 gap-3">
          <h2 className="col-span-2">Mission details</h2>
          <label className="col-span-2">Mission id<input className={input} value={draft.id} onChange={(event) => setDraft({ ...draft, id: event.target.value })} /></label>
          <label className="col-span-2">Mission name<input className={input} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>Start UTC<input className={input} type="datetime-local" value={utcInput(draft.start_time)} onChange={(event) => setDraft({ ...draft, start_time: fromUtcInput(event.target.value) })} /></label>
          <label>End UTC<input className={input} type="datetime-local" value={utcInput(draft.end_time)} onChange={(event) => setDraft({ ...draft, end_time: fromUtcInput(event.target.value), requests: draft.requests.map((item) => ({ ...item, deadline: fromUtcInput(event.target.value) })) })} /></label>
        </section>
        <section aria-label="Orbit and access" className="grid grid-cols-2 gap-3">
          <h2 className="col-span-2">Orbit & access</h2>
          <label>Window source<span className="amis-builder-select"><select className={input} value={draft.window_policy?.provider ?? "synthetic"} onChange={(event) => updatePolicy({ provider: event.target.value as "orbital" | "synthetic" | "canonical_demo" })}>
            <option value="orbital">Orbital</option><option value="synthetic">Synthetic</option><option value="canonical_demo">Canonical demo</option>
          </select><ChevronDown size={16} aria-hidden="true" /></span></label>
          <label>Satellite catalogue<span className="amis-builder-select"><select className={input} value={draft.satellite.orbit?.norad_id ?? ""} onChange={(event) => updateSatellite({ orbit: catalogue.find((item) => item.norad_id === Number(event.target.value)) ?? null })}>
            <option value="">Select satellite</option>{draft.satellite.orbit && !catalogue.some((item) => item.norad_id === draft.satellite.orbit?.norad_id) && <option value={draft.satellite.orbit.norad_id}>{draft.satellite.orbit.name} · pasted TLE</option>}{catalogue.map((item) => <option key={item.norad_id} value={item.norad_id}>{item.name} · {item.norad_id} · {item.epoch.slice(0, 10)}</option>)}
          </select><ChevronDown size={16} aria-hidden="true" /></span></label>
          <label>Max off-nadir °<input className={input} type="number" min="0" max="60" value={draft.window_policy?.max_off_nadir_deg ?? 30} onChange={(event) => updatePolicy({ max_off_nadir_deg: Number(event.target.value) })} /></label>
          <label>Min Sun elevation °<input className={input} type="number" min="-10" max="60" disabled={draft.window_policy?.min_sun_elevation_deg === null} value={draft.window_policy?.min_sun_elevation_deg ?? 10} onChange={(event) => updatePolicy({ min_sun_elevation_deg: Number(event.target.value) })} /></label>
          <label>Settling time (s)<input className={input} type="number" min="0" step="any" value={draft.window_policy?.settling_time_s ?? 0} onChange={(event) => updatePolicy({ settling_time_s: Number(event.target.value) })} /></label>
          <div className="amis-builder-options col-span-full">
            <label className="amis-builder-checkbox"><input type="checkbox" checked={draft.window_policy?.min_sun_elevation_deg === null} onChange={(event) => updatePolicy({ min_sun_elevation_deg: event.target.checked ? null : 10 })} /><span>No daylight requirement</span></label>
            <label className="amis-builder-checkbox"><input type="checkbox" checked={draft.window_policy?.culmination_placement ?? false} onChange={(event) => updatePolicy({ culmination_placement: event.target.checked })} /><span>Place at window culmination</span></label>
          </div>
          <fieldset className="amis-builder-stations col-span-full"><legend>Ground stations (downlink)</legend>
            {stations.map((station) => {
              const selected = draft.window_policy?.ground_station_ids ?? [];
              return <label key={station.id} className="amis-builder-checkbox"><input type="checkbox" checked={selected.includes(station.id)} onChange={(event) => updatePolicy({ ground_station_ids: event.target.checked ? [...selected, station.id] : selected.filter((id) => id !== station.id) })} /><span>{station.name} <span className="text-neutral-400">· {station.min_elevation_deg}°</span></span></label>;
            })}
          </fieldset>
          <label>Downlink rate (MB/s)<input className={input} type="number" min="0" step="any" value={draft.window_policy?.downlink_rate_mb_s ?? 0} onChange={(event) => updatePolicy({ downlink_rate_mb_s: Number(event.target.value) })} /></label>
        </section>
        <p className="text-[12px] text-neutral-400">The orbit is published data. Pointing limits and resource values describe a hypothetical agile imager.</p>
        <details className="amis-builder-tle"><summary className="cursor-pointer"><ChevronRight size={15} aria-hidden="true" />Paste a TLE pair</summary><div className="space-y-2 pt-2">
          <input className={input} value={tle.name} onChange={(event) => setTle({ ...tle, name: event.target.value })} aria-label="TLE satellite name" />
          <input className={input} value={tle.line1} onChange={(event) => setTle({ ...tle, line1: event.target.value })} aria-label="TLE line 1" placeholder="Line 1" />
          <input className={input} value={tle.line2} onChange={(event) => setTle({ ...tle, line2: event.target.value })} aria-label="TLE line 2" placeholder="Line 2" />
          <button className={button} onClick={async () => { try { updateSatellite({ orbit: await parseTle(tle.name, tle.line1, tle.line2) }); setFailure(null); } catch (error) { setFailure(String(error)); } }}>Use TLE</button>
        </div></details>
        <section><h2 className="mb-3">Satellite resources</h2><div className="grid grid-cols-2 gap-2">
          {(["battery_capacity_wh", "battery_charge_wh", "storage_capacity_mb", "storage_usage_mb"] as const).map((key) => <label key={key}>{{battery_capacity_wh: "Battery capacity (Wh)", battery_charge_wh: "Battery charge (Wh)", storage_capacity_mb: "Storage capacity (MB)", storage_usage_mb: "Storage used (MB)"}[key]}<input className={input} type="number" min="0" value={draft.satellite[key]} onChange={(event) => updateSatellite({ [key]: Number(event.target.value) })} /></label>)}
          <label className="amis-builder-checkbox"><input type="checkbox" checked={draft.satellite.available} onChange={(event) => updateSatellite({ available: event.target.checked })} />Available</label>
        </div></section>
        <section><div className="mb-2 flex items-center justify-between"><h2>Targets <span className="ml-2 text-xs font-normal text-neutral-400">{draft.requests.length} added</span></h2><button className={button} onClick={() => addTarget()}><Plus aria-hidden="true" size={15} />Add target</button></div>
          <div className="mb-2 grid grid-cols-2 gap-2">
            <label>Payload power (W)<input className={input} type="number" min="0" step="any" value={powerW} onChange={(event) => setPowerW(Number(event.target.value))} /></label>
            <label>Data rate (Mbit/s)<input className={input} type="number" min="0" step="any" value={dataRateMbps} onChange={(event) => setDataRateMbps(Number(event.target.value))} /></label>
            <p className="col-span-2 text-[12px] text-neutral-400">Starting costs come from power × duration and data rate × duration; stored costs stay editable per target.</p>
            <button className={`${button} col-span-2`} onClick={applyDerivedCosts}>Apply derived costs to all targets</button>
          </div>
          {draft.requests.length === 0 && <p className="mb-3 rounded-md border border-dashed border-[var(--amis-border)] p-4 text-neutral-400">No targets yet. Click anywhere on the map, or use Add target to enter coordinates.</p>}
          <div className="space-y-3">{draft.requests.map((request, index) => <div key={index} className="amis-builder-target rounded-md p-4">
            <div className="mb-3 flex items-center gap-2"><span className="font-mono text-sky-300">{request.id}</span><span className="truncate font-medium">{request.target_name}</span></div>
            <div className="grid grid-cols-2 gap-3">
              {(["id", "target_name", "requester_id"] as const).map((key) => <label key={key}>{key.replace("_", " ")}<input className={input} value={request[key] ?? ""} onChange={(event) => updateRequest(index, { [key]: key === "requester_id" && event.target.value === "" ? undefined : event.target.value })} /></label>)}
              {(["target_lat", "target_lon", "priority", "duration_s", "energy_cost_wh", "storage_cost_mb"] as const).map((key) => <label key={key}>{key.replaceAll("_", " ")}<input className={input} type="number" step="any" value={request[key]} onChange={(event) => updateRequest(index, { [key]: Number(event.target.value) })} /></label>)}
              <label className="col-span-2">Deadline UTC<input className={input} type="datetime-local" value={utcInput(request.deadline)} onChange={(event) => updateRequest(index, { deadline: fromUtcInput(event.target.value) })} /></label>
            </div><div className="mt-2 flex justify-between"><span>{preview?.window_counts[request.id] ?? "–"} windows</span><button className={button} onClick={() => setDraft((current) => ({ ...current, requests: current.requests.filter((_, at) => at !== index) }))}>Remove</button></div>
          </div>)}</div>
        </section>
      </div>
      <div className="amis-builder-footer">
        <section aria-label="Mission validation" aria-live="polite"><h2 className="mb-1 text-sm font-semibold">Validation</h2>
          {failure && <p role="alert" className="text-red-400">{failure}</p>}
          {preview?.errors.map((message, index) => <p key={`e${index}`} className="text-red-400">{message}</p>)}
          {preview?.warnings.map((message, index) => <p key={`w${index}`} className="text-amber-300">{message}</p>)}
          {validatedDraft !== draft ? <p className="text-neutral-400">Checking mission configuration…</p> : draft.requests.length === 0 ? <p className="text-neutral-400">Add at least one target to create your mission.</p> : preview && preview.errors.length === 0 && preview.warnings.length === 0 ? <p className="text-emerald-300">Ready to create · {draft.requests.length} target{draft.requests.length === 1 ? "" : "s"}</p> : null}
        </section>
        <button className={`${REPLAN_BUTTON_PRIMARY} mt-3 w-full`} disabled={busy || validatedDraft !== draft || !preview || preview.errors.length > 0 || draft.requests.length === 0} onClick={async () => { setBusy(true); try { const ok = await onCreate(draft); if (ok) (onCreated ?? onClose)(); } catch (error) { setFailure(String(error)); } finally { setBusy(false); } }}>{busy ? "Creating mission…" : "Create mission"}</button>
      </div></div>
      <div className="amis-builder-map relative min-h-0"><BuilderMap draft={draft} track={preview?.ground_track ?? []} onPick={(lon, lat) => addTarget(lon, lat)} onClearTargets={() => setDraft(current => ({ ...current, requests: [] }))} /></div>
    </div>
  </div>;
}
