import { BookOpen, ChevronDown, ChevronRight, Clock3, FilePlus2, FolderOpen, ListChecks, Play, RefreshCw, RotateCcw, Settings2, ShieldCheck, SkipForward, TriangleAlert, X, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
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

function SettingsCard({ icon: Icon, title, description, danger = false, ...props }: {
  icon: LucideIcon;
  title: string;
  description: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return <button type="button" title={danger ? "Reset mission clock, plans, and events back to the initial scenario" : undefined} aria-label={title} className={`amis-settings-card${danger ? " amis-settings-card-danger" : ""}`} {...props}>
    <span className="amis-settings-card-icon"><Icon size={20} aria-hidden="true" /></span>
    <span className="min-w-0 flex-1"><span className="amis-settings-card-title block font-semibold">{title}</span><span className="amis-settings-card-description">{description}</span></span>
    <ChevronRight size={16} aria-hidden="true" />
  </button>;
}

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
    return <span className="text-xs text-neutral-400">--:--:-- UTC</span>;
  }
  const start = new Date(scenario.start_time).getTime();
  const now = new Date(missionState.simulated_time).getTime();
  const end = new Date(scenario.end_time).getTime();
  const iso = new Date(missionState.simulated_time).toISOString();
  return (
    <div className="flex shrink-0 items-baseline gap-2 whitespace-nowrap" aria-label="Mission time">
      <Clock3 size={14} aria-hidden="true" className="self-center text-neutral-400" />
      <span className="text-sm font-semibold tabular-nums text-neutral-100">
        {`${iso.slice(0, 10)} ${iso.slice(11, 19)} UTC`}
      </span>
      <span className="text-[12px] tabular-nums text-neutral-400">
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
      <span className="shrink-0 whitespace-nowrap rounded-sm border border-sky-800 px-1.5 text-[12px]  text-sky-300">
        Working
      </span>
    );
  }
  if (missionState === null) {
    return null;
  }
  if (!missionState.mission_complete && !hasPlan) {
    return (
      <span className="shrink-0 whitespace-nowrap rounded-sm border border-neutral-800 px-1.5 text-[12px]  text-neutral-400">
        No plan
      </span>
    );
  }
  return missionState.mission_complete ? (
    <span className="shrink-0 whitespace-nowrap rounded-sm border border-emerald-800 px-1.5 text-[12px]  text-emerald-300">
      Complete
    </span>
  ) : (
    <span className="shrink-0 whitespace-nowrap rounded-sm border border-neutral-700 px-1.5 text-[12px]  text-neutral-300">
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
  missionContextStale = false,
  onLoadDemo,
  onNewMission,
  settingsOpen: controlledSettingsOpen,
  onOpenSettings,
  onCloseSettings,
  onLoadMission,
  onExamples,
  onFeasibility,
  onGeneratePlan,
  onResetMission,
  onStep,
  onInjectEvent,
  onReplan,
  planner,
  policy,
  onPlannerChange,
  onPolicyChange,
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
  missionContextStale?: boolean;
  onLoadDemo: () => void;
  settingsOpen?: boolean;
  onOpenSettings?: () => void;
  onCloseSettings?: () => void;
  onNewMission: () => void;
  onLoadMission: () => void;
  onExamples: () => void;
  /** Opens the read-only, window-only feasibility comparison. */
  onFeasibility: () => void;
  onGeneratePlan: () => void;
  onResetMission: () => void;
  onStep: (seconds: number) => void;
  onInjectEvent: (event: MissionEventRequest) => Promise<boolean>;
  planner?: "greedy" | "cp_sat";
  policy?: "utility" | "utility_then_fairness";
  onPlannerChange?: (planner: "greedy" | "cp_sat") => void;
  onPolicyChange?: (policy: "utility" | "utility_then_fairness") => void;
  onReplan: () => void;
}) {
  const [localSettingsOpen, setSettingsOpen] = useState(false);
  const settingsOpen = controlledSettingsOpen ?? localSettingsOpen;
  const settingsRef = useRef<HTMLDialogElement>(null);
  const settingsButtonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (settingsOpen) settingsRef.current?.showModal();
    else if (settingsRef.current?.open) settingsRef.current.close();
  }, [settingsOpen]);
  function closeSettings() {
    if (onCloseSettings) onCloseSettings();
    else setSettingsOpen(false);
    settingsButtonRef.current?.focus();
  }
  function runSettingsAction(action: () => void) {
    if (!onOpenSettings || action === onLoadDemo || action === onResetMission) closeSettings();
    setEventOpen(false);
    action();
  }
  const [seconds, setSeconds] = useState(300);
  const [eventOpen, setEventOpen] = useState(false);
  const eventButtonRef = useRef<HTMLButtonElement>(null);
  const eventVisible = eventOpen && missionState?.mission_complete !== true && plan !== null;

  return (
    <header className="amis-mission-bar relative z-20 flex min-h-9 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-[var(--amis-border)] bg-[var(--amis-surface)] px-3 py-1">
      <div className="flex min-w-0 items-center gap-3">
        <span className="rounded-sm border border-neutral-600 px-1.5 text-xs font-bold tracking-[0.2em] text-neutral-100">
          AMIS
        </span>
        {scenario === null ? (
          <span className="text-xs text-neutral-400">No scenario loaded.</span>
        ) : (
          <div className="flex min-w-0 items-baseline gap-2 whitespace-nowrap">
            <span className="truncate text-lg font-semibold text-neutral-200" title={scenario.name}>
              {scenario.name}
            </span>
            <span className="hidden max-w-48 truncate text-[12px] text-neutral-400 2xl:inline" title={scenario.id}>
              {scenario.id}
            </span>
            <span className="shrink-0 text-[12px] text-neutral-400">{scenario.satellite.id}</span>
          </div>
        )}
      </div>

      <Divider />
      <MissionClock scenario={scenario} missionState={missionState} />
      <StatusChip missionState={missionState} hasPlan={plan !== null} loading={loading} />
      {scenario === null ? null : plan === null ? (
        <span className="shrink-0 whitespace-nowrap text-[12px] text-neutral-400">no plan</span>
      ) : (
        <span
          aria-label={`Current plan V${plan.version}`}
          title={plan.id}
          className="shrink-0 whitespace-nowrap rounded-sm border border-sky-800 bg-sky-950/40 px-1.5 text-[12px] font-semibold text-sky-200"
        >
          Plan{" "}
          {previousVersion === null ? null : (
            <span className="font-normal text-neutral-400">{`V${previousVersion} → `}</span>
          )}
          {`V${plan.version}`}
        </span>
      )}

      <div className="amis-controls ml-auto flex flex-wrap items-center gap-2">
        <button ref={settingsButtonRef} type="button" className={`${CONTROL_BUTTON} amis-settings-trigger`} aria-haspopup="dialog" aria-expanded={settingsOpen} aria-controls="mission-settings" onClick={() => { setEventOpen(false); if (onOpenSettings) onOpenSettings(); else setSettingsOpen(true); }}>
          <Settings2 size={15} aria-hidden="true" />Mission & settings<ChevronDown size={14} aria-hidden="true" />
        </button>
        <dialog ref={settingsRef} id="mission-settings" className="amis-settings-modal" aria-labelledby="settings-title" aria-describedby="settings-subtitle" onCancel={(event) => { event.preventDefault(); closeSettings(); }} onClick={(event) => {
          if (event.target === event.currentTarget) {
            const bounds = event.currentTarget.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeSettings();
          }
        }}>
          <div className="amis-settings-header">
            <div><h2 id="settings-title" tabIndex={-1} autoFocus>Mission & Settings</h2><p id="settings-subtitle">Manage scenario and planning preferences</p></div>
            <button type="button" className="amis-settings-close" aria-label="Close Mission & Settings" onClick={closeSettings}><X size={20} aria-hidden="true" /></button>
          </div>
          <section className="amis-settings-section" aria-labelledby="settings-mission-title">
            <h3 id="settings-mission-title">Mission</h3>
            <div className="amis-settings-grid">
              <SettingsCard icon={FilePlus2} title="New mission" description="Create a new mission" onClick={() => runSettingsAction(onNewMission)} />
              <SettingsCard icon={FolderOpen} title="Load mission" description="Open an existing mission" onClick={() => runSettingsAction(onLoadMission)} />
              <SettingsCard icon={BookOpen} title="Browse examples" description="Explore example scenarios" onClick={() => runSettingsAction(onExamples)} />
              <SettingsCard icon={Play} title="Load demo scenario" description="Load the predefined demo" disabled={loading} onClick={() => runSettingsAction(onLoadDemo)} />
            </div>
          </section>
          <section className="amis-settings-section" aria-labelledby="settings-planning-title">
            <h3 id="settings-planning-title">Planning Configuration</h3>
        <div className="amis-settings-field">
          <label htmlFor="planner-select" className="text-sm text-mission-muted">
            Planner
          </label>
          <div className="amis-settings-select-wrap">
          <select
            id="planner-select"
            aria-label="Planner selection"
            value={planner ?? "greedy"}
            onChange={(e) => onPlannerChange?.(e.target.value as "greedy" | "cp_sat")}
            disabled={loading}
            className={`${CONTROL_INPUT} amis-settings-select`}
          >
            <option value="greedy">Greedy</option>
            <option value="cp_sat">CP-SAT</option>
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          </div>
        </div>
        <div className="amis-settings-field">
          <label htmlFor="policy-select" className="text-sm text-mission-muted">
            Optimization Policy
          </label>
          <div className="amis-settings-select-wrap">
          <select
            id="policy-select"
            aria-label="Planning policy"
            value={policy ?? "utility"}
            onChange={(e) => onPolicyChange?.(e.target.value as "utility" | "utility_then_fairness")}
            disabled={loading}
            aria-describedby="settings-policy-help"
            title={planner === "greedy" ? "Fairness policy requires CP-SAT planner" : undefined}
            className={`${CONTROL_INPUT} amis-settings-select`}
          >
            <option value="utility">Pure Utility</option>
            <option value="utility_then_fairness" disabled={planner === "greedy"}>
              Utility-then-Fairness
            </option>
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          </div>
            <p id="settings-policy-help" className="amis-settings-policy-help">Utility-then-Fairness requires the CP-SAT planner.</p>
        </div>
          </section>
          <section className="amis-settings-section" aria-labelledby="settings-tools-title">
            <h3 id="settings-tools-title">Mission Tools</h3>
            <div className="amis-settings-grid">
              <SettingsCard icon={ShieldCheck} title="Feasibility Analysis" description="Review observation feasibility." disabled={scenario === null} onClick={() => runSettingsAction(onFeasibility)} />
              <SettingsCard icon={RotateCcw} title="Reset mission" description="Reset clock, plans, and events" danger disabled={loading || scenario === null || (plan === null && events.length === 0 && missionState?.simulated_time === scenario?.start_time)} onClick={() => runSettingsAction(onResetMission)} />
            </div>
          </section>
        </dialog>
        <button
          type="button"
          onClick={() => {
            setEventOpen(false);
            onGeneratePlan();
          }}
          disabled={
            loading || scenario === null || plan !== null || missionState?.mission_complete === true
          }
          className={plan === null ? REPLAN_BUTTON_PRIMARY : CONTROL_BUTTON}
        >
          <ListChecks size={14} aria-hidden="true" />Generate plan
        </button>
        <Divider />
        <label className="text-[12px] uppercase text-neutral-400" htmlFor="step-seconds">
          seconds
        </label>
        <input
          id="step-seconds"
          type="number"
          min={1}
          step={1}
          value={seconds}
          disabled={missionContextStale || missionState === null || missionState.mission_complete}
          onChange={(event) => setSeconds(Number(event.target.value))}
          className={`${CONTROL_INPUT} w-16`}
        />
        <button
          type="button"
          onClick={() => onStep(seconds)}
          disabled={loading || missionContextStale || missionState === null || missionState.mission_complete || !(seconds > 0)}
          title={missionContextStale ? "Refresh the current plan before stepping the mission" : undefined}
          className={CONTROL_BUTTON}
        >
          <SkipForward size={14} aria-hidden="true" />Step
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
            disabled={loading || missionContextStale || plan === null || missionState === null || missionState.mission_complete}
            title={missionContextStale ? "Refresh the current plan before injecting an event" : plan === null ? "Generate a plan first: events are evaluated against it" : undefined}
            className={eventVisible ? EVENT_BUTTON_OPEN : EVENT_BUTTON}
          >
            <TriangleAlert size={14} aria-hidden="true" />Event
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
            replanBlocked
              ? "Refresh the backend's current plan before replanning"
              : plan === null
              ? "Generate a plan first"
              : `Build the next version from Plan V${plan.version}; V${plan.version} stays unchanged`
          }
          className={awaitingReplan ? REPLAN_BUTTON_PRIMARY : REPLAN_BUTTON}
        >
          <RefreshCw size={14} aria-hidden="true" />Replan
        </button>
      </div>
    </header>
  );
}
