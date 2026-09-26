import { describe, expect, it } from "vitest";
import type { MissionPlanSchema, MissionStateSchema, ScenarioSchema } from "../api/client";
import { storageProfile } from "./storageProfile";

const scenario = {
  start_time: "2026-01-01T00:00:00Z",
  satellite: { storage_usage_mb: 10 },
} as ScenarioSchema;

const action = (id: string, kind: "imaging" | "downlink", start: string, end: string, storage: number) => ({
  id, kind, start, end, storage_cost_mb: storage, request_id: kind === "imaging" ? id : null,
});

describe("storageProfile", () => {
  it("rises on imaging, falls at downlink end, and floors at zero", () => {
    const plan = {
      actions: [
        action("A", "imaging", "2026-01-01T01:00:00Z", "2026-01-01T01:01:00Z", 50),
        action("D", "downlink", "2026-01-01T01:30:00Z", "2026-01-01T01:40:00Z", -500),
        action("B", "imaging", "2026-01-01T02:00:00Z", "2026-01-01T02:01:00Z", 20),
      ],
    } as unknown as MissionPlanSchema;
    expect(storageProfile(scenario, plan).map((point) => [point.kind, point.usedMb])).toEqual([
      ["start", 10],
      ["imaging", 60],
      ["downlink", 0],
      ["imaging", 20],
    ]);
  });
});

describe("storageProfile with a live mission state", () => {
  it("walks the future from the backend's live storage, not the scenario seed", () => {
    const plan = {
      actions: [
        { ...action("A", "imaging", "2026-01-01T01:00:00Z", "2026-01-01T01:01:00Z", 50), status: "completed" },
        { ...action("D", "downlink", "2026-01-01T01:30:00Z", "2026-01-01T01:40:00Z", -45), status: "planned" },
      ],
    } as unknown as MissionPlanSchema;
    const state = { simulated_time: "2026-01-01T01:10:00Z", storage_usage_mb: 80 } as MissionStateSchema;
    expect(storageProfile(scenario, plan, state).map((point) => [point.kind, point.usedMb])).toEqual([
      ["start", 10],
      ["imaging", 60],
      ["now", 80],
      ["downlink", 35],
    ]);
  });
});
