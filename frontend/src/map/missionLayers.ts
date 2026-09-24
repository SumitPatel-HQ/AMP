import type { Layer } from "@deck.gl/core";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { Coordinate, MapTarget, MissionMapModel, SatellitePlacement } from "./missionMapModel";
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

/** Everything one frame of the mission map depends on. */
export interface MissionMapScene {
  model: MissionMapModel;
  selectedRequestId: string | null;
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
export function buildMissionLayers({ model, selectedRequestId, visibility }: MissionMapScene): Layer[] {
  const layers: Layer[] = [];

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
