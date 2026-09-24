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
  fetchWindows,
  generateWindows,
  injectEvent as postEvent,
  replan as replanMission,
  stepSimulation,
} from "../api/amis";
import type {
  ImpactSchema,
  MissionEventRequest,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import { eventAnchorRequestId, eventAnchorWindowId } from "../timeline/missionTimelineModel";
import { EMPTY_SELECTION } from "./types";
import type {
  MissionOperation,
  MissionSelection,
  MissionSessionError,
  PlanConflict,
  ReplanResult,
} from "./types";

export interface MissionSessionState {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  windows: ObservationWindowSchema[];
  impact: ImpactSchema | null;
  /** The last replan, or null while no replan has run on this plan. */
  replanResult: ReplanResult | null;
  /** The request, window, event and plan the reviewer is following, if any. */
  selection: MissionSelection;
  loading: boolean;
  /** The inject or replan request in flight, so the lifecycle can say so. */
  operation: MissionOperation | null;
  /** The last replan's version conflict, until the next mutation succeeds. */
  planConflict: PlanConflict | null;
  error: MissionSessionError | null;
  loadDemoScenario: () => Promise<void>;
  generatePlan: () => Promise<void>;
  replan: () => Promise<void>;
  step: (seconds: number) => Promise<void>;
  /** Resolves true once the backend accepted the event and the workspace refetched. */
  injectEvent: (event: MissionEventRequest) => Promise<boolean>;
  selectRequest: (requestId: string | null) => void;
  selectWindow: (windowId: string | null) => void;
  selectEvent: (eventId: string | null) => void;
  selectPlan: (planId: string | null) => void;
  dismissError: () => void;
  dismissPlanConflict: () => void;
}

function describeError(error: unknown): MissionSessionError {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message, details: error.details };
  }
  return { code: "CLIENT_ERROR", message: String(error), details: {} };
}

/**
 * The scenario's latest persisted impact, or null when no event has been
 * injected yet (the backend answers SIMULATION_STATE_ERROR "no impact exists").
 */
async function fetchImpactIfAny(scenarioId: string): Promise<ImpactSchema | null> {
  try {
    return await fetchImpact(scenarioId);
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === "SIMULATION_STATE_ERROR") {
      return null;
    }
    throw caught;
  }
}

export function useMissionSession(): MissionSessionState {
  const [scenario, setScenario] = useState<ScenarioSchema | null>(null);
  const [plan, setPlan] = useState<MissionPlanSchema | null>(null);
  const [missionState, setMissionState] = useState<MissionStateSchema | null>(null);
  const [events, setEvents] = useState<MissionEventSchema[]>([]);
  const [windows, setWindows] = useState<ObservationWindowSchema[]>([]);
  const [impact, setImpact] = useState<ImpactSchema | null>(null);
  const [replanResult, setReplanResult] = useState<ReplanResult | null>(null);
  const [selection, setSelection] = useState<MissionSelection>(EMPTY_SELECTION);
  const [loading, setLoading] = useState(false);
  const [operation, setOperation] = useState<MissionOperation | null>(null);
  const [planConflict, setPlanConflict] = useState<PlanConflict | null>(null);
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
      setReplanResult(null);
      setPlanConflict(null);
      setSelection(EMPTY_SELECTION);
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
      setPlanConflict(null);
      // Regenerated windows and a fresh plan replace what a selected window or
      // plan pointed at; the request survives because the scenario does.
      setSelection((current) => ({ ...current, windowId: null, planId: null }));
      await refetchStateAndEvents(scenario.id);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, refetchStateAndEvents]);

  /**
   * A refused replan leaves the session pointing at a plan the backend has
   * moved past. Rather than retry against a version nobody has looked at, the
   * session loads the plan the backend names as current (and the mission
   * context around it) and records the conflict for the reviewer.
   */
  const refreshAfterConflict = useCallback(
    async (scenarioId: string, expectedPlanId: string, conflict: ApiError) => {
      const reported = conflict.details["current_plan_id"];
      const currentPlanId = typeof reported === "string" ? reported : null;
      setPlanConflict({ message: conflict.message, expectedPlanId, currentPlanId });
      try {
        const [currentPlan, nextWindows, nextImpact] = await Promise.all([
          currentPlanId === null ? Promise.resolve(null) : fetchPlan(currentPlanId),
          fetchWindows(scenarioId),
          fetchImpactIfAny(scenarioId),
          refetchStateAndEvents(scenarioId),
        ]);
        if (currentPlan !== null) {
          setPlan(currentPlan);
        }
        setWindows(nextWindows);
        setImpact(nextImpact);
      } catch (caught) {
        setError(describeError(caught));
      }
    },
    [refetchStateAndEvents],
  );

  const replan = useCallback(async () => {
    if (scenario === null || plan === null) {
      return;
    }
    setLoading(true);
    setOperation("replan");
    setError(null);
    // The displayed plan is the version the reviewer decided against, so it
    // is the version the server must still hold for this replan to be safe.
    const initialPlan = plan;
    try {
      const revisedPlan = await replanMission(scenario.id, initialPlan.id);
      setPlanConflict(null);
      // The server has already committed to the new version, so the local
      // plan pointer must move with it even if the comparison below fails -
      // otherwise the next replan attempt would still send the stale id and
      // loop on a version conflict.
      setPlan(revisedPlan);
      // A request selected before this replan may not appear in its trace,
      // so it is cleared rather than left pointing at data this replan never
      // touched. Its window goes with it, and so does a selected plan, which
      // may drop out of the pair this replan now compares.
      setSelection((current) => ({
        ...current,
        requestId: null,
        windowId: null,
        planId: null,
      }));
      const [diff, traces] = await Promise.all([
        comparePlans(initialPlan.id, revisedPlan.id),
        fetchTraces(revisedPlan.id),
      ]);
      await refetchStateAndEvents(scenario.id);
      setReplanResult({
        initialPlan,
        revisedPlan,
        diff,
        traces,
      });
    } catch (caught) {
      // A version conflict gets its own stale-plan notice, carrying the
      // backend's code and message, instead of a second generic error.
      if (caught instanceof ApiError && caught.code === "PLAN_VERSION_CONFLICT") {
        await refreshAfterConflict(scenario.id, initialPlan.id, caught);
      } else {
        setError(describeError(caught));
      }
    } finally {
      setOperation(null);
      setLoading(false);
    }
  }, [scenario, plan, refetchStateAndEvents, refreshAfterConflict]);

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

  const injectEvent = useCallback(
    async (event: MissionEventRequest): Promise<boolean> => {
      if (scenario === null) {
        return false;
      }
      setLoading(true);
      setOperation("inject");
      setError(null);
      try {
        const injected = await postEvent(scenario.id, event);
        setPlanConflict(null);
        // The backend owns what the event changed: window validity, the
        // emergency request's windows, battery, and the persisted impact.
        // Each is refetched rather than mirrored here.
        const [nextState, nextEvents, nextWindows, nextImpact] = await Promise.all([
          fetchState(scenario.id),
          fetchEvents(scenario.id),
          fetchWindows(scenario.id),
          fetchImpact(scenario.id),
        ]);
        setMissionState(nextState);
        setEvents(nextEvents);
        setWindows(nextWindows);
        setImpact(nextImpact);
        // Follow the injected event, and what it names, across every panel.
        const requestId = eventAnchorRequestId(injected);
        setSelection((current) => ({
          ...current,
          eventId: injected.id,
          requestId: requestId ?? current.requestId,
          windowId: requestId === null ? current.windowId : eventAnchorWindowId(injected),
        }));
        return true;
      } catch (caught) {
        setError(describeError(caught));
        return false;
      } finally {
        setOperation(null);
        setLoading(false);
      }
    },
    [scenario],
  );

  // A selected window belongs to one request, so choosing a request drops it.
  const selectRequest = useCallback(
    (requestId: string | null) =>
      setSelection((current) => ({ ...current, requestId, windowId: null })),
    [],
  );

  // Selecting a window also follows its request, so the panels that only know
  // requests (map, timeline, trace) still highlight what the window is for.
  const selectWindow = useCallback(
    (windowId: string | null) =>
      setSelection((current) => {
        const window = windows.find((candidate) => candidate.id === windowId);
        return {
          ...current,
          windowId,
          requestId: window === undefined ? current.requestId : window.request_id,
        };
      }),
    [windows],
  );

  // Selecting an event also follows what it disrupted, so the map, timeline
  // and nav highlight the affected request/target (and window for a cloud
  // block). Mission-level events name no request and leave those untouched.
  const selectEvent = useCallback(
    (eventId: string | null) =>
      setSelection((current) => {
        if (eventId === null) {
          return { ...current, eventId };
        }
        const event = events.find((candidate) => candidate.id === eventId);
        if (event === undefined) {
          return { ...current, eventId };
        }
        const requestId = eventAnchorRequestId(event);
        if (requestId === null) {
          return { ...current, eventId };
        }
        return { ...current, eventId, requestId, windowId: eventAnchorWindowId(event) };
      }),
    [events],
  );

  const selectPlan = useCallback(
    (planId: string | null) => setSelection((current) => ({ ...current, planId })),
    [],
  );

  const dismissError = useCallback(() => setError(null), []);
  const dismissPlanConflict = useCallback(() => setPlanConflict(null), []);

  return {
    scenario,
    plan,
    missionState,
    events,
    windows,
    impact,
    replanResult,
    selection,
    loading,
    operation,
    planConflict,
    error,
    loadDemoScenario,
    generatePlan,
    replan,
    step,
    injectEvent,
    selectRequest,
    selectWindow,
    selectEvent,
    selectPlan,
    dismissError,
    dismissPlanConflict,
  };
}
