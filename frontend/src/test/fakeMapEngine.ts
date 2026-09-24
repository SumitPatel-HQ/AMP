import type { MissionMapScene } from "../map/missionLayers";
import type {
  MissionMapEngine,
  MissionMapHandlers,
} from "../map/missionMapEngine";

/**
 * Stands in for the WebGL map, which jsdom cannot run. It records what the
 * panel asked it to draw and hands back the handlers so tests can play the
 * part of a pointer on the map.
 */
export const fakeMap = {
  scenes: [] as MissionMapScene[],
  handlers: null as MissionMapHandlers | null,
  fits: 0,
  zooms: [] as number[],
  lastScene(): MissionMapScene {
    const scene = this.scenes.at(-1);
    if (scene === undefined) throw new Error("the map has not rendered a scene");
    return scene;
  },
  reset() {
    this.scenes = [];
    this.handlers = null;
    this.fits = 0;
    this.zooms = [];
  },
};

export function createMissionMapEngine(
  _container: HTMLElement,
  handlers: MissionMapHandlers,
): MissionMapEngine {
  fakeMap.handlers = handlers;
  return {
    render: (scene) => fakeMap.scenes.push(scene),
    fitTargets: () => {
      fakeMap.fits += 1;
    },
    zoomBy: (delta) => fakeMap.zooms.push(delta),
    resize: () => {},
    destroy: () => {},
  };
}
