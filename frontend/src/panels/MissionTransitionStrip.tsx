import type { ReactNode } from "react";
import type {
  EventStage,
  ImpactStage,
  MissionTransition,
  PlanStage,
  TransitionStage,
} from "../state/missionTransition";
import { clockTime, shortPlanId } from "./format";

const TONES = {
  plan: "border-sky-700/70 text-sky-300",
  current: "border-emerald-700/70 text-emerald-300",
  event: "border-red-700/70 text-red-300",
  impact: "border-amber-700/70 text-amber-300",
  pending: "border-dashed border-amber-600/80 text-amber-200",
  quiet: "border-neutral-700 text-neutral-400",
} as const;

function Stage({
  label,
  tone,
  title,
  line,
  note,
}: {
  label: string;
  tone: keyof typeof TONES;
  title: ReactNode;
  line: string;
  /** Quieter context under the line, such as an id or a time. */
  note: string;
}) {
  return (
    <li
      aria-label={label}
      className={`flex min-w-0 flex-1 flex-col justify-center border-l-2 bg-white/[0.02] px-2.5 leading-4 ${TONES[tone]}`}
    >
      <p className="truncate text-xs font-semibold uppercase tracking-wide">{title}</p>
      <p className="truncate text-[11px] text-neutral-200">{line}</p>
      <p className="truncate text-[11px] text-neutral-500">{note}</p>
    </li>
  );
}

function Arrow() {
  return (
    <li aria-hidden="true" className="flex shrink-0 items-center px-1.5 text-neutral-600">
      →
    </li>
  );
}

function PlanCell({ stage, afterReplan }: { stage: PlanStage; afterReplan: boolean }) {
  const role =
    stage.role === "previous"
      ? "previous"
      : stage.role === "evaluated"
        ? "current · evaluated"
        : afterReplan
          ? "current · replanned"
          : "current";
  return (
    <Stage
      label={`Plan V${stage.version} (${stage.role === "previous" ? "previous" : "current"})`}
      tone={stage.role === "current" && afterReplan ? "current" : "plan"}
      title={
        <>
          Plan V{stage.version} <span className="font-normal normal-case text-neutral-500">({role})</span>
        </>
      }
      line={`${stage.scheduled} / ${stage.requestCount} scheduled`}
      note={shortPlanId(stage.planId)}
    />
  );
}

function EventCell({ stage }: { stage: EventStage }) {
  return (
    <Stage
      label={`Event ${stage.eventId}`}
      tone="event"
      title={`${stage.eventType ?? "Event"} · ${stage.eventId}`}
      line={stage.requestId === null ? "payload unavailable" : `${stage.requestId} / ${stage.windowId}`}
      note={stage.time === null ? "time unavailable" : `at ${clockTime(stage.time)} UTC`}
    />
  );
}

function ImpactCell({ stage }: { stage: ImpactStage }) {
  const count =
    stage.invalidCount === 0
      ? "No scheduled action invalid"
      : `${stage.invalidCount} scheduled action${stage.invalidCount === 1 ? "" : "s"} invalid`;
  return (
    <Stage
      label="Impact"
      tone={stage.invalidCount === 0 ? "quiet" : "impact"}
      title="Impact"
      line={count}
      note={
        stage.affectedRequestIds.length === 0
          ? "plan still feasible"
          : `${stage.affectedRequestIds.join(", ")} · ${stage.reasonCodes.join(", ")}`
      }
    />
  );
}

function StageCell({ stage, afterReplan }: { stage: TransitionStage; afterReplan: boolean }) {
  switch (stage.kind) {
    case "plan":
      return <PlanCell stage={stage} afterReplan={afterReplan} />;
    case "event":
      return <EventCell stage={stage} />;
    case "impact":
      return <ImpactCell stage={stage} />;
    case "awaiting-replan":
      return (
        <Stage
          label="Awaiting replan"
          tone="pending"
          title="Awaiting replan"
          line="Replan builds the next plan version"
          note="from the current mission state"
        />
      );
    case "no-event":
      return (
        <Stage
          label="Replan without event"
          tone="quiet"
          title="Replan"
          line="No new event"
          note="replanned on request"
        />
      );
  }
}

/**
 * The mission's story so far in one row: the plan in force, the event that
 * hit it, what that event invalidated, and whether a replan has answered it.
 */
export function MissionTransitionStrip({
  transition,
  hasScenario,
}: {
  transition: MissionTransition;
  hasScenario: boolean;
}) {
  const afterReplan = transition.phase === "replanned";
  return (
    <section
      aria-label="Mission transition"
      className="flex h-[58px] shrink-0 items-stretch gap-1 border-b border-[var(--amis-border)] bg-[var(--amis-surface)] px-1 py-1"
    >
      {transition.stages.length === 0 ? (
        <p className="flex items-center px-2 text-xs text-neutral-500">
          {hasScenario
            ? "No plan yet. Generate plan to build Plan V1 for this mission."
            : "Load a scenario to start a mission."}
        </p>
      ) : (
        <ol className="flex min-w-0 flex-1 items-stretch">
          {transition.stages.map((stage, index) => (
            <StageGroup key={`${stage.kind}-${index}`} first={index === 0}>
              <StageCell stage={stage} afterReplan={afterReplan} />
            </StageGroup>
          ))}
          {transition.phase === "planned" ? (
            <>
              <Arrow />
              <li className="flex min-w-0 flex-[3] items-center px-2.5 text-[11px] text-neutral-500">
                No event yet. Step the clock or inject an event to disrupt this plan.
              </li>
            </>
          ) : null}
        </ol>
      )}
    </section>
  );
}

function StageGroup({ first, children }: { first: boolean; children: ReactNode }) {
  return (
    <>
      {first ? null : <Arrow />}
      {children}
    </>
  );
}
