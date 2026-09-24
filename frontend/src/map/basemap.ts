import type {
  ExpressionSpecification,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import { feature } from "topojson-client";
import landTopology from "world-atlas/land-110m.json";
import type { GeometryCollection } from "topojson-specification";

/** A basemap the engine can try, in the order it tries them. */
export interface BasemapOption {
  name: string;
  style: string | StyleSpecification;
}

/**
 * Keyless dark vector styles first, then a style built from the bundled land
 * outline so the map still draws offline or when both tile hosts are down.
 */
export const BASEMAPS: BasemapOption[] = [
  { name: "OpenFreeMap", style: "https://tiles.openfreemap.org/styles/dark" },
  {
    name: "CARTO",
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  },
  { name: "Offline", style: offlineStyle() },
];

function offlineStyle(): StyleSpecification {
  const land = feature(landTopology, landTopology.objects.land as GeometryCollection);
  return {
    version: 8,
    sources: { land: { type: "geojson", data: land } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0b0d10" } },
      { id: "land", type: "fill", source: "land", paint: { "fill-color": "#16191e" } },
      {
        id: "coast",
        type: "line",
        source: "land",
        paint: { "line-color": "#2a2f37", "line-width": 0.6 },
      },
    ],
  };
}

/** Basemap labels that compete with mission targets rather than orient them. */
const NOISY_LABELS =
  /road|highway|oneway|street|transport|poi|housenum|water|marine|suburb|village|neighbourhood|hamlet|town|other|airport|rail|aeroway|park|building/i;

/** Latin names only, so a regional view never mixes three scripts per label. */
const LATIN_NAME: ExpressionSpecification = ["coalesce", ["get", "name:en"], ["get", "name:latin"], ["get", "name"]];

/**
 * Quiets whichever vector style loaded: drops road, point-of-interest and
 * minor-place labels, and mutes the countries, states and cities that remain,
 * so the basemap orients the reviewer without competing with the mission.
 */
export function tuneBasemap(map: MapLibreMap): void {
  for (const layer of map.getStyle().layers) {
    if (layer.type !== "symbol") continue;
    if (NOISY_LABELS.test(layer.id)) {
      map.setLayoutProperty(layer.id, "visibility", "none");
      continue;
    }
    if (map.getLayoutProperty(layer.id, "text-field") !== undefined) {
      map.setLayoutProperty(layer.id, "text-field", LATIN_NAME);
      map.setPaintProperty(layer.id, "text-color", "#4b5563");
      map.setPaintProperty(layer.id, "text-opacity", 0.8);
      map.setPaintProperty(layer.id, "text-halo-color", "#0b0d10");
      map.setPaintProperty(layer.id, "text-halo-width", 1.2);
    }
  }
}
