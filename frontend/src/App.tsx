import { useMissionSession } from "./state/useMissionSession";
import { missionTransition, type MissionTransition } from "./state/missionTransition";
import { knownPlans, planLabel } from "./state/planContext";
import { ErrorBanner } from "./panels/ErrorBanner";
import { ImpactPanel } from "./panels/ImpactPanel";
import { MetricsPanel } from "./panels/MetricsPanel";
import { MissionBar } from "./panels/MissionBar";
import { MissionMapPanel } from "./panels/MissionMapPanel";
import { MissionNavPanel } from "./panels/MissionNavPanel";
import { MissionTransitionStrip } from "./panels/MissionTransitionStrip";
import { StatePanel } from "./panels/StatePanel";
import { TimelinePanel } from "./panels/TimelinePanel";
import { TracePanel } from "./panels/TracePanel";

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
  // The replan the trace and evaluation describe, named once for both panels.
  const replanContext =
    replanResult === null
      ? null
      : `${planLabel(replanResult.initialPlan.id, plans)} → ${planLabel(replanResult.revisedPlan.id, plans)}`;
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
        requestCount={session.scenario?.requests.length ?? null}
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
        />
        <TracePanel
          traces={replanResult?.traces ?? []}
          planContext={replanContext}
          selectedRequestId={selection.requestId}
          onSelectRequest={session.selectRequest}
        />
        <MetricsPanel diff={replanResult?.diff ?? null} plans={plans} />
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
        loading={session.loading}
        onLoadDemo={session.loadDemoScenario}
        onGeneratePlan={session.generatePlan}
        onStep={session.step}
        onInjectCloudBlock={session.injectCloudBlock}
        onReplan={session.replan}
      />
      <MissionTransitionStrip transition={transition} hasScenario={session.scenario !== null} />
      <ErrorBanner error={session.error} onDismiss={session.dismissError} />
      <MissionWorkspace session={session} transition={transition} />
    </div>
  );
}

export default App;
