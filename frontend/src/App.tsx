import { useMissionSession } from "./state/useMissionSession";
import { ErrorBanner } from "./panels/ErrorBanner";
import { ScenarioPanel } from "./panels/ScenarioPanel";
import { StatePanel } from "./panels/StatePanel";
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
      <div className="lg:col-span-3">
        <TimelinePanel scenario={session.scenario} plan={session.plan} />
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
