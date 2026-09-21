import { client, ApiError, isErrorEnvelope } from "./client";
import type {
  ScenarioSchema,
  ObservationWindowSchema,
  MissionPlanSchema,
  MissionStateSchema,
  MissionEventSchema,
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

export async function fetchEvents(scenarioId: string): Promise<MissionEventSchema[]> {
  return unwrap(
    await client.GET("/scenarios/{scenario_id}/events", {
      params: { path: { scenario_id: scenarioId } },
    }),
  );
}

export { ApiError };
