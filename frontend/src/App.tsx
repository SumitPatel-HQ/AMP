import { useMissionSession } from "./state/useMissionSession";
import { missionTransition, type MissionTransition } from "./state/missionTransition";
import { knownPlans } from "./state/planContext";
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
  const plans = knownPlans(session.plan, replanResult);
  return (
    <main className="grid min-h-0 min-w-0 flex-1 grid-cols-[minmax(220px,18rem)_minmax(0,1fr)_minmax(240px,19rem)] grid-rows-[minmax(220px,1.1fr)_minmax(190px,1fr)_minmax(150px,0.8fr)] gap-1 p-1">
      <MissionNavPanel
        scenario={session.scenario}
        plan={session.plan}
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
          onSelectRequest={session.selectRequest}
        />
        <PlanComparisonPanel
          replanResult={replanResult}
          plans={plans}
          selectedRequestId={selection.requestId}
          onSelectRequest={session.selectRequest}
          onSelectWindow={session.selectWindow}
        />
        <MetricsPanel
          currentPlanId={session.plan?.id ?? null}
          metrics={session.metrics}
          diff={replanResult?.diff ?? null}
          plans={plans}
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
    <div className="flex h-dvh min-h-[680px] min-w-[1200px] flex-col overflow-hidden">
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
        onLoadDemo={session.loadDemoScenario}
        onGeneratePlan={session.generatePlan}
        onStep={session.step}
        onInjectEvent={session.injectEvent}
        onReplan={session.replan}
      />
      <MissionTransitionStrip transition={transition} hasScenario={session.scenario !== null} />
      <PlanConflictBanner
        conflict={session.planConflict}
        plan={session.plan}
        onDismiss={session.dismissPlanConflict}
      />
      <ErrorBanner error={session.error} onDismiss={session.dismissError} />
      <MissionWorkspace session={session} transition={transition} />
    </div>
  );
}

export default App;
