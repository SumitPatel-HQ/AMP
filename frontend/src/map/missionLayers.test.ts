import { describe, expect, it } from "vitest";
import { cueEvent, missionState, plan, scenario } from "../test/mapFixtures";
import { buildMissionLayers, CUES_LAYER_ID, TARGETS_LAYER_ID } from "./missionLayers";
import { buildMissionMapModel, type MapCue, type MapTarget } from "./missionMapModel";
import { DEFAULT_VISIBILITY, SELECTED_COLOR } from "./palette";

const model = buildMissionMapModel(scenario, plan, missionState, []);

function layerIds(layers: ReturnType<typeof buildMissionLayers>): string[] {
  return layers.map((layer) => layer.id);
}

describe("mission map layers", () => {
  it("stacks sequence, event rings, targets, labels and satellite in that order", () => {
    const layers = buildMissionLayers({ model, selectedRequestId: null, visibility: DEFAULT_VISIBILITY });

    expect(layerIds(layers)).toEqual([
      "amis-plan-sequence",
      "amis-event-rings",
      TARGETS_LAYER_ID,
      "amis-target-labels",
      "amis-satellite",
      "amis-satellite-label",
    ]);
  });

  it("outlines only the selected target in the selection colour", () => {
    const layers = buildMissionLayers({ model, selectedRequestId: "OBS-B", visibility: DEFAULT_VISIBILITY });
    const targets = layers.find((layer) => layer.id === TARGETS_LAYER_ID);
    if (targets === undefined) throw new Error("targets layer missing");
    const { getLineColor } = targets.props as unknown as {
      getLineColor: (target: MapTarget) => number[];
    };

    expect(getLineColor(model.targets[1])).toEqual([...SELECTED_COLOR, 255]);
    expect(getLineColor(model.targets[0])).not.toEqual([...SELECTED_COLOR, 255]);
  });

  it("drops the overlays that are switched off but always keeps the targets", () => {
    const layers = buildMissionLayers({
      model,
      selectedRequestId: null,
      visibility: { labels: false, sequence: false, satellite: false, events: false, cues: false },
    });

    expect(layerIds(layers)).toEqual([TARGETS_LAYER_ID]);
  });
});

describe("cue marker layer", () => {
  const cueModel = buildMissionMapModel(scenario, plan, missionState, [cueEvent]);

  it("draws cue markers beneath the targets and outlines the selected cue event", () => {
    const layers = buildMissionLayers({
      model: cueModel,
      selectedRequestId: null,
      selectedEventId: "EVT-004",
      visibility: DEFAULT_VISIBILITY,
    });
    const ids = layerIds(layers);
    expect(ids.indexOf(CUES_LAYER_ID)).toBeLessThan(ids.indexOf(TARGETS_LAYER_ID));
    const cues = layers.find((layer) => layer.id === CUES_LAYER_ID);
    if (cues === undefined) throw new Error("cue layer missing");
    const { getLineColor } = cues.props as unknown as { getLineColor: (cue: MapCue) => number[] };
    expect(getLineColor(cueModel.cues![0])).toEqual([...SELECTED_COLOR, 255]);
  });

  it("is switched off with its own layer toggle", () => {
    const layers = buildMissionLayers({
      model: cueModel,
      selectedRequestId: null,
      visibility: { ...DEFAULT_VISIBILITY, cues: false },
    });
    expect(layerIds(layers)).not.toContain(CUES_LAYER_ID);
  });
});
