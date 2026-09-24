import type {
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationRequestSchema,
  ScenarioSchema,
  ScheduledActionSchema,
} from "../api/client";
import { missionRequestPool } from "../state/missionEvent";
import { eventAnchorRequestId } from "../timeline/missionTimelineModel";

/** Longitude then latitude, the order every map library here takes. */
export type Coordinate = readonly [number, number];

/**
 * Where a request stands, read off the current plan and the live mission
 * state. Completion wins because the clock has already settled it.
 */
export type TargetPlanStatus = "completed" | "scheduled" | "unscheduled" | "unplanned";

/** One observation target as the map draws it. */
export interface MapTarget {
  requestId: string;
  coordinate: Coordinate;
  priority: number;
  deadline: string;
  status: TargetPlanStatus;
  /** The action that observes this target in the current plan, if any. */
  action: ScheduledActionSchema | null;
  /** Why the current plan left this request out, if it did. */
  unscheduledReason: string | null;
  /** Events whose payload names this request. */
  eventIds: string[];
}

/** Where the satellite is drawn, and the request it is over if it is observing. */
export interface SatellitePlacement {
  satelliteId: string;
  coordinate: Coordinate;
  overRequestId: string | null;
}

export interface MissionMapModel {
  targets: MapTarget[];
  satellite: SatellitePlacement | null;
  /** Targets in the order the current plan visits them. */
  planSequence: Coordinate[];
  /** [west, south, east, north] around every target, or null with none. */
  bounds: [number, number, number, number] | null;
}

/** One scheduled action reduced to when it runs and where it points. */
interface ScheduledActionPoint {
  requestId: string;
  startMs: number;
  endMs: number;
  coordinate: Coordinate;
}

function targetCoordinate(request: ObservationRequestSchema): Coordinate {
  return [request.target_lon, request.target_lat];
}

function scheduledActionPoints(
  requests: readonly ObservationRequestSchema[],
  plan: MissionPlanSchema | null,
): ScheduledActionPoint[] {
  const requestsById = new Map<string, ObservationRequestSchema>(
    requests.map((request) => [request.id, request]),
  );
  return (plan?.actions ?? [])
    .flatMap((action) => {
      const request = requestsById.get(action.request_id);
      return request === undefined
        ? []
        : [
            {
              requestId: action.request_id,
              startMs: new Date(action.start).getTime(),
              endMs: new Date(action.end).getTime(),
              coordinate: targetCoordinate(request),
            },
          ];
    })
    .sort((left, right) => left.startMs - right.startMs);
}

/**
 * The satellite is drawn over the target its current action observes, and over
 * the last one it observed otherwise. The domain holds no satellite position,
 * so this reads one off the plan rather than inventing geography: with no
 * scheduled action there is nothing to read and nothing is drawn.
 */
export function satellitePlacement(
  scenario: ScenarioSchema,
  plan: MissionPlanSchema | null,
  simulatedTime: string | null,
  requests: readonly ObservationRequestSchema[] = scenario.requests,
): SatellitePlacement | null {
  const points = scheduledActionPoints(requests, plan);
  const first = points[0];
  if (first === undefined) {
    return null;
  }
  const satelliteId = scenario.satellite.id;
  if (simulatedTime === null) {
    return { satelliteId, coordinate: first.coordinate, overRequestId: null };
  }
  const now = new Date(simulatedTime).getTime();

  const observing = points.find((point) => point.startMs <= now && now <= point.endMs);
  if (observing !== undefined) {
    return { satelliteId, coordinate: observing.coordinate, overRequestId: observing.requestId };
  }
  const previous = points.filter((point) => point.endMs < now).at(-1);
  return { satelliteId, coordinate: (previous ?? first).coordinate, overRequestId: null };
}

function targetStatus(
  action: ScheduledActionSchema | null,
  unscheduledReason: string | null,
  completed: boolean,
): TargetPlanStatus {
  if (completed || action?.status === "completed") return "completed";
  if (action !== null) return "scheduled";
  if (unscheduledReason !== null) return "unscheduled";
  return "unplanned";
}

function targetBounds(targets: MapTarget[]): [number, number, number, number] | null {
  if (targets.length === 0) {
    return null;
  }
  const lons = targets.map((target) => target.coordinate[0]);
  const lats = targets.map((target) => target.coordinate[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

/**
 * Everything the map draws, derived only from data the session already holds.
 * Emergency requests arrive through the event log rather than the immutable
 * scenario, so the map draws the whole request pool, reading their targets
 * from the events that carry them.
 */
export function buildMissionMapModel(
  scenario: ScenarioSchema,
  plan: MissionPlanSchema | null,
  missionState: MissionStateSchema | null,
  events: MissionEventSchema[],
): MissionMapModel {
  const requestPool = missionRequestPool(scenario, events);
  const completedIds = new Set(missionState?.completed_request_ids ?? []);
  const targets = requestPool.map((request): MapTarget => {
    const action = plan?.actions.find((candidate) => candidate.request_id === request.id) ?? null;
    const unscheduledReason =
      plan?.unscheduled.find((entry) => entry.request_id === request.id)?.reason_code ?? null;
    return {
      requestId: request.id,
      coordinate: targetCoordinate(request),
      priority: request.priority,
      deadline: request.deadline,
      status: targetStatus(action, unscheduledReason, completedIds.has(request.id)),
      action,
      unscheduledReason,
      eventIds: events
        .filter((event) => eventAnchorRequestId(event) === request.id)
        .map((event) => event.id),
    };
  });

  return {
    targets,
    satellite: satellitePlacement(scenario, plan, missionState?.simulated_time ?? null, requestPool),
    planSequence: scheduledActionPoints(requestPool, plan).map((point) => point.coordinate),
    bounds: targetBounds(targets),
  };
}
