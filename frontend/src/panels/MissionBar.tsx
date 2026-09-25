import { useRef, useState } from "react";
import type {
  MissionEventRequest,
  MissionEventSchema,
  MissionPlanSchema,
  MissionStateSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import {
  CONTROL_BUTTON,
  CONTROL_INPUT,
  EVENT_BUTTON,
  EVENT_BUTTON_OPEN,
  REPLAN_BUTTON,
  REPLAN_BUTTON_PRIMARY,
} from "./controls";
import { EventControl } from "./EventControl";

/** hh:mm:ss of a non-negative span, the format the mission clock counts in. */
function formatSpan(ms: number): string {
  const totalSeconds = Math.max(Math.floor(ms / 1000), 0);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

function Divider() {
  return <span aria-hidden="true" className="h-5 w-px bg-[var(--amis-border)]" />;
}

/** Simulated UTC time plus elapsed/total, both read from scenario and state. */
function MissionClock({
  scenario,
  missionState,
}: {
  scenario: ScenarioSchema | null;
  missionState: MissionStateSchema | null;
}) {
  if (scenario === null || missionState === null) {
    return <span className="text-xs text-neutral-600">--:--:-- UTC</span>;
  }
  const start = new Date(scenario.start_time).getTime();
  const now = new Date(missionState.simulated_time).getTime();
  const end = new Date(scenario.end_time).getTime();
  const iso = new Date(missionState.simulated_time).toISOString();
  return (
    <div className="flex shrink-0 items-baseline gap-2 whitespace-nowrap" aria-label="Mission time">
      <span className="text-sm font-semibold tabular-nums text-neutral-100">
        {`${iso.slice(0, 10)} ${iso.slice(11, 19)} UTC`}
      </span>
      <span className="text-[11px] tabular-nums text-neutral-500">
        {`T+${formatSpan(now - start)} / ${formatSpan(end - start)}`}
      </span>
    </div>
  );
}

/**
 * The lifecycle read from two facts the session holds: whether the mission
 * state reports completion, and whether a plan exists to run.
 */
function StatusChip({
  missionState,
  hasPlan,
  loading,
}: {
  missionState: MissionStateSchema | null;
  hasPlan: boolean;
  loading: boolean;
}) {
  if (loading) {
    return (
      <span className="shrink-0 whitespace-nowrap rounded-sm border border-sky-800 px-1.5 text-[10px] uppercase tracking-wider text-sky-300">
        Working
      </span>
    );
  }
  if (missionState === null) {
    return null;
  }
  if (!missionState.mission_complete && !hasPlan) {
    return (
      <span className="shrink-0 whitespace-nowrap rounded-sm border border-neutral-800 px-1.5 text-[10px] uppercase tracking-wider text-neutral-500">
        No plan
      </span>
    );
  }
  return missionState.mission_complete ? (
    <span className="shrink-0 whitespace-nowrap rounded-sm border border-emerald-800 px-1.5 text-[10px] uppercase tracking-wider text-emerald-300">
      Complete
    </span>
  ) : (
    <span className="shrink-0 whitespace-nowrap rounded-sm border border-neutral-700 px-1.5 text-[10px] uppercase tracking-wider text-neutral-300">
      In progress
    </span>
  );
}

/**
 * The persistent mission bar: who the mission is, where its clock stands, and
 * every lifecycle action (load, plan, step, event, replan) in one row.
 */
export function MissionBar({
  scenario,
  plan,
  previousVersion,
  awaitingReplan,
  missionState,
  windows,
  events,
  loading,
  replanning,
  replanBlocked = false,
  onLoadDemo,
  onGeneratePlan,
  onStep,
  onInjectEvent,
  onReplan,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  /** The version the last replan started from, while the current plan is its result. */
  previousVersion: number | null;
  /** An event has invalidated the current plan and no replan has answered it yet. */
  awaitingReplan: boolean;
  missionState: MissionStateSchema | null;
  windows: ObservationWindowSchema[];
  events: MissionEventSchema[];
  loading: boolean;
  /** A replan request is in flight. */
  replanning: boolean;
  replanBlocked?: boolean;
  onLoadDemo: () => void;
  onGeneratePlan: () => void;
  onStep: (seconds: number) => void;
  onInjectEvent: (event: MissionEventRequest) => Promise<boolean>;
  onReplan: () => void;
}) {
  const [seconds, setSeconds] = useState(300);
  const [eventOpen, setEventOpen] = useState(false);
  const eventButtonRef = useRef<HTMLButtonElement>(null);
  const eventVisible = eventOpen && missionState?.mission_complete !== true && plan !== null;

  return (
    <header className="relative z-20 flex min-h-9 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-[var(--amis-border)] bg-[var(--amis-surface)] px-3 py-1">
      <div className="flex min-w-0 items-center gap-3">
        <span className="rounded-sm border border-neutral-600 px-1.5 text-xs font-bold tracking-[0.2em] text-neutral-100">
          AMIS
        </span>
        {scenario === null ? (
          <span className="text-xs text-neutral-500">No scenario loaded.</span>
        ) : (
          <div className="flex min-w-0 items-baseline gap-2 whitespace-nowrap">
            <span className="truncate text-xs font-semibold text-neutral-200" title={scenario.name}>
              {scenario.name}
            </span>
            <span className="hidden max-w-48 truncate text-[10px] text-neutral-500 2xl:inline" title={scenario.id}>
              {scenario.id}
            </span>
            <span className="shrink-0 text-[10px] text-neutral-500">{scenario.satellite.id}</span>
          </div>
        )}
      </div>

      <Divider />
      <MissionClock scenario={scenario} missionState={missionState} />
      <StatusChip missionState={missionState} hasPlan={plan !== null} loading={loading} />
      {scenario === null ? null : plan === null ? (
        <span className="shrink-0 whitespace-nowrap text-[11px] text-neutral-500">no plan</span>
      ) : (
        <span
          aria-label={`Current plan V${plan.version}`}
          title={plan.id}
          className="shrink-0 whitespace-nowrap rounded-sm border border-sky-800 bg-sky-950/40 px-1.5 text-[11px] font-semibold text-sky-200"
        >
          Plan{" "}
          {previousVersion === null ? null : (
            <span className="font-normal text-neutral-400">{`V${previousVersion} → `}</span>
          )}
          {`V${plan.version}`}
        </span>
      )}

      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => {
            setEventOpen(false);
            onLoadDemo();
          }}
          disabled={loading}
          className={CONTROL_BUTTON}
        >
          Load demo scenario
        </button>
        <button
          type="button"
          onClick={() => {
            setEventOpen(false);
            onGeneratePlan();
          }}
          disabled={loading || scenario === null || missionState?.mission_complete === true}
          className={CONTROL_BUTTON}
        >
          Generate plan
        </button>
        <Divider />
        <label className="text-[10px] uppercase text-neutral-500" htmlFor="step-seconds">
          seconds
        </label>
        <input
          id="step-seconds"
          type="number"
          min={1}
          step={1}
          value={seconds}
          disabled={missionState === null || missionState.mission_complete}
          onChange={(event) => setSeconds(Number(event.target.value))}
          className={`${CONTROL_INPUT} w-16`}
        />
        <button
          type="button"
          onClick={() => onStep(seconds)}
          disabled={loading || missionState === null || missionState.mission_complete || !(seconds > 0)}
          className={CONTROL_BUTTON}
        >
          Step
        </button>
        <div
          className="relative"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setEventOpen(false);
              eventButtonRef.current?.focus();
            }
          }}
        >
          <button
            ref={eventButtonRef}
            type="button"
            aria-expanded={eventVisible}
            aria-controls="event-control"
            onClick={() => setEventOpen((open) => !open)}
            // The backend evaluates every event against the current plan, so
            // there is nothing to inject into before one exists.
            disabled={loading || plan === null || missionState === null || missionState.mission_complete}
            title={plan === null ? "Generate a plan first: events are evaluated against it" : undefined}
            className={eventVisible ? EVENT_BUTTON_OPEN : EVENT_BUTTON}
          >
            Event
          </button>
          {eventVisible && scenario !== null && missionState !== null ? (
            <div
              id="event-control"
              className="absolute right-0 top-8 w-max border border-[var(--amis-border)] bg-[var(--amis-surface)] p-2.5 shadow-lg shadow-black/60"
            >
              <EventControl
                scenario={scenario}
                plan={plan}
                missionState={missionState}
                windows={windows}
                events={events}
                loading={loading}
                onInjectEvent={onInjectEvent}
                onInjected={() => setEventOpen(false)}
              />
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onReplan}
          disabled={loading || plan === null || missionState?.mission_complete === true || replanBlocked}
          aria-busy={replanning}
          title={
            plan === null
              ? "Generate a plan first"
              : `Build the next version from Plan V${plan.version}; V${plan.version} stays unchanged`
          }
          className={awaitingReplan ? REPLAN_BUTTON_PRIMARY : REPLAN_BUTTON}
        >
          Replan
        </button>
      </div>
    </header>
  );
}
