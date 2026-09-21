import { useCallback, useState } from "react";
import {
  ApiError,
  createPlan,
  createScenario,
  fetchDemoScenario,
  fetchEvents,
  fetchState,
  generateWindows,
} from "../api/amis";
import type {
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ScenarioSchema,
} from "../api/client";
import type { MissionSessionError } from "./types";

export interface MissionSessionState {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  loading: boolean;
  error: MissionSessionError | null;
  loadDemoScenario: () => Promise<void>;
  generatePlan: () => Promise<void>;
  dismissError: () => void;
}

function describeError(error: unknown): MissionSessionError {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message };
  }
  return { code: "CLIENT_ERROR", message: String(error) };
}

export function useMissionSession(): MissionSessionState {
  const [scenario, setScenario] = useState<ScenarioSchema | null>(null);
  const [plan, setPlan] = useState<MissionPlanSchema | null>(null);
  const [missionState, setMissionState] = useState<MissionStateSchema | null>(null);
  const [events, setEvents] = useState<MissionEventSchema[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<MissionSessionError | null>(null);

  const refetchStateAndEvents = useCallback(async (scenarioId: string) => {
    const [nextState, nextEvents] = await Promise.all([
      fetchState(scenarioId),
      fetchEvents(scenarioId),
    ]);
    setMissionState(nextState);
    setEvents(nextEvents);
  }, []);

  const loadDemoScenario = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const demo = await fetchDemoScenario();
      const demoSession = {
        ...demo,
        id: `${demo.id}-${crypto.randomUUID()}`,
      };
      const loaded = await createScenario(demoSession);
      setScenario(loaded);
      setPlan(null);
      await refetchStateAndEvents(loaded.id);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [refetchStateAndEvents]);

  const generatePlan = useCallback(async () => {
    if (scenario === null) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await generateWindows(scenario.id);
      const nextPlan = await createPlan(scenario.id);
      setPlan(nextPlan);
      await refetchStateAndEvents(scenario.id);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, refetchStateAndEvents]);

  const dismissError = useCallback(() => setError(null), []);

  return {
    scenario,
    plan,
    missionState,
    events,
    loading,
    error,
    loadDemoScenario,
    generatePlan,
    dismissError,
  };
}
