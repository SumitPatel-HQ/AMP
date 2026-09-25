import { useEffect, useMemo, useRef, useState } from "react";
import type {
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationRequestSchema,
  ScenarioSchema,
} from "../api/client";
import type { MapHover, MissionMapEngine } from "../map/missionMapEngine";
import { buildMissionMapModel, type MissionMapModel } from "../map/missionMapModel";
import { expiredRequestIds } from "../state/requestStatus";
import {
  cssColor,
  DEFAULT_VISIBILITY,
  EVENT_COLOR,
  type LayerVisibility,
  SATELLITE_COLOR,
  SELECTED_COLOR,
  STATUS_COLORS,
  STATUS_LABELS,
} from "../map/palette";
import { clockTime } from "./format";
import { PanelFrame } from "./PanelFrame";

const LAYER_TOGGLES: { key: keyof LayerVisibility; label: string }[] = [
  { key: "labels", label: "Labels" },
  { key: "sequence", label: "Plan sequence" },
  { key: "satellite", label: "Satellite" },
  { key: "events", label: "Event impact" },
];

const OVERLAY_BOX =
  "border border-[var(--amis-border)] bg-[#0b0d10]/90 text-[10px] text-neutral-300 backdrop-blur-sm";

function LayersBox({
  visibility,
  onToggle,
}: {
  visibility: LayerVisibility;
  onToggle: (key: keyof LayerVisibility) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className={`${OVERLAY_BOX} absolute left-2 top-2 w-36`}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between px-2 py-1 uppercase tracking-wider text-neutral-400 hover:text-neutral-200"
      >
        Layers <span aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <ul aria-label="Map layers" className="border-t border-[var(--amis-border)] py-1">
          {LAYER_TOGGLES.map(({ key, label }) => (
            <li key={key}>
              <label className="flex cursor-pointer items-center gap-2 px-2 py-0.5 uppercase tracking-wide hover:bg-white/[0.04]">
                <input
                  type="checkbox"
                  checked={visibility[key]}
                  onChange={() => onToggle(key)}
                  className="h-3 w-3 accent-sky-500"
                />
                {label}
              </label>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function MapControls({ engine }: { engine: MissionMapEngine | null }) {
  const button =
    "flex h-6 w-6 items-center justify-center text-sm text-neutral-300 hover:bg-white/[0.06] disabled:opacity-40";
  return (
    <div className={`${OVERLAY_BOX} absolute right-2 top-2 flex flex-col divide-y divide-[var(--amis-border)]`}>
      <button type="button" aria-label="Zoom in" disabled={engine === null} onClick={() => engine?.zoomBy(1)} className={button}>
        +
      </button>
      <button type="button" aria-label="Zoom out" disabled={engine === null} onClick={() => engine?.zoomBy(-1)} className={button}>
        −
      </button>
      <button type="button" aria-label="Fit targets" disabled={engine === null} onClick={() => engine?.fitTargets()} className={button}>
        ⌂
      </button>
    </div>
  );
}

function Swatch({ color, ring = false }: { color: string; ring?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-2 w-2 rounded-full"
      style={ring ? { boxShadow: `0 0 0 1.5px ${color}` } : { backgroundColor: color }}
    />
  );
}

function Legend() {
  return (
    <ul
      aria-label="Map legend"
      className={`${OVERLAY_BOX} absolute bottom-2 left-2 flex max-w-[calc(100%-6rem)] flex-wrap items-center gap-x-3 gap-y-0.5 px-2.5 py-1 uppercase tracking-wide`}
    >
      {(Object.keys(STATUS_COLORS) as (keyof typeof STATUS_COLORS)[]).map((status) => (
        <li key={status} className="flex items-center gap-1.5">
          <Swatch color={cssColor(STATUS_COLORS[status])} />
          {STATUS_LABELS[status]}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <Swatch color={cssColor(EVENT_COLOR)} ring />
        Event
      </li>
      <li className="flex items-center gap-1.5">
        <Swatch color={cssColor(SATELLITE_COLOR)} ring />
        Satellite
      </li>
      <li className="flex items-center gap-1.5">
        <Swatch color={cssColor(SELECTED_COLOR)} ring />
        Selected
      </li>
    </ul>
  );
}

/** The detail card beside whatever the pointer is over, read from the model. */
function HoverCard({ hover, model }: { hover: MapHover; model: MissionMapModel }) {
  const style = { left: hover.x + 14, top: hover.y + 14 };
  if (hover.kind === "satellite") {
    const satellite = model.satellite;
    if (satellite === null) return null;
    return (
      <div role="tooltip" style={style} className={`${OVERLAY_BOX} pointer-events-none absolute px-2 py-1.5`}>
        <p className="font-semibold text-orange-300">{satellite.satelliteId}</p>
        <p className="text-neutral-400">
          {satellite.overRequestId === null
            ? "at the last target its plan visited"
            : `observing ${satellite.overRequestId}`}
        </p>
        <p className="text-neutral-600">position read from the plan, not an orbit</p>
      </div>
    );
  }
  const target = model.targets.find((candidate) => candidate.requestId === hover.id);
  if (target === undefined) return null;
  return (
    <div role="tooltip" style={style} className={`${OVERLAY_BOX} pointer-events-none absolute min-w-40 px-2 py-1.5`}>
      <p className="flex items-center justify-between gap-3">
        <span className="font-semibold text-neutral-100">{target.requestId}</span>
        <span className="text-neutral-500">P{target.priority}</span>
      </p>
      <p style={{ color: cssColor(STATUS_COLORS[target.status]) }}>
        {STATUS_LABELS[target.status]}
        {target.action === null ? "" : ` · ${target.action.status}`}
      </p>
      {target.action === null ? null : (
        <p className="text-neutral-400">
          action {clockTime(target.action.start)}–{clockTime(target.action.end)} · {target.action.window_id}
        </p>
      )}
      {target.unscheduledReason === null ? null : (
        <p className="text-amber-300">{target.unscheduledReason}</p>
      )}
      <p className="text-neutral-500">deadline {clockTime(target.deadline)}</p>
      {target.eventIds.length === 0 ? null : (
        <p className="text-red-300">{target.eventIds.join(", ")}</p>
      )}
    </div>
  );
}

/**
 * The central spatial workspace: a dark vector basemap with the mission's
 * targets, plan sequence and inferred satellite position drawn over it.
 */
const NO_REQUESTS: readonly ObservationRequestSchema[] = [];

export function MissionMapPanel({
  scenario,
  plan,
  missionState,
  events,
  requestPool = NO_REQUESTS,
  selectedRequestId,
  onSelectRequest,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  /** The backend's request pool; only its expiry is read, the rest comes from the events. */
  requestPool?: readonly ObservationRequestSchema[];
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [engine, setEngine] = useState<MissionMapEngine | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<string | null>(null);
  const [hover, setHover] = useState<MapHover | null>(null);
  const [visibility, setVisibility] = useState<LayerVisibility>(DEFAULT_VISIBILITY);

  // The engine outlives renders, so it reads selection through a ref rather
  // than capturing the values from the render that created it.
  const selectionRef = useRef({ selectedRequestId, onSelectRequest });
  useEffect(() => {
    selectionRef.current = { selectedRequestId, onSelectRequest };
  }, [selectedRequestId, onSelectRequest]);

  const model = useMemo(
    () =>
      scenario === null
        ? null
        : buildMissionMapModel(
            scenario,
            plan,
            missionState,
            events,
            expiredRequestIds(requestPool),
          ),
    [scenario, plan, missionState, events, requestPool],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) return;
    let created: MissionMapEngine | null = null;
    let cancelled = false;
    let observer: ResizeObserver | null = null;

    // MapLibre and deck.gl load only once the map mounts, keeping them out of
    // the entry bundle.
    import("../map/missionMapEngine")
      .then(({ createMissionMapEngine }) => {
        if (cancelled) return;
        created = createMissionMapEngine(container, {
          onPickTarget: (requestId) => {
            const { selectedRequestId: current, onSelectRequest: select } = selectionRef.current;
            select(current === requestId ? null : requestId);
          },
          onHover: setHover,
          onBasemap: setBasemap,
        });
        setEngine(created);
        if (typeof ResizeObserver !== "undefined") {
          observer = new ResizeObserver(() => created?.resize());
          observer.observe(container);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setFailure(error instanceof Error ? error.message : String(error));
      });

    return () => {
      cancelled = true;
      observer?.disconnect();
      created?.destroy();
    };
  }, []);

  useEffect(() => {
    if (engine === null || model === null) return;
    engine.render({ model, selectedRequestId, visibility });
  }, [engine, model, selectedRequestId, visibility]);

  const meta = [
    scenario === null ? null : `${scenario.requests.length} targets`,
    basemap,
  ]
    .filter((part) => part !== null)
    .join(" · ");

  return (
    <PanelFrame title="Mission map" meta={meta || undefined} bodyClassName="relative overflow-hidden">
      {/* MapLibre makes its container position: relative, so the container
          fills a positioned wrapper rather than positioning itself. */}
      <div className="absolute inset-0 bg-[#0b0d10]">
        <div ref={containerRef} data-testid="mission-map" className="h-full w-full" />
      </div>
      {failure !== null ? (
        <p role="alert" className="absolute inset-x-0 top-1/2 text-center text-xs text-red-400">
          Map unavailable: {failure}
        </p>
      ) : scenario === null ? (
        <p className="absolute inset-x-0 top-1/2 text-center text-xs text-neutral-500">
          Load a scenario to see its observation targets.
        </p>
      ) : null}
      <LayersBox
        visibility={visibility}
        onToggle={(key) => setVisibility((current) => ({ ...current, [key]: !current[key] }))}
      />
      <MapControls engine={engine} />
      {scenario === null ? null : <Legend />}
      {hover !== null && model !== null ? <HoverCard hover={hover} model={model} /> : null}
    </PanelFrame>
  );
}
