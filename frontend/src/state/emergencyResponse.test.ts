import { describe, expect, it } from "vitest";
import type { EmergencyResponseSchema, MetricsSchema } from "../api/client";
import {
  emergencyResponseRows,
  emergencyResponseState,
  formatLatency,
  plannedDiffersFromAchieved,
  responseSummary,
} from "./emergencyResponse";

const row = {
  request_id: "OBS-EMG",
  event_id: "EVT-001",
  arrival_time: "2026-09-21T10:05:00Z",
  request_status: "scheduled",
  planned_start_time: "2026-09-21T10:40:00Z",
  planned_latency_s: 2100,
  planned_satellite_id: "SAT-1",
  achieved_start_time: null,
  achieved_latency_s: null,
  achieved_satellite_id: null,
} satisfies EmergencyResponseSchema;

describe("emergency response", () => {
  it("reads state only from backend fields", () => {
    expect(emergencyResponseState(row)).toBe("planned");
    expect(
      emergencyResponseState({ ...row, achieved_start_time: row.planned_start_time }),
    ).toBe("achieved");
    expect(emergencyResponseState({ ...row, planned_start_time: null })).toBe("unserved");
    expect(
      emergencyResponseState({ ...row, planned_start_time: null, request_status: "expired" }),
    ).toBe("expired");
  });

  it("formats missing service as no acquisition, never as zero", () => {
    expect(formatLatency(null)).toBe("no acquisition");
    expect(formatLatency(0)).toBe("0 s");
    expect(formatLatency(2100)).toBe("35 min");
    expect(formatLatency(3725)).toBe("1 h 2 min 5 s");
  });

  it("shows each mean with its own denominator and the total", () => {
    const metrics = {
      time_to_first_acquisition_s: 2100,
      achieved_time_to_first_acquisition_s: null,
      emergency_request_count: 3,
      planned_emergency_request_count: 1,
      achieved_emergency_request_count: 0,
    } as MetricsSchema;

    expect(responseSummary(metrics, "planned")).toBe("35 min · 1 of 3 planned");
    expect(responseSummary(metrics, "achieved")).toBe("N/A · 0 of 3 started");
  });

  it("reads metrics recorded before emergency response as no arrivals", () => {
    const old = {
      emergency_request_count: 0,
      planned_emergency_request_count: 0,
      achieved_emergency_request_count: 0,
    } as MetricsSchema;

    expect(emergencyResponseRows(old)).toEqual([]);
    expect(responseSummary(old, "planned")).toBe("N/A · 0 of 0 planned");
  });

  it("notices when planned and achieved placements differ", () => {
    const achieved = {
      ...row,
      achieved_start_time: row.planned_start_time,
      achieved_latency_s: 2100,
      achieved_satellite_id: "SAT-1",
    };
    expect(plannedDiffersFromAchieved(achieved)).toBe(false);
    expect(plannedDiffersFromAchieved({ ...achieved, planned_satellite_id: "SAT-2" })).toBe(true);
    expect(plannedDiffersFromAchieved(row)).toBe(false);
  });
});
