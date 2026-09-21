import { useCallback, useState } from "react";
import {
  ApiError,
  createPlan,
  createScenario,
  fetchDemoScenario,
  fetchEvents,
  fetchImpact,
  fetchPlan,
  fetchState,
  generateWindows,
  injectCloudBlock,
  stepSimulation,
} from "../api/amis";
import type {
  ImpactSchema,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import type { MissionSessionError } from "./types";

export interface MissionSessionState {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  windows: ObservationWindowSchema[];
  impact: ImpactSchema | null;
  loading: boolean;
  error: MissionSessionError | null;
  loadDemoScenario: () => Promise<void>;
  generatePlan: () => Promise<void>;
  step: (seconds: number) => Promise<void>;
  injectCloudBlock: (requestId: string, windowId: string) => Promise<void>;
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
  const [windows, setWindows] = useState<ObservationWindowSchema[]>([]);
  const [impact, setImpact] = useState<ImpactSchema | null>(null);
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
      setWindows([]);
      setImpact(null);
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
      const nextWindows = await generateWindows(scenario.id);
      setWindows(nextWindows);
      const nextPlan = await createPlan(scenario.id);
      setPlan(nextPlan);
      setImpact(null);
      await refetchStateAndEvents(scenario.id);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, refetchStateAndEvents]);

  const step = useCallback(
    async (seconds: number) => {
      if (scenario === null) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const nextState = await stepSimulation(scenario.id, seconds);
        setMissionState(nextState);
        if (plan !== null) {
          setPlan(await fetchPlan(plan.id));
        }
      } catch (caught) {
        setError(describeError(caught));
      } finally {
        setLoading(false);
      }
    },
    [scenario, plan],
  );

  const injectCloudBlockEvent = useCallback(
    async (requestId: string, windowId: string) => {
      if (scenario === null) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await injectCloudBlock(scenario.id, requestId, windowId);
        setWindows((current) =>
          current.map((window) =>
            window.id === windowId
              ? { ...window, valid: false, invalid_reason: "WINDOW_INVALIDATED" }
              : window,
          ),
        );
        const [nextImpact] = await Promise.all([
          fetchImpact(scenario.id),
          refetchStateAndEvents(scenario.id),
        ]);
        setImpact(nextImpact);
      } catch (caught) {
        setError(describeError(caught));
      } finally {
        setLoading(false);
      }
    },
    [scenario, refetchStateAndEvents],
  );

  const dismissError = useCallback(() => setError(null), []);

  return {
    scenario,
    plan,
    missionState,
    events,
    windows,
    impact,
    loading,
    error,
    loadDemoScenario,
    generatePlan,
    step,
    injectCloudBlock: injectCloudBlockEvent,
    dismissError,
  };
}
