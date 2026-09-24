import { useMissionSession } from "./state/useMissionSession";
import { ErrorBanner } from "./panels/ErrorBanner";
import { ImpactPanel } from "./panels/ImpactPanel";
import { MetricsPanel } from "./panels/MetricsPanel";
import { MissionBar } from "./panels/MissionBar";
import { MissionMapPanel } from "./panels/MissionMapPanel";
import { MissionNavPanel } from "./panels/MissionNavPanel";
import { StatePanel } from "./panels/StatePanel";
import { TimelinePanel } from "./panels/TimelinePanel";
import { TracePanel } from "./panels/TracePanel";

type Session = ReturnType<typeof useMissionSession>;

/**
 * The mission workspace, one viewport tall. Mission objects to the left, the
 * map at the centre and live state to the right; the timeline spans the full
 * width beneath them, and the analysis of the last replan sits at the bottom.
 * Each region scrolls on its own so none of them pushes the others off screen.
 */
function MissionWorkspace({ session }: { session: Session }) {
  const { selection } = session;
  return (
    <main className="grid min-h-0 flex-1 grid-cols-[minmax(230px,17rem)_minmax(0,1fr)_minmax(210px,15rem)] grid-rows-[minmax(280px,1fr)_minmax(190px,30%)_minmax(160px,24%)] gap-1 p-1">
      <MissionNavPanel
        scenario={session.scenario}
        plan={session.plan}
        replanResult={session.replanResult}
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
        satelliteCapacityWh={session.scenario?.satellite.battery_capacity_wh ?? null}
        storageCapacityMb={session.scenario?.satellite.storage_capacity_mb ?? null}
        requestCount={session.scenario?.requests.length ?? null}
      />
      <TimelinePanel
        className="col-span-3"
        scenario={session.scenario}
        plan={session.plan}
        replanResult={session.replanResult}
        missionState={session.missionState}
        selectedRequestId={selection.requestId}
        onSelectRequest={session.selectRequest}
      />
      <div className="col-span-3 grid min-h-0 grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_minmax(0,1fr)] gap-1">
        <ImpactPanel impact={session.impact} plan={session.plan} />
        <TracePanel
          traces={session.replanResult?.traces ?? []}
          selectedRequestId={selection.requestId}
          onSelectRequest={session.selectRequest}
        />
        <MetricsPanel diff={session.replanResult?.diff ?? null} />
      </div>
    </main>
  );
}

function App() {
  const session = useMissionSession();

  return (
    <div className="flex h-screen min-h-[720px] min-w-[1100px] flex-col">
      <MissionBar
        scenario={session.scenario}
        plan={session.plan}
        missionState={session.missionState}
        windows={session.windows}
        loading={session.loading}
        onLoadDemo={session.loadDemoScenario}
        onGeneratePlan={session.generatePlan}
        onStep={session.step}
        onInjectCloudBlock={session.injectCloudBlock}
        onReplan={session.replan}
      />
      <ErrorBanner error={session.error} onDismiss={session.dismissError} />
      <MissionWorkspace session={session} />
    </div>
  );
}

export default App;
