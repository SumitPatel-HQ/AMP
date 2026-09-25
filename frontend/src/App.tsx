import { useMissionSession } from "./state/useMissionSession";
import { missionTransition, type MissionTransition } from "./state/missionTransition";
import { eventSummary } from "./state/missionEvent";
import { planLabel } from "./state/planContext";
import { clockTime } from "./panels/format";
import { ErrorBanner, PlanConflictBanner } from "./panels/ErrorBanner";
import { ImpactPanel } from "./panels/ImpactPanel";
import { MetricsPanel } from "./panels/MetricsPanel";
import { MissionBar } from "./panels/MissionBar";
import { MissionMapPanel } from "./panels/MissionMapPanel";
import { MissionNavPanel } from "./panels/MissionNavPanel";
import { MissionTransitionStrip } from "./panels/MissionTransitionStrip";
import { PlanComparisonPanel } from "./panels/PlanComparisonPanel";
import { StatePanel } from "./panels/StatePanel";
import { TimelinePanel } from "./panels/TimelinePanel";

type Session = ReturnType<typeof useMissionSession>;

function MissionFocus({ session }: { session: Session }) {
  const { selection } = session;
  if (Object.values(selection).every((value) => value === null)) return null;
  const request = session.requestPool.find((item) => item.id === selection.requestId);
  const window = session.windows.find((item) => item.id === selection.windowId);
  const event = session.events.find((item) => item.id === selection.eventId);
  const parts = [
    selection.requestId === null ? null : request === undefined ? selection.requestId : `${request.id} · P${request.priority} · deadline ${clockTime(request.deadline)} UTC`,
    selection.windowId === null ? null : window === undefined ? selection.windowId : `${window.id} · ${clockTime(window.start)}–${clockTime(window.end)} UTC${window.valid ? "" : " · invalid"}`,
    selection.eventId === null ? null : event === undefined ? selection.eventId : `${event.id} · ${eventSummary(event)}`,
    selection.planId === null ? null : `Selected ${planLabel(selection.planId, session.plans)}`,
  ].filter((part) => part !== null);
  return (
    <div role="status" aria-label="Mission focus" className="flex min-h-7 shrink-0 items-center gap-2 border-b border-[var(--amis-border)] bg-fuchsia-950/20 px-3 text-[11px]">
      <span className="shrink-0 font-semibold uppercase tracking-wide text-fuchsia-300">Focus</span>
      <span className="min-w-0 flex-1 truncate text-neutral-200" title={parts.join(" · ")}>{parts.join(" · ")}</span>
      {selection.planId !== null && selection.planId !== session.plan?.id ? (
        <span className="hidden shrink-0 text-neutral-500 lg:inline">Timeline shows current V{session.plan?.version}</span>
      ) : null}
      <button type="button" onClick={session.clearSelection} className="shrink-0 text-neutral-400 hover:text-neutral-100">Clear focus</button>
    </div>
  );
}

/**
 * The mission workspace, one viewport tall. Mission objects to the left, the
 * map at the centre and live state to the right; the timeline spans the full
 * width beneath them, and the analysis of the current transition sits at the
 * bottom. Each region scrolls on its own so none of them pushes the others off
 * screen.
 */
function MissionWorkspace({
  session,
  transition,
}: {
  session: Session;
  transition: MissionTransition;
}) {
  const { selection, replanResult } = session;
  const plans = session.plans;
  return (
    <main className="amis-workspace grid min-h-0 min-w-0 flex-1 gap-1 p-1">
      <MissionNavPanel
        scenario={session.scenario}
        plan={session.plan}
        plans={plans}
        replanResult={replanResult}
        impact={session.impact}
        missionState={session.missionState}
        windows={session.windows}
        events={session.events}
        requestPool={session.requestPool}
        selection={selection}
        onSelectRequest={session.selectRequest}
        onSelectWindow={session.selectWindow}
        onSelectEvent={session.selectEvent}
        onSelectPlan={session.selectPlan}
      />
      <MissionMapPanel
        scenario={session.scenario}
        plan={session.plan}
        missionState={session.missionState}
        events={session.events}
        requestPool={session.requestPool}
        selectedRequestId={selection.requestId}
        onSelectRequest={session.selectRequest}
      />
      <StatePanel
        state={session.missionState}
        events={session.events}
        plan={session.plan}
        replanned={replanResult !== null && replanResult.revisedPlan.id === session.plan?.id}
        satelliteCapacityWh={session.scenario?.satellite.battery_capacity_wh ?? null}
        storageCapacityMb={session.scenario?.satellite.storage_capacity_mb ?? null}
        requestCount={session.scenario === null ? null : session.requestPool.length}
      />
      <TimelinePanel
        className="col-span-3"
        scenario={session.scenario}
        plan={session.plan}
        replanResult={replanResult}
        missionState={session.missionState}
        windows={session.windows}
        events={session.events}
        impact={session.impact}
        selectedRequestId={selection.requestId}
        selectedWindowId={selection.windowId}
        selectedEventId={selection.eventId}
        onSelectRequest={session.selectRequest}
        onSelectWindow={session.selectWindow}
        onSelectEvent={session.selectEvent}
      />
      <div className="col-span-3 grid min-h-0 grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,1fr)] gap-1">
        <ImpactPanel
          impact={session.impact}
          events={session.events}
          plans={plans}
          earlier={!transition.stages.some((stage) => stage.kind === "impact")}
          selectedRequestId={selection.requestId}
          selectedWindowId={selection.windowId}
          selectedEventId={selection.eventId}
          onSelectRequest={session.selectRequest}
          onSelectWindow={session.selectWindow}
          onSelectEvent={session.selectEvent}
        />
        <PlanComparisonPanel
          replanResult={replanResult}
          currentPlan={session.plan}
          loading={session.loading}
          onRetryComparison={session.retryComparison}
          plans={plans}
          selectedRequestId={selection.requestId}
          selectedEventId={selection.eventId}
          onSelectRequest={session.selectRequest}
          onSelectWindow={session.selectWindow}
          onSelectEvent={session.selectEvent}
        />
        <MetricsPanel
          currentPlanId={session.plan?.id ?? null}
          metrics={session.metrics}
          diff={replanResult?.diff ?? null}
          plans={plans}
          selectedPlanId={selection.planId}
        />
      </div>
    </main>
  );
}

function App() {
  const session = useMissionSession();
  const transition = missionTransition({
    scenario: session.scenario,
    plan: session.plan,
    impact: session.impact,
    events: session.events,
    replanResult: session.replanResult,
    operation: session.operation,
  });
  // The bar names a previous version only while the strip still shows that replan.
  const previousStage = transition.stages.find(
    (stage) => stage.kind === "plan" && stage.role === "previous",
  );
  const previousVersion = previousStage?.kind === "plan" ? previousStage.version : null;

  return (
    <div className="flex h-dvh min-h-[640px] min-w-[900px] flex-col overflow-hidden">
      <MissionBar
        scenario={session.scenario}
        plan={session.plan}
        previousVersion={previousVersion}
        awaitingReplan={transition.phase === "awaiting-replan"}
        missionState={session.missionState}
        windows={session.windows}
        events={session.events}
        loading={session.loading}
        replanning={session.operation === "replan"}
        replanBlocked={session.stalePlan}
        missionContextStale={session.stalePlan}
        onLoadDemo={session.loadDemoScenario}
        onGeneratePlan={session.generatePlan}
        onStep={session.step}
        onInjectEvent={session.injectEvent}
        onReplan={session.replan}
      />
      <MissionTransitionStrip transition={transition} hasScenario={session.scenario !== null} />
      <MissionFocus session={session} />
      <PlanConflictBanner
        conflict={session.planConflict}
        plan={session.plan}
        onDismiss={session.dismissPlanConflict}
        onRetryMissionRefresh={session.retryMissionRefresh}
      />
      <ErrorBanner error={session.error} onDismiss={session.dismissError} />
      <MissionWorkspace session={session} transition={transition} />
    </div>
  );
}

export default App;
