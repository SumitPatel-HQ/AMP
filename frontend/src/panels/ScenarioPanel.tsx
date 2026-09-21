import type { MissionPlanSchema, ScenarioSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

export function ScenarioPanel({
  scenario,
  plan,
  loading,
  onLoadDemo,
  onGeneratePlan,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  loading: boolean;
  onLoadDemo: () => void;
  onGeneratePlan: () => void;
}) {
  return (
    <PanelFrame title="Scenario">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onLoadDemo}
          disabled={loading}
          className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
        >
          Load demo scenario
        </button>
        <button
          type="button"
          onClick={onGeneratePlan}
          disabled={loading || scenario === null}
          className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
        >
          Generate plan
        </button>
      </div>
      {scenario === null ? (
        <p className="text-sm text-neutral-500">No scenario loaded.</p>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-neutral-500">id</dt>
          <dd className="text-neutral-200">{scenario.id}</dd>
          <dt className="text-neutral-500">name</dt>
          <dd className="text-neutral-200">{scenario.name}</dd>
          <dt className="text-neutral-500">satellite</dt>
          <dd className="text-neutral-200">{scenario.satellite.id}</dd>
          <dt className="text-neutral-500">requests</dt>
          <dd className="text-neutral-200">{scenario.requests.length}</dd>
          <dt className="text-neutral-500">plan</dt>
          <dd className="text-neutral-200">
            {plan === null ? "not generated" : `v${plan.version} (${plan.actions.length} scheduled)`}
          </dd>
        </dl>
      )}
    </PanelFrame>
  );
}
