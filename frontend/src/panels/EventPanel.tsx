import { useMemo, useState } from "react";
import type {
  ImpactSchema,
  MissionPlanSchema,
  ObservationWindowSchema,
  ScenarioSchema,
} from "../api/client";
import { PanelFrame } from "./PanelFrame";

function actionSummary(
  plan: MissionPlanSchema | null,
  actionId: string,
): { requestId: string; start: string; end: string } | null {
  const action = plan?.actions.find((candidate) => candidate.id === actionId);
  if (action === undefined) {
    return null;
  }
  return { requestId: action.request_id, start: action.start, end: action.end };
}

function ImpactReport({
  impact,
  plan,
}: {
  impact: ImpactSchema;
  plan: MissionPlanSchema | null;
}) {
  return (
    <div className="flex flex-col gap-2 text-sm">
      <h3 className="text-xs uppercase tracking-widest text-neutral-500">Impact</h3>
      {impact.invalid_unfrozen_action_ids.length === 0 ? (
        <p className="text-emerald-400">No scheduled actions became invalid.</p>
      ) : (
        <ul className="space-y-1">
          {impact.invalid_unfrozen_action_ids.map((actionId) => {
            const summary = actionSummary(plan, actionId);
            const reasons = impact.reason_codes[actionId] ?? [];
            return (
              <li key={actionId} className="text-red-300">
                {summary?.requestId ?? actionId}: {reasons.join(", ") || "invalidated"}
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-neutral-500">
        {impact.frozen_action_ids.length} frozen, {impact.valid_unfrozen_action_ids.length}{" "}
        still valid.
      </p>
    </div>
  );
}

export function EventPanel({
  scenario,
  plan,
  windows,
  impact,
  loading,
  onInjectCloudBlock,
}: {
  scenario: ScenarioSchema | null;
  plan: MissionPlanSchema | null;
  windows: ObservationWindowSchema[];
  impact: ImpactSchema | null;
  loading: boolean;
  onInjectCloudBlock: (requestId: string, windowId: string) => void;
}) {
  const [requestId, setRequestId] = useState("");
  const [windowId, setWindowId] = useState("");

  const windowsForRequest = useMemo(
    () => windows.filter((window) => window.request_id === requestId),
    [windows, requestId],
  );

  if (scenario === null) {
    return (
      <PanelFrame title="Cloud block event">
        <p className="text-sm text-neutral-500">Load a scenario to inject events.</p>
      </PanelFrame>
    );
  }

  return (
    <PanelFrame title="Cloud block event">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Request"
          value={requestId}
          onChange={(event) => {
            setRequestId(event.target.value);
            setWindowId("");
          }}
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200"
        >
          <option value="">Select request</option>
          {scenario.requests.map((request) => (
            <option key={request.id} value={request.id}>
              {request.id}
            </option>
          ))}
        </select>
        <select
          aria-label="Window"
          value={windowId}
          onChange={(event) => setWindowId(event.target.value)}
          disabled={requestId === ""}
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200 disabled:opacity-40"
        >
          <option value="">Select window</option>
          {windowsForRequest.map((window) => (
            <option key={window.id} value={window.id}>
              {window.id} ({window.start}–{window.end}
              {window.valid ? "" : ", invalid"})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => onInjectCloudBlock(requestId, windowId)}
          disabled={loading || requestId === "" || windowId === ""}
          className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
        >
          Inject cloud block
        </button>
      </div>
      {impact !== null && <ImpactReport impact={impact} plan={plan} />}
    </PanelFrame>
  );
}
