import type {
  MissionPlanSchema,
  ScenarioSchema,
  ScheduledActionSchema,
} from "../api/client";
import { PanelFrame } from "./PanelFrame";

const HEIGHT = 28;
const ROW_GAP = 6;
const LEFT_LABEL_WIDTH = 110;

const STATUS_COLORS: Record<ScheduledActionSchema["status"], string> = {
  planned: "#3b82f6",
  started: "#f59e0b",
  completed: "#10b981",
};

export function TimelinePanel({
  scenario,
  plan,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
}) {
  if (scenario === null || plan === null) {
    return (
      <PanelFrame title="Timeline">
        <p className="text-sm text-neutral-500">
          Load a scenario and generate a plan to see scheduled actions.
        </p>
      </PanelFrame>
    );
  }

  const rangeStart = new Date(scenario.start_time).getTime();
  const rangeEnd = new Date(scenario.end_time).getTime();
  const rangeMs = Math.max(rangeEnd - rangeStart, 1);
  const width = 720;
  const trackWidth = width - LEFT_LABEL_WIDTH;
  const svgHeight = plan.actions.length * (HEIGHT + ROW_GAP) + ROW_GAP;

  const toX = (isoTime: string): number => {
    const offset = new Date(isoTime).getTime() - rangeStart;
    return LEFT_LABEL_WIDTH + (offset / rangeMs) * trackWidth;
  };

  return (
    <PanelFrame title="Timeline">
      {plan.actions.length === 0 ? (
        <p className="text-sm text-neutral-500">Plan has no scheduled actions.</p>
      ) : (
        <svg
          role="img"
          aria-label="Mission timeline of scheduled actions"
          width="100%"
          viewBox={`0 0 ${width} ${svgHeight}`}
        >
          {plan.actions.map((action, index) => {
            const y = ROW_GAP + index * (HEIGHT + ROW_GAP);
            const x1 = toX(action.start);
            const x2 = toX(action.end);
            return (
              <g key={action.id}>
                <text
                  x={0}
                  y={y + HEIGHT / 2}
                  dominantBaseline="middle"
                  fontSize={11}
                  fill="#9ca3af"
                >
                  {action.request_id}
                </text>
                <rect
                  x={x1}
                  y={y}
                  width={Math.max(x2 - x1, 2)}
                  height={HEIGHT}
                  rx={2}
                  fill={STATUS_COLORS[action.status]}
                />
              </g>
            );
          })}
        </svg>
      )}
    </PanelFrame>
  );
}
