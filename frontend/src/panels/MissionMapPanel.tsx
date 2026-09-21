import { geoEquirectangular, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import landTopology from "world-atlas/land-110m.json";
import type { GeometryCollection } from "topojson-specification";
import type {
  MissionPlanSchema,
  MissionStateSchema,
  ObservationRequestSchema,
  ScenarioSchema,
} from "../api/client";
import { PanelFrame } from "./PanelFrame";

const WIDTH = 720;
const HEIGHT = 360;

const land = feature(
  landTopology,
  landTopology.objects.land as GeometryCollection,
);
const projection = geoEquirectangular().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
const landPath = geoPath(projection)(land) ?? "";

/** Longitude then latitude, the order d3-geo projections take. */
type Coordinate = readonly [number, number];

/** Where the satellite is drawn, and the request it is over if it is observing. */
interface SatellitePlacement {
  coordinate: Coordinate;
  overRequestId: string | null;
}

/** One scheduled action reduced to when it runs and where it points. */
interface ScheduledActionPoint {
  requestId: string;
  startMs: number;
  endMs: number;
  coordinate: Coordinate;
}

function scheduledActionPoints(
  scenario: ScenarioSchema,
  plan: MissionPlanSchema | null,
): ScheduledActionPoint[] {
  const requestsById = new Map<string, ObservationRequestSchema>(
    scenario.requests.map((request) => [request.id, request]),
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
              coordinate: [request.target_lon, request.target_lat] as Coordinate,
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
function satellitePlacement(
  scenario: ScenarioSchema,
  plan: MissionPlanSchema | null,
  simulatedTime: string | null,
): SatellitePlacement | null {
  const points = scheduledActionPoints(scenario, plan);
  const first = points[0];
  if (first === undefined) {
    return null;
  }
  if (simulatedTime === null) {
    return { coordinate: first.coordinate, overRequestId: null };
  }
  const now = new Date(simulatedTime).getTime();

  const observing = points.find((point) => point.startMs <= now && now <= point.endMs);
  if (observing !== undefined) {
    return { coordinate: observing.coordinate, overRequestId: observing.requestId };
  }
  const previous = points.filter((point) => point.endMs < now).at(-1);
  return { coordinate: (previous ?? first).coordinate, overRequestId: null };
}

/** Projects a coordinate to a position within the map's own box. */
function cssPosition(coordinate: Coordinate): { left: string; top: string } | null {
  const point = projection([coordinate[0], coordinate[1]]);
  if (point === null) {
    return null;
  }
  return { left: `${(point[0] / WIDTH) * 100}%`, top: `${(point[1] / HEIGHT) * 100}%` };
}

export function MissionMapPanel({
  scenario,
  plan,
  missionState,
  selectedRequestId,
  onSelectRequest,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  missionState: MissionStateSchema | null;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}) {
  if (scenario === null) {
    return (
      <PanelFrame title="Mission map">
        <p className="text-sm text-neutral-500">
          Load a scenario to see its observation targets.
        </p>
      </PanelFrame>
    );
  }

  const satellite = satellitePlacement(scenario, plan, missionState?.simulated_time ?? null);
  const satelliteAt = satellite === null ? null : cssPosition(satellite.coordinate);

  return (
    <PanelFrame title="Mission map">
      <div className="relative w-full" style={{ aspectRatio: `${WIDTH} / ${HEIGHT}` }}>
        <svg
          aria-hidden="true"
          className="absolute inset-0 h-full w-full rounded bg-neutral-900"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        >
          <path d={landPath} fill="#1f2937" stroke="#374151" strokeWidth={0.5} />
        </svg>
        <div
          role="group"
          aria-label="Observation targets"
          className="absolute inset-0"
        >
          {scenario.requests.map((request) => {
            const at = cssPosition([request.target_lon, request.target_lat]);
            if (at === null) {
              return null;
            }
            const selected = request.id === selectedRequestId;
            return (
              <button
                key={request.id}
                type="button"
                data-request-id={request.id}
                data-selected={selected ? "true" : undefined}
                aria-pressed={selected}
                aria-label={`Target ${request.id}`}
                title={`${request.id} · priority ${request.priority}`}
                onClick={() => onSelectRequest(selected ? null : request.id)}
                style={at}
                className={`absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border ${
                  selected
                    ? "border-fuchsia-300 bg-fuchsia-400"
                    : "border-sky-300 bg-sky-500"
                }`}
              />
            );
          })}
          {satelliteAt === null ? null : (
            <div
              aria-label={`Satellite ${scenario.satellite.id}`}
              data-over-request={satellite?.overRequestId ?? undefined}
              style={satelliteAt}
              className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border border-amber-200 bg-amber-400"
            />
          )}
        </div>
      </div>
    </PanelFrame>
  );
}
