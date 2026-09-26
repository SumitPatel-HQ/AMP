import { useEffect, useMemo, useRef, useState } from "react";
import type { MissionMapEngine } from "../map/missionMapEngine";
import { buildMissionMapModel } from "../map/missionMapModel";
import { DEFAULT_VISIBILITY } from "../map/palette";
import { fetchGroundStations, fetchOrbitalElements, parseTle, validateScenario } from "../api/amis";
import type { GroundStationSchema, ObservationRequestSchema, OrbitalElementsSchema, ScenarioPreviewSchema, ScenarioSchema } from "../api/client";

const input = "w-full rounded border border-neutral-700 bg-neutral-950 px-2 py-1 text-xs text-neutral-100";
const button = "rounded border border-neutral-600 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800 disabled:opacity-40";
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
    window_policy: { provider: "orbital", max_off_nadir_deg: 30, min_sun_elevation_deg: 10, settling_time_s: 0, culmination_placement: false, ground_station_ids: [], downlink_rate_mb_s: 0 },
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

function BuilderMap({ draft, track, onPick }: { draft: ScenarioSchema; track: ScenarioPreviewSchema["ground_track"]; onPick: (lon: number, lat: number) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const engine = useRef<MissionMapEngine | null>(null);
  const pick = useRef(onPick);
  const model = useMemo(() => buildMissionMapModel(draft, null, null, [], new Set(), track), [draft, track]);
  const currentModel = useRef(model);
  useEffect(() => { pick.current = onPick; }, [onPick]);
  useEffect(() => { currentModel.current = model; }, [model]);
  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    import("../map/missionMapEngine").then(({ createMissionMapEngine }) => {
      if (cancelled || !container.current) return;
      engine.current = createMissionMapEngine(container.current, {
        onPickTarget: () => {}, onPickCoordinate: (lon, lat) => pick.current(lon, lat),
        onHover: () => {}, onBasemap: () => {},
      });
      engine.current.render({ model: currentModel.current, selectedRequestId: null, visibility: DEFAULT_VISIBILITY });
    });
    return () => { cancelled = true; engine.current?.destroy(); engine.current = null; };
  }, []);
  useEffect(() => { engine.current?.render({ model, selectedRequestId: null, visibility: DEFAULT_VISIBILITY }); }, [model]);
  return <div ref={container} className="h-full min-h-72 w-full" aria-label="Click map to add target" />;
}

export function MissionBuilder({ onClose, onCreate }: {
  onClose: () => void; onCreate: (draft: ScenarioSchema) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState<ScenarioSchema>(initialDraft);
  const [catalogue, setCatalogue] = useState<OrbitalElementsSchema[]>([]);
  const [stations, setStations] = useState<GroundStationSchema[]>([]);
  useEffect(() => {
    fetchGroundStations().then(setStations).catch(() => setStations([]));
  }, []);
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
      validateScenario(draft).then((result) => { if (active) setPreview(result); })
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

  return <div className="fixed inset-0 z-50 flex flex-col bg-[#0b0d10] text-neutral-100" role="dialog" aria-label="New mission">
    <div className="flex items-center gap-3 border-b border-neutral-700 px-4 py-2">
      <strong>New mission</strong><span className="text-xs text-neutral-500">Times are UTC. Click the map to add a target.</span>
      <div className="ml-auto flex gap-2">
        <label className={button}>Import JSON<input type="file" accept="application/json,.json" className="hidden" onChange={async (event) => {
          const file = event.target.files?.[0]; if (!file) return;
          try { imported.current = true; setDraft(JSON.parse(await file.text()) as ScenarioSchema); setFailure(null); }
          catch (error) { setFailure(`Invalid JSON: ${String(error)}`); }
        }} /></label>
        <button className={button} onClick={exportJson}>Export JSON</button>
        <button className={button} onClick={onClose}>Close</button>
      </div>
    </div>
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(420px,560px)_1fr]">
      <div className="space-y-4 overflow-y-auto border-r border-neutral-700 p-4 text-xs">
        <section className="grid grid-cols-2 gap-2">
          <label className="col-span-2">Mission id<input className={input} value={draft.id} onChange={(event) => setDraft({ ...draft, id: event.target.value })} /></label>
          <label className="col-span-2">Mission name<input className={input} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>Start UTC<input className={input} type="datetime-local" value={utcInput(draft.start_time)} onChange={(event) => setDraft({ ...draft, start_time: fromUtcInput(event.target.value) })} /></label>
          <label>End UTC<input className={input} type="datetime-local" value={utcInput(draft.end_time)} onChange={(event) => setDraft({ ...draft, end_time: fromUtcInput(event.target.value), requests: draft.requests.map((item) => ({ ...item, deadline: fromUtcInput(event.target.value) })) })} /></label>
          <label>Window source<select className={input} value={draft.window_policy?.provider ?? "synthetic"} onChange={(event) => updatePolicy({ provider: event.target.value as "orbital" | "synthetic" | "canonical_demo" })}>
            <option value="orbital">Orbital</option><option value="synthetic">Synthetic</option><option value="canonical_demo">Canonical demo</option>
          </select></label>
          <label>Satellite catalogue<select className={input} value={draft.satellite.orbit?.norad_id ?? ""} onChange={(event) => updateSatellite({ orbit: catalogue.find((item) => item.norad_id === Number(event.target.value)) ?? null })}>
            <option value="">Select satellite</option>{draft.satellite.orbit && !catalogue.some((item) => item.norad_id === draft.satellite.orbit?.norad_id) && <option value={draft.satellite.orbit.norad_id}>{draft.satellite.orbit.name} · pasted TLE</option>}{catalogue.map((item) => <option key={item.norad_id} value={item.norad_id}>{item.name} · {item.norad_id} · {item.epoch.slice(0, 10)}</option>)}
          </select></label>
          <label>Max off-nadir °<input className={input} type="number" min="0" max="60" value={draft.window_policy?.max_off_nadir_deg ?? 30} onChange={(event) => updatePolicy({ max_off_nadir_deg: Number(event.target.value) })} /></label>
          <label>Min Sun elevation °<input className={input} type="number" min="-10" max="60" disabled={draft.window_policy?.min_sun_elevation_deg === null} value={draft.window_policy?.min_sun_elevation_deg ?? 10} onChange={(event) => updatePolicy({ min_sun_elevation_deg: Number(event.target.value) })} />
            <span className="flex gap-1"><input type="checkbox" checked={draft.window_policy?.min_sun_elevation_deg === null} onChange={(event) => updatePolicy({ min_sun_elevation_deg: event.target.checked ? null : 10 })} /> No daylight requirement</span>
          </label>
          <label>Settling time (s)<input className={input} type="number" min="0" step="any" value={draft.window_policy?.settling_time_s ?? 0} onChange={(event) => updatePolicy({ settling_time_s: Number(event.target.value) })} /></label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={draft.window_policy?.culmination_placement ?? false} onChange={(event) => updatePolicy({ culmination_placement: event.target.checked })} />Place at window culmination</label>
          <fieldset className="col-span-full flex flex-wrap items-center gap-2"><legend>Ground stations (downlink)</legend>
            {stations.map((station) => {
              const selected = draft.window_policy?.ground_station_ids ?? [];
              return <label key={station.id} className="flex items-center gap-1"><input type="checkbox" checked={selected.includes(station.id)} onChange={(event) => updatePolicy({ ground_station_ids: event.target.checked ? [...selected, station.id] : selected.filter((id) => id !== station.id) })} />{station.name} · {station.min_elevation_deg}°</label>;
            })}
          </fieldset>
          <label>Downlink rate (MB/s)<input className={input} type="number" min="0" step="any" value={draft.window_policy?.downlink_rate_mb_s ?? 0} onChange={(event) => updatePolicy({ downlink_rate_mb_s: Number(event.target.value) })} /></label>
        </section>
        <p className="text-[10px] text-neutral-500">The orbit is published data. Pointing limits and resource values describe a hypothetical agile imager.</p>
        <details><summary className="cursor-pointer">Paste a TLE pair</summary><div className="space-y-2 pt-2">
          <input className={input} value={tle.name} onChange={(event) => setTle({ ...tle, name: event.target.value })} aria-label="TLE satellite name" />
          <input className={input} value={tle.line1} onChange={(event) => setTle({ ...tle, line1: event.target.value })} placeholder="Line 1" />
          <input className={input} value={tle.line2} onChange={(event) => setTle({ ...tle, line2: event.target.value })} placeholder="Line 2" />
          <button className={button} onClick={async () => { try { updateSatellite({ orbit: await parseTle(tle.name, tle.line1, tle.line2) }); setFailure(null); } catch (error) { setFailure(String(error)); } }}>Use TLE</button>
        </div></details>
        <section><h3 className="mb-2 font-semibold">Satellite resources</h3><div className="grid grid-cols-2 gap-2">
          {(["battery_capacity_wh", "battery_charge_wh", "storage_capacity_mb", "storage_usage_mb"] as const).map((key) => <label key={key}>{key.replaceAll("_", " ")}<input className={input} type="number" min="0" value={draft.satellite[key]} onChange={(event) => updateSatellite({ [key]: Number(event.target.value) })} /></label>)}
          <label className="flex items-center gap-2"><input type="checkbox" checked={draft.satellite.available} onChange={(event) => updateSatellite({ available: event.target.checked })} />Available</label>
        </div></section>
        <section><div className="mb-2 flex items-center justify-between"><h3 className="font-semibold">Targets</h3><button className={button} onClick={() => addTarget()}>Add target</button></div>
          <div className="mb-2 grid grid-cols-2 gap-2">
            <label>Payload power (W)<input className={input} type="number" min="0" step="any" value={powerW} onChange={(event) => setPowerW(Number(event.target.value))} /></label>
            <label>Data rate (Mbit/s)<input className={input} type="number" min="0" step="any" value={dataRateMbps} onChange={(event) => setDataRateMbps(Number(event.target.value))} /></label>
            <p className="col-span-2 text-[10px] text-neutral-500">Starting costs come from power × duration and data rate × duration; stored costs stay editable per target.</p>
            <button className={`${button} col-span-2`} onClick={applyDerivedCosts}>Apply derived costs to all targets</button>
          </div>
          <div className="space-y-3">{draft.requests.map((request, index) => <div key={index} className="rounded border border-neutral-800 p-2">
            <div className="grid grid-cols-2 gap-2">
              {(["id", "target_name"] as const).map((key) => <label key={key}>{key.replace("_", " ")}<input className={input} value={request[key] ?? ""} onChange={(event) => updateRequest(index, { [key]: event.target.value })} /></label>)}
              {(["target_lat", "target_lon", "priority", "duration_s", "energy_cost_wh", "storage_cost_mb"] as const).map((key) => <label key={key}>{key.replaceAll("_", " ")}<input className={input} type="number" step="any" value={request[key]} onChange={(event) => updateRequest(index, { [key]: Number(event.target.value) })} /></label>)}
              <label className="col-span-2">Deadline UTC<input className={input} type="datetime-local" value={utcInput(request.deadline)} onChange={(event) => updateRequest(index, { deadline: fromUtcInput(event.target.value) })} /></label>
            </div><div className="mt-2 flex justify-between"><span>{preview?.window_counts[request.id] ?? "–"} windows</span><button className={button} onClick={() => setDraft((current) => ({ ...current, requests: current.requests.filter((_, at) => at !== index) }))}>Remove</button></div>
          </div>)}</div>
        </section>
        <section aria-label="Mission validation"><h3 className="font-semibold">Preview</h3>
          {failure && <p role="alert" className="text-red-400">{failure}</p>}
          {preview?.errors.map((message, index) => <p key={`e${index}`} className="text-red-400">{message}</p>)}
          {preview?.warnings.map((message, index) => <p key={`w${index}`} className="text-amber-300">{message}</p>)}
          {preview && preview.errors.length === 0 && preview.warnings.length === 0 && <p className="text-emerald-300">Ready to create</p>}
        </section>
        <button className={`${button} w-full border-sky-700 text-sky-200`} disabled={busy || !preview || preview.errors.length > 0 || draft.requests.length === 0} onClick={async () => { setBusy(true); const ok = await onCreate(draft); setBusy(false); if (ok) onClose(); }}>Create mission</button>
      </div>
      <div className="relative min-h-0"><BuilderMap draft={draft} track={preview?.ground_track ?? []} onPick={(lon, lat) => addTarget(lon, lat)} /><span className="pointer-events-none absolute left-3 top-3 rounded bg-black/80 px-2 py-1 text-xs">Click map to add a target</span></div>
    </div>
  </div>;
}
