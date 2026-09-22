import { useCallback, useState } from "react";
import {
  ApiError,
  comparePlans,
  createPlan,
  createScenario,
  fetchDemoScenario,
  fetchEvents,
  fetchImpact,
  fetchPlan,
  fetchState,
  fetchTraces,
  generateWindows,
  injectCloudBlock,
  replan as replanMission,
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
import type { MissionSessionError, ReplanResult } from "./types";

export interface MissionSessionState {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  windows: ObservationWindowSchema[];
  impact: ImpactSchema | null;
  /** The last replan, or null while no replan has run on this plan. */
  replanResult: ReplanResult | null;
  /** The request the reviewer is following across panels, if any. */
  selectedRequestId: string | null;
  loading: boolean;
  error: MissionSessionError | null;
  loadDemoScenario: () => Promise<void>;
  generatePlan: () => Promise<void>;
  replan: () => Promise<void>;
  step: (seconds: number) => Promise<void>;
  injectCloudBlock: (requestId: string, windowId: string) => Promise<void>;
  selectRequest: (requestId: string | null) => void;
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
  const [replanResult, setReplanResult] = useState<ReplanResult | null>(null);
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<MissionSessionError | null>(null);

  const refetchStateAndEvents = useCallback(async (scenarioId: string) => {
    const [nextState, nextEvents] = await Promise.all([
      fetchState(scenarioId),
      fetchEvents(scenarioId),
    ]);
    setMissionState(nextState);
    setEvents(nextEvents);
    return nextState;
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
      setReplanResult(null);
      setSelectedRequestId(null);
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
      setReplanResult(null);
      await refetchStateAndEvents(scenario.id);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, refetchStateAndEvents]);

  const replan = useCallback(async () => {
    if (scenario === null || plan === null) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // The displayed plan is the version the reviewer decided against, so it
      // is the version the server must still hold for this replan to be safe.
      const initialPlan = plan;
      const revisedPlan = await replanMission(scenario.id, initialPlan.id);
      // The server has already committed to the new version, so the local
      // plan pointer must move with it even if the comparison below fails -
      // otherwise the next replan attempt would still send the stale id and
      // loop on a version conflict.
      setPlan(revisedPlan);
      // A request selected before this replan may not appear in its trace,
      // so it is cleared rather than left pointing at data this replan never
      // touched.
      setSelectedRequestId(null);
      const [diff, traces] = await Promise.all([
        comparePlans(initialPlan.id, revisedPlan.id),
        fetchTraces(revisedPlan.id),
      ]);
      const nextState = await refetchStateAndEvents(scenario.id);
      setReplanResult({
        initialPlan,
        revisedPlan,
        diff,
        traces,
        frozenAt: nextState.simulated_time,
      });
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, plan, refetchStateAndEvents]);

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
          const refreshedPlan = await fetchPlan(plan.id);
          setPlan(refreshedPlan);
          if (replanResult !== null && replanResult.revisedPlan.id === refreshedPlan.id) {
            // Battery and storage utilisation read the live mission state, not
            // the plan, so the metrics panel goes stale after a step unless
            // its comparison is refetched along with the revised timeline.
            const diff = await comparePlans(replanResult.initialPlan.id, refreshedPlan.id);
            setReplanResult((current) =>
              current === null || current.revisedPlan.id !== refreshedPlan.id
                ? current
                : { ...current, revisedPlan: refreshedPlan, diff },
            );
          }
        }
      } catch (caught) {
        setError(describeError(caught));
      } finally {
        setLoading(false);
      }
    },
    [scenario, plan, replanResult],
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

  const selectRequest = useCallback(
    (requestId: string | null) => setSelectedRequestId(requestId),
    [],
  );

  const dismissError = useCallback(() => setError(null), []);

  return {
    scenario,
    plan,
    missionState,
    events,
    windows,
    impact,
    replanResult,
    selectedRequestId,
    loading,
    error,
    loadDemoScenario,
    generatePlan,
    replan,
    step,
    injectCloudBlock: injectCloudBlockEvent,
    selectRequest,
    dismissError,
  };
}
