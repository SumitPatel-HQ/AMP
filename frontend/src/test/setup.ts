import { afterEach, vi } from "vitest";
import { fakeMap } from "./fakeMapEngine";

// Every suite that renders the dashboard mounts the map, and jsdom has no
// WebGL, so the MapLibre/deck.gl engine is swapped for a recording fake.
vi.mock("../map/missionMapEngine", () => import("./fakeMapEngine"));

afterEach(() => fakeMap.reset());
