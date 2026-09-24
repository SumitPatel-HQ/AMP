import type {
  MissionPlanSchema,
  PlanChangeType,
  ScenarioSchema,
  ScheduledActionSchema,
  UnscheduledEntrySchema,
} from "../api/client";
import { CHANGED_MARKER, FROZEN_STROKE, STATUS_COLORS } from "./timelinePalette";

const HEIGHT = 28;
const ROW_GAP = 6;
const LEFT_LABEL_WIDTH = 110;
const WIDTH = 720;

const SELECTION_STROKE = "#e879f9";

/** One timeline of one plan, with that plan's unscheduled requests beneath it. */
export interface PlanTimelineProps {
  /** Names this timeline in headings, labels, and both accessible names. */
  label: string;
  scenario: ScenarioSchema;
  plan: MissionPlanSchema;
  /** Drives the frozen rule: an action is frozen once it has started. */
  simulatedTime: string | null;
  /** Change types keyed by request id. Empty on a timeline nothing changed on. */
  changeByRequestId: Record<string, PlanChangeType>;
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string | null) => void;
}

function priorityOf(scenario: ScenarioSchema, requestId: string): string {
  const request = scenario.requests.find((candidate) => candidate.id === requestId);
  return request === undefined ? "unknown" : String(request.priority);
}

function UnscheduledList({
  label,
  scenario,
  entries,
  changeByRequestId,
}: {
  label: string;
  scenario: ScenarioSchema;
  entries: UnscheduledEntrySchema[];
  changeByRequestId: Record<string, PlanChangeType>;
}) {
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-xs uppercase tracking-widest text-neutral-500">Unscheduled</h4>
      {entries.length === 0 ? (
        <p className="text-sm text-neutral-500">
          This plan fitted every request in the pool.
        </p>
      ) : (
        <ul aria-label={`${label} unscheduled requests`} className="space-y-1 text-sm">
          {entries.map((entry) => {
            // A request the replan dropped is marked here, because this is the
            // only place it appears once it has no action to draw.
            const change = changeByRequestId[entry.request_id];
            return (
              <li
                key={entry.request_id}
                data-request-id={entry.request_id}
                data-change={change}
                className="text-amber-300"
              >
                <span className="font-mono">{entry.request_id}</span>
                {" · priority "}
                {priorityOf(scenario, entry.request_id)}
                {" · "}
                <span className="font-mono text-amber-400">{entry.reason_code}</span>
                {change === undefined ? null : (
                  <span className="font-mono text-pink-400">{` · ${change}`}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function PlanTimeline({
  label,
  scenario,
  plan,
  simulatedTime,
  changeByRequestId,
  selectedRequestId,
  onSelectRequest,
}: PlanTimelineProps) {
  const rangeStart = new Date(scenario.start_time).getTime();
  const rangeEnd = new Date(scenario.end_time).getTime();
  const rangeMs = Math.max(rangeEnd - rangeStart, 1);
  const trackWidth = WIDTH - LEFT_LABEL_WIDTH;
  const svgHeight = plan.actions.length * (HEIGHT + ROW_GAP) + ROW_GAP;
  const simulatedMs = simulatedTime === null ? null : new Date(simulatedTime).getTime();

  const toX = (isoTime: string): number => {
    const offset = new Date(isoTime).getTime() - rangeStart;
    return LEFT_LABEL_WIDTH + (offset / rangeMs) * trackWidth;
  };

  // The planner's rule, read from the same two values it reads: an action is
  // frozen once its start time is at or before the current simulated time.
  const isFrozen = (action: ScheduledActionSchema): boolean =>
    simulatedMs !== null && new Date(action.start).getTime() <= simulatedMs;

  return (
    <div role="group" aria-label={label} className="flex flex-col gap-2">
      <h3 className="text-xs uppercase tracking-widest text-neutral-400">
        {label} <span className="text-neutral-500">V{plan.version}</span>
      </h3>
      {plan.actions.length === 0 ? (
        <p className="text-sm text-neutral-500">Plan has no scheduled actions.</p>
      ) : (
        <svg
          role="group"
          aria-label={`${label} timeline of scheduled actions`}
          width="100%"
          viewBox={`0 0 ${WIDTH} ${svgHeight}`}
        >
          {plan.actions.map((action, index) => {
            const y = ROW_GAP + index * (HEIGHT + ROW_GAP);
            const x1 = toX(action.start);
            const x2 = toX(action.end);
            const frozen = isFrozen(action);
            const change = changeByRequestId[action.request_id];
            const selected = action.request_id === selectedRequestId;
            return (
              <g
                key={action.id}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                aria-label={[
                  action.request_id,
                  frozen ? "frozen and untouchable by replanning" : "still replannable",
                  change === undefined ? null : `${change} by the last replan`,
                ]
                  .filter((part) => part !== null)
                  .join(", ")}
                data-request-id={action.request_id}
                data-frozen={frozen ? "true" : "false"}
                data-change={change}
                data-selected={selected ? "true" : undefined}
                onClick={() => onSelectRequest(selected ? null : action.request_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectRequest(selected ? null : action.request_id);
                  }
                }}
                className="cursor-pointer"
              >
                <text
                  x={0}
                  y={y + HEIGHT / 2}
                  dominantBaseline="middle"
                  fontSize={11}
                  fill={selected ? "#f9fafb" : "#9ca3af"}
                >
                  {change === undefined
                    ? action.request_id
                    : `${action.request_id} · ${change}`}
                </text>
                <rect
                  x={x1}
                  y={y}
                  width={Math.max(x2 - x1, 2)}
                  height={HEIGHT}
                  rx={2}
                  fill={STATUS_COLORS[action.status]}
                  fillOpacity={frozen ? 0.45 : 1}
                  stroke={frozen ? FROZEN_STROKE : undefined}
                  strokeWidth={frozen ? 2 : undefined}
                  strokeDasharray={frozen ? "3 2" : undefined}
                />
                {change === undefined ? null : (
                  <circle cx={x1} cy={y} r={3.5} fill={CHANGED_MARKER} />
                )}
                {selected ? (
                  <rect
                    x={0}
                    y={y - 2}
                    width={WIDTH}
                    height={HEIGHT + 4}
                    rx={3}
                    fill="none"
                    stroke={SELECTION_STROKE}
                    strokeWidth={1}
                  />
                ) : null}
              </g>
            );
          })}
        </svg>
      )}
      <UnscheduledList
        label={label}
        scenario={scenario}
        entries={plan.unscheduled}
        changeByRequestId={changeByRequestId}
      />
    </div>
  );
}
