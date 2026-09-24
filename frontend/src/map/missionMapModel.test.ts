import { describe, expect, it } from "vitest";
import { missionState, plan, scenario } from "../test/mapFixtures";
import { buildMissionMapModel, satellitePlacement } from "./missionMapModel";

describe("mission map model", () => {
  it("places the satellite over the target it is observing", () => {
    expect(satellitePlacement(scenario, plan, "2026-09-21T10:15:00Z")).toEqual({
      satelliteId: "SAT-001",
      coordinate: [77.59, 12.97],
      overRequestId: "OBS-A",
    });
  });

  it("leaves the satellite over the last target it observed between actions", () => {
    const placement = satellitePlacement(scenario, plan, "2026-09-21T11:00:00Z");

    expect(placement?.overRequestId).toBeNull();
    expect(placement?.coordinate).toEqual([77.59, 12.97]);
  });

  it("draws no satellite until a plan says where it is", () => {
    expect(satellitePlacement(scenario, null, null)).toBeNull();
  });

  it("puts the satellite at the first planned target before the clock is known", () => {
    expect(satellitePlacement(scenario, plan, null)?.coordinate).toEqual([77.59, 12.97]);
  });

  it("draws every target even without a plan or a mission state", () => {
    const model = buildMissionMapModel(scenario, null, null, []);

    expect(model.targets.map((target) => target.status)).toEqual(["unplanned", "unplanned"]);
    expect(model.planSequence).toEqual([]);
  });

  it("reads each target's status from the plan, with live completion winning", () => {
    const model = buildMissionMapModel(
      scenario,
      { ...plan, actions: [plan.actions[0]], unscheduled: [{ request_id: "OBS-B", reason_code: "TIME_OVERLAP" }] },
      { ...missionState, completed_request_ids: [] },
      [],
    );
    expect(model.targets.map((target) => target.status)).toEqual(["scheduled", "unscheduled"]);
    expect(model.targets[1].unscheduledReason).toBe("TIME_OVERLAP");

    const completed = buildMissionMapModel(
      scenario,
      plan,
      { ...missionState, completed_request_ids: ["OBS-A"] },
      [],
    );
    expect(completed.targets[0].status).toBe("completed");
  });

  it("links a target to the events whose payload names it", () => {
    const model = buildMissionMapModel(scenario, plan, missionState, [
      {
        id: "EVT-001",
        scenario_id: scenario.id,
        event_time: scenario.start_time,
        event_type: "CLOUD_BLOCK",
        payload: { request_id: "OBS-B", window_id: "WIN-OBS-B-1" },
      },
    ]);

    expect(model.targets.map((target) => target.eventIds)).toEqual([[], ["EVT-001"]]);
  });

  it("orders the plan sequence by action start and bounds every target", () => {
    const model = buildMissionMapModel(scenario, plan, missionState, []);

    expect(model.planSequence).toEqual([
      [77.59, 12.97],
      [151.21, -33.87],
    ]);
    expect(model.bounds).toEqual([77.59, -33.87, 151.21, 12.97]);
  });
});
