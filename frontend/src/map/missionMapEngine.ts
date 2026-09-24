import { MapLibreOverlay } from "@deck.gl/maplibre";
import type { PickingInfo } from "@deck.gl/core";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre finds its worker beside its own module file, which Vite's dependency
// bundling moves; bundling the worker explicitly gives it a stable URL.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { BASEMAPS, tuneBasemap } from "./basemap";
import {
  buildMissionLayers,
  type MissionMapScene,
  SATELLITE_LAYER_ID,
  TARGETS_LAYER_ID,
} from "./missionLayers";
import type { MapTarget } from "./missionMapModel";

/** What the pointer is over, in pixels relative to the map container. */
export interface MapHover {
  kind: "target" | "satellite";
  id: string;
  x: number;
  y: number;
}

export interface MissionMapHandlers {
  onPickTarget: (requestId: string) => void;
  onHover: (hover: MapHover | null) => void;
  onBasemap: (name: string) => void;
}

/** The imperative map the React panel drives; nothing else touches MapLibre. */
export interface MissionMapEngine {
  render: (scene: MissionMapScene) => void;
  fitTargets: () => void;
  zoomBy: (delta: number) => void;
  resize: () => void;
  destroy: () => void;
}

/** How long a basemap may take to load before the next one is tried. */
const BASEMAP_TIMEOUT_MS = 8000;

/**
 * A flat dark basemap (MapLibre) with the mission drawn over it as a deck.gl
 * overlay. The overlay runs non-interleaved so it survives basemap swaps and
 * stays independent of the style's own layers.
 */
export function createMissionMapEngine(
  container: HTMLElement,
  handlers: MissionMapHandlers,
): MissionMapEngine {
  let scene: MissionMapScene | null = null;
  let basemapIndex = 0;
  let styleReady = false;
  let fittedBounds: string | null = null;

  maplibregl.setWorkerUrl(maplibreWorkerUrl);

  const map = new maplibregl.Map({
    container,
    style: BASEMAPS[0].style,
    center: [20, 15],
    zoom: 1.2,
    minZoom: 0.6,
    maxZoom: 12,
    renderWorldCopies: false,
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
  });
  handlers.onBasemap(BASEMAPS[0].name);

  const nextBasemap = () => {
    if (styleReady || basemapIndex >= BASEMAPS.length - 1) {
      return;
    }
    basemapIndex += 1;
    map.setStyle(BASEMAPS[basemapIndex].style);
    handlers.onBasemap(BASEMAPS[basemapIndex].name);
    armTimeout();
  };

  let timeout: ReturnType<typeof setTimeout> | undefined;
  const armTimeout = () => {
    clearTimeout(timeout);
    timeout = setTimeout(nextBasemap, BASEMAP_TIMEOUT_MS);
  };
  armTimeout();

  map.on("style.load", () => {
    styleReady = true;
    clearTimeout(timeout);
    tuneBasemap(map);
  });
  // A style that fails to fetch reports here before it ever loads; tile errors
  // after load are left to MapLibre, which already retries them.
  map.on("error", () => {
    if (!styleReady) {
      nextBasemap();
    }
  });

  const overlay = new MapLibreOverlay({
    interleaved: false,
    layers: [],
    pickingRadius: 8,
    onClick: (info: PickingInfo) => {
      if (info.layer?.id === TARGETS_LAYER_ID && info.object !== undefined) {
        handlers.onPickTarget((info.object as MapTarget).requestId);
      }
    },
    onHover: (info: PickingInfo) => {
      if (info.object === undefined || info.layer === null) {
        handlers.onHover(null);
        return;
      }
      if (info.layer.id === TARGETS_LAYER_ID) {
        handlers.onHover({
          kind: "target",
          id: (info.object as MapTarget).requestId,
          x: info.x,
          y: info.y,
        });
      } else if (info.layer.id === SATELLITE_LAYER_ID) {
        handlers.onHover({ kind: "satellite", id: "satellite", x: info.x, y: info.y });
      }
    },
    getCursor: ({ isHovering }) => (isHovering ? "pointer" : "grab"),
  });
  map.addControl(overlay);

  const fitTargets = () => {
    const bounds = scene?.model.bounds;
    if (bounds === null || bounds === undefined) {
      return;
    }
    const [west, south, east, north] = bounds;
    // A lone target has no extent to fit, so it gets a regional zoom instead.
    if (west === east && south === north) {
      map.easeTo({ center: [west, south], zoom: 4, duration: 600 });
      return;
    }
    map.fitBounds(bounds, { padding: 70, maxZoom: 6, duration: 600 });
  };

  return {
    render(nextScene) {
      scene = nextScene;
      overlay.setProps({ layers: buildMissionLayers(nextScene) });
      // Frame the targets once per distinct target set, not on every render,
      // so a reviewer's own pan and zoom survive steps and replans.
      const key = JSON.stringify(nextScene.model.bounds);
      if (key !== fittedBounds) {
        fittedBounds = key;
        fitTargets();
      }
    },
    fitTargets,
    zoomBy(delta) {
      map.easeTo({ zoom: map.getZoom() + delta, duration: 250 });
    },
    resize() {
      map.resize();
    },
    destroy() {
      clearTimeout(timeout);
      // Removing the map removes its controls, which finalizes the overlay.
      map.remove();
    },
  };
}
