import { useMissionSession } from "./state/useMissionSession";
import { ErrorBanner } from "./panels/ErrorBanner";
import { EventPanel } from "./panels/EventPanel";
import { MissionMapPanel } from "./panels/MissionMapPanel";
import { ScenarioPanel } from "./panels/ScenarioPanel";
import { StatePanel } from "./panels/StatePanel";
import { SteppingPanel } from "./panels/SteppingPanel";
import { TimelinePanel } from "./panels/TimelinePanel";

// Panels mount independently over this grid. Add, remove, or reorder an
// entry here without any other panel needing to change.
function DashboardPanels({ session }: { session: ReturnType<typeof useMissionSession> }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-1">
        <ScenarioPanel
          scenario={session.scenario}
          plan={session.plan}
          loading={session.loading}
          onLoadDemo={session.loadDemoScenario}
          onGeneratePlan={session.generatePlan}
        />
      </div>
      <div className="lg:col-span-1">
        <StatePanel
          state={session.missionState}
          events={session.events}
          satelliteCapacityWh={session.scenario?.satellite.battery_capacity_wh ?? null}
        />
      </div>
      <div className="lg:col-span-1">
        <SteppingPanel
          missionState={session.missionState}
          loading={session.loading}
          onStep={session.step}
        />
      </div>
      <div className="lg:col-span-3">
        <TimelinePanel
          scenario={session.scenario}
          plan={session.plan}
          replanResult={session.replanResult}
          missionState={session.missionState}
          selectedRequestId={session.selectedRequestId}
          loading={session.loading}
          onReplan={session.replan}
          onSelectRequest={session.selectRequest}
        />
      </div>
      <div className="lg:col-span-3">
        <MissionMapPanel
          scenario={session.scenario}
          plan={session.plan}
          missionState={session.missionState}
          selectedRequestId={session.selectedRequestId}
          onSelectRequest={session.selectRequest}
        />
      </div>
      <div className="lg:col-span-3">
        <EventPanel
          scenario={session.scenario}
          plan={session.plan}
          windows={session.windows}
          impact={session.impact}
          loading={session.loading}
          onInjectCloudBlock={session.injectCloudBlock}
        />
      </div>
    </div>
  );
}

function App() {
  const session = useMissionSession();

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-4 p-6">
      <header>
        <h1 className="text-lg font-semibold text-neutral-200">AMIS Mission Dashboard</h1>
      </header>
      <ErrorBanner error={session.error} onDismiss={session.dismissError} />
      <DashboardPanels session={session} />
    </div>
  );
}

export default App;
