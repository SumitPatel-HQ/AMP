import type { MissionPlanSchema, MissionStateSchema, ScenarioSchema } from "../api/client";

/** Two targets on different continents and a plan that visits both. */
export const scenario = {
  id: "SCN-MAP",
  name: "Map demo",
  start_time: "2026-09-21T10:00:00Z",
  end_time: "2026-09-21T14:00:00Z",
  satellite: {
    id: "SAT-001",
    battery_capacity_wh: 500,
    battery_charge_wh: 500,
    storage_capacity_mb: 2000,
    storage_usage_mb: 0,
    available: true,
  },
  requests: [
    {
      id: "OBS-A",
      target_lat: 12.97,
      target_lon: 77.59,
      priority: 5,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
    {
      id: "OBS-B",
      target_lat: -33.87,
      target_lon: 151.21,
      priority: 3,
      duration_s: 600,
      deadline: "2026-09-21T14:00:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "pending",
    },
  ],
} satisfies ScenarioSchema;

export const plan = {
  id: "SCN-MAP:PLAN-1",
  scenario_id: scenario.id,
  version: 1,
  parent_plan_id: null,
  created_at: scenario.start_time,
  actions: [
    {
      id: "ACT-OBS-A-1",
      request_id: "OBS-A",
      satellite_id: scenario.satellite.id,
      window_id: "WIN-OBS-A-1",
      start: "2026-09-21T10:10:00Z",
      end: "2026-09-21T10:20:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
    {
      id: "ACT-OBS-B-1",
      request_id: "OBS-B",
      satellite_id: scenario.satellite.id,
      window_id: "WIN-OBS-B-1",
      start: "2026-09-21T12:00:00Z",
      end: "2026-09-21T12:10:00Z",
      energy_cost_wh: 40,
      storage_cost_mb: 100,
      status: "planned",
    },
  ],
  unscheduled: [],
  mission_utility: 8,
  violation_count: 0,
  planning_time_ms: 1,
} satisfies MissionPlanSchema;

export const missionState = {
  scenario_id: scenario.id,
  simulated_time: "2026-09-21T10:15:00Z",
  satellite_id: scenario.satellite.id,
  battery_wh: 500,
  storage_usage_mb: 0,
  available: true,
  active_event_ids: [],
  completed_request_ids: [],
  mission_complete: false,
} satisfies MissionStateSchema;
