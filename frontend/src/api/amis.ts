import { client, ApiError, isErrorEnvelope } from "./client";
import type {
  ScenarioSchema,
  ObservationWindowSchema,
  MissionPlanSchema,
  MissionStateSchema,
  MissionEventSchema,
  ImpactSchema,
  PlanDiffSchema,
  DecisionTraceSchema,
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

export async function injectCloudBlock(
  scenarioId: string,
  requestId: string,
  windowId: string,
): Promise<MissionEventSchema> {
  return unwrap(
    await client.POST("/scenarios/{scenario_id}/events", {
      params: { path: { scenario_id: scenarioId } },
      body: {
        event_type: "CLOUD_BLOCK",
        payload: { request_id: requestId, window_id: windowId },
      },
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

export async function fetchTraces(planId: string): Promise<DecisionTraceSchema[]> {
  return unwrap(
    await client.GET("/plans/{plan_id}/traces", {
      params: { path: { plan_id: planId } },
    }),
  );
}

export { ApiError };
