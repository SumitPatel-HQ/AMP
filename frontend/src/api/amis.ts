import { client, ApiError, isErrorEnvelope } from "./client";
import type {
  ScenarioSchema,
  ObservationRequestSchema,
  ObservationWindowSchema,
  MissionPlanSchema,
  MissionStateSchema,
  MissionEventRequest,
  MissionEventSchema,
  ImpactSchema,
  PlanDiffSchema,
  MetricsSchema,
  DecisionTraceSchema,
  ScenarioSummarySchema,
  ScenarioPreviewSchema,
  OrbitalElementsSchema,
  GroundTrackPointSchema,
  GroundStationSchema,
  ContactWindowSchema,
  FeasibilitySchema,
} from "./client";

function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined) {
    if (isErrorEnvelope(result.error)) {
      throw new ApiError(result.error);
    }
    throw new Error("request failed with an undocumented error shape");
  }
  if (result.data === undefined) {
    throw new Error("request succeeded but returned no data");
  }
  return result.data;
}

export async function fetchDemoScenario(): Promise<ScenarioSchema> {
  return unwrap(await client.GET("/demo/scenario"));
}

export async function fetchExamples(): Promise<ScenarioSummarySchema[]> {
  return unwrap(await client.GET("/examples"));
}

export async function fetchExample(id: string): Promise<ScenarioSchema> {
  return unwrap(await client.GET("/examples/{example_id}", { params: { path: { example_id: id } } }));
}

export async function fetchMissions(): Promise<ScenarioSummarySchema[]> {
  return unwrap(await client.GET("/scenarios"));
}

export async function fetchScenario(id: string): Promise<ScenarioSchema> {
  return unwrap(await client.GET("/scenarios/{scenario_id}", { params: { path: { scenario_id: id } } }));
}

export async function fetchMissionPlans(id: string): Promise<MissionPlanSchema[]> {
  return unwrap(await client.GET("/scenarios/{scenario_id}/plans", { params: { path: { scenario_id: id } } }));
}

export async function fetchOrbitalElements(): Promise<OrbitalElementsSchema[]> {
  return unwrap(await client.GET("/orbital-elements"));
}

export async function parseTle(name: string, line1: string, line2: string): Promise<OrbitalElementsSchema> {
  return unwrap(await client.POST("/orbital-elements/parse-tle", { body: { name, line1, line2 } }));
}

export async function validateScenario(scenario: ScenarioSchema): Promise<ScenarioPreviewSchema> {
  return unwrap(await client.POST("/scenarios/validate", { body: scenario }));
}

export async function fetchGroundStations(): Promise<GroundStationSchema[]> {
  return unwrap(await client.GET("/ground-stations"));
}

/** Contact windows at the mission's stations, communication outages applied. */
export async function fetchContacts(id: string): Promise<ContactWindowSchema[]> {
  return unwrap(await client.GET("/scenarios/{scenario_id}/contacts", {
    params: { path: { scenario_id: id } },
  }));
}

export async function fetchGroundTrack(id: string): Promise<GroundTrackPointSchema[]> {
  return unwrap(await client.GET("/scenarios/{scenario_id}/ground-track", {
    params: { path: { scenario_id: id }, query: { step_s: 60 } },
  }));
}

export async function fetchSatellitePosition(id: string, time: string): Promise<GroundTrackPointSchema> {
  const points = unwrap(await client.GET("/scenarios/{scenario_id}/ground-track", {
    params: { path: { scenario_id: id }, query: { start: time, end: time, step_s: 30 } },
  }));
  if (points[0] === undefined) throw new Error("position sample was empty");
  return points[0];
}

export async function createScenario(scenario: ScenarioSchema): Promise<ScenarioSchema> {
  return unwrap(await client.POST("/scenarios", { body: scenario }));
}

export async function generateWindows(
  scenarioId: string,
): Promise<ObservationWindowSchema[]> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/windows/generate", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export async function createPlan(scenarioId: string): Promise<MissionPlanSchema> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/plan", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export async function fetchState(scenarioId: string): Promise<MissionStateSchema> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/state", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

/** A candidate for window-only feasibility: where, how long, and by when. */
export interface FeasibilityQuery {
  lat: number;
  lon: number;
  /** Imaging duration in seconds. */
  duration: number;
  /** Timezone-aware ISO 8601 deadline. */
  deadline: string;
  satelliteId: string | null;
}

/**
 * Each satellite's earliest suitable window for a candidate. Read-only and
 * window-only: nothing is submitted or reserved, and the backend searches from
 * the Scenario start whatever the mission clock says.
 */
export async function fetchFeasibility(
  scenarioId: string,
  query: FeasibilityQuery,
): Promise<FeasibilitySchema> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/feasibility", {
      params: {
        path: { scenario_id: scenarioId },
        query: {
          lat: query.lat,
          lon: query.lon,
          duration: query.duration,
          deadline: query.deadline,
          ...(query.satelliteId === null ? {} : { satellite_id: query.satelliteId }),
        },
      },
    }),
  );
}

/**
 * The request pool with live statuses: the scenario's requests plus those the
 * event log introduced. The scenario is immutable, so expiry shows only here.
 */
export async function fetchRequests(scenarioId: string): Promise<ObservationRequestSchema[]> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/requests", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export async function fetchEvents(scenarioId: string): Promise<MissionEventSchema[]> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/events", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export async function stepSimulation(
  scenarioId: string,
  seconds: number,
): Promise<MissionStateSchema> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/simulation/step", {
      params: { path: { scenario_id: scenarioId } },
      body: { seconds },
    }),
  );
}

export async function fetchWindows(scenarioId: string): Promise<ObservationWindowSchema[]> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/windows", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

/** Any event the backend accepts: CLOUD_BLOCK, BATTERY_DROP or EMERGENCY_TASK. */
export async function injectEvent(
  scenarioId: string,
  event: MissionEventRequest,
): Promise<MissionEventSchema> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/events", {
      params: { path: { scenario_id: scenarioId } },
      body: event,
    }),
  );
}

export async function fetchImpact(scenarioId: string): Promise<ImpactSchema> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/impact", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export async function fetchPlan(planId: string): Promise<MissionPlanSchema> {
  return unwrap(
    await client.GET("/plans/{plan_id}", {
      params: { path: { plan_id: planId } },
    }),
  );
}

export async function replan(
  scenarioId: string,
  expectedParentPlanId: string,
): Promise<MissionPlanSchema> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/replan", {
      params: { path: { scenario_id: scenarioId } },
      body: { expected_parent_plan_id: expectedParentPlanId },
    }),
  );
}

export async function comparePlans(
  oldPlanId: string,
  newPlanId: string,
): Promise<PlanDiffSchema> {
  return unwrap(
    await client.GET("/plans/{old_plan_id}/compare/{new_plan_id}", {
      params: { path: { old_plan_id: oldPlanId, new_plan_id: newPlanId } },
    }),
  );
}

export async function fetchMetrics(planId: string): Promise<MetricsSchema> {
  return unwrap(
    await client.GET("/plans/{plan_id}/metrics", {
      params: { path: { plan_id: planId } },
    }),
  );
}

export async function fetchTraces(planId: string): Promise<DecisionTraceSchema[]> {
  return unwrap(
    await client.GET("/plans/{plan_id}/traces", {
      params: { path: { plan_id: planId } },
    }),
  );
}

export { ApiError };
