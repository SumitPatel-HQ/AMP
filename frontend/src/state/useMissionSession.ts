import { useCallback, useState } from "react";
import {
  ApiError,
  comparePlans,
  createPlan,
  createScenario,
  fetchDemoScenario,
  fetchEvents,
  fetchImpact,
  fetchMetrics,
  fetchPlan,
  fetchRequests,
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
  MetricsSchema,
  MissionEventRequest,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationRequestSchema,
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
  plans: MissionPlanSchema[];
  missionState: MissionStateSchema | null;
  events: MissionEventSchema[];
  windows: ObservationWindowSchema[];
  /** The backend's request pool with live statuses, emergency arrivals included. */
  requestPool: ObservationRequestSchema[];
  /** The current plan's metrics, measured at the current mission state. */
  metrics: MetricsSchema | null;
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
  /** True while the backend's current plan could not be loaded after a conflict. */
  stalePlan: boolean;
  error: MissionSessionError | null;
  loadDemoScenario: () => Promise<void>;
  generatePlan: () => Promise<void>;
  replan: () => Promise<void>;
  retryComparison: () => Promise<void>;
  step: (seconds: number) => Promise<void>;
  /** Resolves true once the backend accepted the event and the workspace refetched. */
  injectEvent: (event: MissionEventRequest) => Promise<boolean>;
  selectRequest: (requestId: string | null) => void;
  selectWindow: (windowId: string | null) => void;
  selectEvent: (eventId: string | null) => void;
  selectPlan: (planId: string | null) => void;
  clearSelection: () => void;
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
  const [plans, setPlans] = useState<MissionPlanSchema[]>([]);
  const [missionState, setMissionState] = useState<MissionStateSchema | null>(null);
  const [events, setEvents] = useState<MissionEventSchema[]>([]);
  const [windows, setWindows] = useState<ObservationWindowSchema[]>([]);
  const [requestPool, setRequestPool] = useState<ObservationRequestSchema[]>([]);
  const [metrics, setMetrics] = useState<MetricsSchema | null>(null);
  const [impact, setImpact] = useState<ImpactSchema | null>(null);
  const [replanResult, setReplanResult] = useState<ReplanResult | null>(null);
  const [selection, setSelection] = useState<MissionSelection>(EMPTY_SELECTION);
  const [loading, setLoading] = useState(false);
  const [operation, setOperation] = useState<MissionOperation | null>(null);
  const [planConflict, setPlanConflict] = useState<PlanConflict | null>(null);
  const [stalePlan, setStalePlan] = useState(false);
  const [error, setError] = useState<MissionSessionError | null>(null);

  const rememberPlan = useCallback((next: MissionPlanSchema) => {
    setPlans((current) => {
      const previous = current.filter((candidate) => candidate.id !== next.id);
      return [...previous, next].sort((left, right) => left.version - right.version);
    });
  }, []);

  const refetchStateAndEvents = useCallback(async (scenarioId: string) => {
    const [nextState, nextEvents] = await Promise.all([
      fetchState(scenarioId),
      fetchEvents(scenarioId),
    ]);
    setMissionState(nextState);
    setEvents(nextEvents);
  }, []);

  /**
   * What the backend evaluates against the mission state: request statuses
   * (expiry included) and the current plan's metrics. Every mutation moves
   * that state, so both are refetched after each one rather than mirrored.
   */
  const refetchPoolAndMetrics = useCallback(async (scenarioId: string, planId: string | null) => {
    const [nextPool, nextMetrics] = await Promise.all([
      fetchRequests(scenarioId),
      planId === null ? Promise.resolve(null) : fetchMetrics(planId),
    ]);
    setRequestPool(nextPool);
    setMetrics(nextMetrics);
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
      setPlans([]);
      setWindows([]);
      setImpact(null);
      setReplanResult(null);
      setPlanConflict(null);
      setStalePlan(false);
      setSelection(EMPTY_SELECTION);
      await Promise.all([
        refetchStateAndEvents(loaded.id),
        refetchPoolAndMetrics(loaded.id, null),
      ]);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [refetchStateAndEvents, refetchPoolAndMetrics]);

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
      setPlans([nextPlan]);
      setImpact(null);
      setReplanResult(null);
      setPlanConflict(null);
      setStalePlan(false);
      // Regenerated windows and a fresh plan replace what a selected window or
      // plan pointed at; the request survives because the scenario does.
      setSelection((current) => ({ ...current, windowId: null, planId: null }));
      await Promise.all([
        refetchStateAndEvents(scenario.id),
        refetchPoolAndMetrics(scenario.id, nextPlan.id),
      ]);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [scenario, refetchStateAndEvents, refetchPoolAndMetrics]);

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
      setStalePlan(true);
      setReplanResult(null);
      try {
        const [currentPlan, nextWindows, nextImpact] = await Promise.all([
          currentPlanId === null ? Promise.resolve(null) : fetchPlan(currentPlanId),
          fetchWindows(scenarioId),
          fetchImpactIfAny(scenarioId),
          refetchStateAndEvents(scenarioId),
          refetchPoolAndMetrics(scenarioId, currentPlanId),
        ]);
        if (currentPlan !== null) {
          setPlan(currentPlan);
          setStalePlan(false);
          rememberPlan(currentPlan);
          setSelection((current) => ({ ...current, planId: null }));
        }
        setWindows(nextWindows);
        setImpact(nextImpact);
      } catch (caught) {
        setError(describeError(caught));
      }
    },
    [refetchStateAndEvents, refetchPoolAndMetrics, rememberPlan],
  );

  /**
   * The comparison's metrics read the live mission state as well, so while
   * the replan it compares still produced the current plan it is refetched
   * alongside that state.
   */
  const refreshComparison = useCallback(
    async (currentPlan: MissionPlanSchema) => {
      if (replanResult === null || replanResult.revisedPlan.id !== currentPlan.id) {
        return;
      }
      const diff = await comparePlans(replanResult.initialPlan.id, currentPlan.id);
      setReplanResult((current) =>
        current === null || current.revisedPlan.id !== currentPlan.id
          ? current
          : { ...current, revisedPlan: currentPlan, diff },
      );
    },
    [replanResult],
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
      setStalePlan(false);
      // The server has already committed to the new version, so the local
      // plan pointer must move with it even if the comparison below fails -
      // otherwise the next replan attempt would still send the stale id and
      // loop on a version conflict.
      setPlan(revisedPlan);
      rememberPlan(initialPlan);
      rememberPlan(revisedPlan);
      setReplanResult(null);
      // The request still belongs to the mission after replanning. A selected
      // window may have become invalid, so only that narrower focus is reset.
      setSelection((current) => ({
        ...current,
        windowId: null,
      }));
      // Wait for every refresh before enabling another action. A failed
      // comparison must not leave a late state or metrics update in flight.
      const results = await Promise.allSettled([
        comparePlans(initialPlan.id, revisedPlan.id),
        fetchTraces(revisedPlan.id),
        refetchStateAndEvents(scenario.id),
        refetchPoolAndMetrics(scenario.id, revisedPlan.id),
      ]);
      const failed = results.find((result) => result.status === "rejected");
      if (failed?.status === "rejected") throw failed.reason;
      const [diff, traces] = results as [
        PromiseFulfilledResult<Awaited<ReturnType<typeof comparePlans>>>,
        PromiseFulfilledResult<Awaited<ReturnType<typeof fetchTraces>>>,
        PromiseFulfilledResult<void>,
        PromiseFulfilledResult<void>,
      ];
      setReplanResult({
        initialPlan,
        revisedPlan,
        diff: diff.value,
        traces: traces.value,
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
  }, [scenario, plan, refetchStateAndEvents, refetchPoolAndMetrics, refreshAfterConflict, rememberPlan]);

  const retryComparison = useCallback(async () => {
    if (plan === null || plan.parent_plan_id === null) return;
    setLoading(true);
    setError(null);
    try {
      const parentId = plan.parent_plan_id;
      const initialPlan = plans.find((candidate) => candidate.id === parentId) ?? await fetchPlan(parentId);
      const [diff, traces] = await Promise.all([
        comparePlans(parentId, plan.id),
        fetchTraces(plan.id),
      ]);
      rememberPlan(initialPlan);
      setReplanResult({ initialPlan, revisedPlan: plan, diff, traces });
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setLoading(false);
    }
  }, [plan, plans, rememberPlan]);

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
        const refreshPlan = async () => {
          if (plan === null) {
            return;
          }
          const refreshedPlan = await fetchPlan(plan.id);
          setPlan(refreshedPlan);
          rememberPlan(refreshedPlan);
          await refreshComparison(refreshedPlan);
        };
        await refreshPlan();
        await refetchPoolAndMetrics(scenario.id, plan?.id ?? null);
      } catch (caught) {
        setError(describeError(caught));
      } finally {
        setLoading(false);
      }
    },
    [scenario, plan, refreshComparison, refetchPoolAndMetrics, rememberPlan],
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
        // A battery drop or an emergency arrival moves what the metrics and
        // request statuses read, so they follow the event too.
        await Promise.all([
          refetchPoolAndMetrics(scenario.id, plan?.id ?? null),
          plan === null ? Promise.resolve() : refreshComparison(plan),
        ]);
        // Follow the injected event, and what it names, across every panel.
        const requestId = eventAnchorRequestId(injected);
        setSelection((current) => ({
          ...current,
          eventId: injected.id,
          requestId,
          windowId: requestId === null ? null : eventAnchorWindowId(injected),
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
    [scenario, plan, refetchPoolAndMetrics, refreshComparison],
  );

  // A selected window belongs to one request, so choosing a request drops it.
  const selectRequest = useCallback(
    (requestId: string | null) =>
      setSelection((current) => ({ ...current, requestId, windowId: null, eventId: null })),
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
          eventId: null,
        };
      }),
    [windows],
  );

  // Selecting an event also follows what it disrupted, so the map, timeline
  // and nav highlight the affected request/target (and window for a cloud
  // block). Mission-level events clear unrelated request/window focus.
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
          return { ...current, eventId, requestId: null, windowId: null };
        }
        return { ...current, eventId, requestId, windowId: eventAnchorWindowId(event) };
      }),
    [events],
  );

  const selectPlan = useCallback(
    (planId: string | null) => setSelection((current) => ({ ...current, planId })),
    [],
  );
  const clearSelection = useCallback(() => setSelection(EMPTY_SELECTION), []);

  const dismissError = useCallback(() => setError(null), []);
  const dismissPlanConflict = useCallback(() => setPlanConflict(null), []);

  return {
    scenario,
    plan,
    plans,
    missionState,
    events,
    windows,
    requestPool,
    metrics,
    impact,
    replanResult,
    selection,
    loading,
    operation,
    planConflict,
    stalePlan,
    error,
    loadDemoScenario,
    generatePlan,
    replan,
    retryComparison,
    step,
    injectEvent,
    selectRequest,
    selectWindow,
    selectEvent,
    selectPlan,
    clearSelection,
    dismissError,
    dismissPlanConflict,
  };
}
