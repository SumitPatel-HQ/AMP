import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { MapContactTrack, MapStationFootprint } from "./contactTracks";
import type { Coordinate, MapCue, MapStation, MapTarget, MissionMapModel, SatellitePlacement } from "./missionMapModel";
import {
  EVENT_COLOR,
  type LayerVisibility,
  SATELLITE_COLOR,
  SELECTED_COLOR,
  SEQUENCE_COLOR,
  STATUS_COLORS,
} from "./palette";

export const TARGETS_LAYER_ID = "amis-targets";
export const SATELLITE_LAYER_ID = "amis-satellite";
export const CUES_LAYER_ID = "amis-cues";

/** Everything one frame of the mission map depends on. */
export interface MissionMapScene {
  model: MissionMapModel;
  selectedRequestId: string | null;
  /** The event the reviewer is following, so its cue marker can highlight. */
  selectedEventId?: string | null;
  visibility: LayerVisibility;
}

/** Higher priority draws a larger dot, so importance reads before colour. */
export function targetRadius(target: MapTarget): number {
  return 4 + target.priority * 1.2;
}

/**
 * The deck.gl layers for one scene, bottom to top: plan sequence, event rings,
 * targets, labels, satellite. Pure: the same scene always builds the same stack.
 */
export function buildMissionLayers({
  model,
  selectedRequestId,
  selectedEventId = null,
  visibility,
}: MissionMapScene): Layer[] {
  const layers: Layer[] = [];

  if (model.groundTrack?.length) {
    layers.push(new PathLayer<{ path: Coordinate[] }>({
      id: "amis-ground-track",
      data: model.groundTrack.map((path) => ({ path })),
      getPath: (item) => item.path as [number, number][],
      getColor: [249, 115, 22, 130], getWidth: 1.5, widthUnits: "pixels",
    }));
  }

  if (model.stationFootprints?.length) {
    layers.push(new ScatterplotLayer<MapStationFootprint>({
      id: "amis-station-footprints",
      data: model.stationFootprints.filter((footprint) => footprint.radiusM > 0),
      getPosition: (footprint) => [...footprint.coordinate],
      getRadius: (footprint) => footprint.radiusM,
      radiusUnits: "meters",
      stroked: true,
      filled: true,
      getFillColor: (footprint) => (footprint.inContact ? [56, 189, 248, 45] : [56, 189, 248, 12]),
      getLineColor: (footprint) => (footprint.inContact ? [125, 211, 252, 220] : [56, 189, 248, 90]),
      getLineWidth: 1,
      lineWidthUnits: "pixels",
      updateTriggers: { getFillColor: model.stationFootprints, getLineColor: model.stationFootprints },
    }));
  }

  if (model.contactTracks?.length) {
    layers.push(new PathLayer<{ path: Coordinate[]; track: MapContactTrack }>({
      id: "amis-contact-tracks",
      data: model.contactTracks.flatMap((track) => track.paths.map((path) => ({ path, track }))),
      getPath: (item) => item.path as [number, number][],
      getColor: (item) =>
        !item.track.valid ? [239, 68, 68, 200] : item.track.downlink ? [14, 165, 233, 255] : [125, 211, 252, 150],
      getWidth: (item) => (item.track.downlink ? 4 : 2.5),
      widthUnits: "pixels",
      capRounded: true,
    }));
  }

  if (model.stations?.length) {
    layers.push(new ScatterplotLayer<MapStation>({
      id: "amis-ground-stations",
      data: model.stations,
      getPosition: (station) => [...station.coordinate],
      getRadius: 6,
      radiusUnits: "pixels",
      stroked: true,
      filled: true,
      getFillColor: [56, 189, 248, 180],
      getLineColor: [224, 242, 254, 255],
      getLineWidth: 1.5,
      lineWidthUnits: "pixels",
      pickable: true,
    }));
  }

  if (visibility.sequence && model.planSequence.length > 1) {
    layers.push(
      new PathLayer<{ path: Coordinate[] }>({
        id: "amis-plan-sequence",
        data: [{ path: [...model.planSequence] }],
        getPath: (datum) => datum.path as [number, number][],
        getColor: [...SEQUENCE_COLOR, 110],
        getWidth: 1.5,
        widthUnits: "pixels",
        jointRounded: true,
        capRounded: true,
      }),
    );
  }

  if (visibility.events) {
    layers.push(
      new ScatterplotLayer<MapTarget>({
        id: "amis-event-rings",
        data: model.targets.filter((target) => target.eventIds.length > 0),
        getPosition: (target) => [...target.coordinate],
        getRadius: (target) => targetRadius(target) + 7,
        radiusUnits: "pixels",
        stroked: true,
        filled: true,
        getFillColor: [...EVENT_COLOR, 40],
        getLineColor: [...EVENT_COLOR, 230],
        getLineWidth: 1.5,
        lineWidthUnits: "pixels",
      }),
    );
  }

  if (visibility.cues && model.cues?.length) {
    // Drawn beneath the targets: the target keeps its own pick, the outer
    // ring picks the cue event that introduced it.
    layers.push(
      new ScatterplotLayer<MapCue>({
        id: CUES_LAYER_ID,
        data: model.cues,
        pickable: true,
        getPosition: (cue) => [...cue.coordinate],
        getRadius: 18,
        radiusUnits: "pixels",
        stroked: true,
        filled: true,
        getFillColor: [...EVENT_COLOR, 18],
        getLineColor: (cue) =>
          cue.evidence.eventId === selectedEventId ? [...SELECTED_COLOR, 255] : [...EVENT_COLOR, 200],
        getLineWidth: (cue) => (cue.evidence.eventId === selectedEventId ? 3 : 1.5),
        lineWidthUnits: "pixels",
        updateTriggers: { getLineColor: selectedEventId, getLineWidth: selectedEventId },
      }),
    );
  }

  layers.push(
    new ScatterplotLayer<MapTarget>({
      id: TARGETS_LAYER_ID,
      data: model.targets,
      pickable: true,
      getPosition: (target) => [...target.coordinate],
      getRadius: (target) =>
        target.requestId === selectedRequestId ? targetRadius(target) + 3 : targetRadius(target),
      radiusUnits: "pixels",
      stroked: true,
      getFillColor: (target) => [...STATUS_COLORS[target.status], 235],
      getLineColor: (target) =>
        target.requestId === selectedRequestId ? [...SELECTED_COLOR, 255] : [10, 10, 11, 220],
      getLineWidth: (target) => (target.requestId === selectedRequestId ? 3 : 1),
      lineWidthUnits: "pixels",
      updateTriggers: {
        getRadius: selectedRequestId,
        getLineColor: selectedRequestId,
        getLineWidth: selectedRequestId,
      },
    }),
  );

  if (visibility.labels) {
    layers.push(
      new TextLayer<MapTarget>({
        id: "amis-target-labels",
        data: model.targets,
        getPosition: (target) => [...target.coordinate],
        getText: (target) => target.requestId,
        getSize: 11,
        getColor: (target) =>
          target.requestId === selectedRequestId ? [245, 208, 254, 255] : [212, 214, 220, 210],
        getPixelOffset: (target) => [targetRadius(target) + 6, 0],
        getTextAnchor: "start",
        getAlignmentBaseline: "center",
        fontFamily: "ui-monospace, Cascadia Code, Consolas, monospace",
        fontWeight: 600,
        outlineWidth: 3,
        outlineColor: [10, 10, 11, 230],
        fontSettings: { sdf: true },
        updateTriggers: { getColor: selectedRequestId },
      }),
    );
  }

  if (visibility.satellite && model.satellite !== null) {
    layers.push(
      new ScatterplotLayer<SatellitePlacement>({
        id: SATELLITE_LAYER_ID,
        data: [model.satellite],
        pickable: true,
        getPosition: (satellite) => [...satellite.coordinate],
        getRadius: 6,
        radiusUnits: "pixels",
        stroked: true,
        getFillColor: [250, 250, 250, 255],
        getLineColor: [...SATELLITE_COLOR, 255],
        getLineWidth: 3,
        lineWidthUnits: "pixels",
      }),
      new TextLayer<SatellitePlacement>({
        id: "amis-satellite-label",
        data: [model.satellite],
        getPosition: (satellite) => [...satellite.coordinate],
        getText: (satellite) => satellite.satelliteId,
        getSize: 10,
        getColor: [...SATELLITE_COLOR, 255],
        getPixelOffset: [0, -16],
        getTextAnchor: "middle",
        getAlignmentBaseline: "bottom",
        fontFamily: "ui-monospace, Cascadia Code, Consolas, monospace",
        fontWeight: 700,
        outlineWidth: 3,
        outlineColor: [10, 10, 11, 230],
        fontSettings: { sdf: true },
      }),
    );
  }

  return layers;
}
