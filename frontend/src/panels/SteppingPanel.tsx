import { useState } from "react";
import type { MissionStateSchema } from "../api/client";
import { PanelFrame } from "./PanelFrame";

export function SteppingPanel({
  missionState,
  loading,
  onStep,
}: {
  missionState: MissionStateSchema | null;
  loading: boolean;
  onStep: (seconds: number) => void;
}) {
  const [seconds, setSeconds] = useState(300);

  return (
    <PanelFrame title="Stepping">
      {missionState === null ? (
        <p className="text-sm text-neutral-500">Load a scenario to step the simulation.</p>
      ) : (
        <>
          {missionState.mission_complete && (
            <p className="text-sm text-emerald-400">Mission complete.</p>
          )}
          <div className="flex items-center gap-2">
            <label className="text-sm text-neutral-500" htmlFor="step-seconds">
              seconds
            </label>
            <input
              id="step-seconds"
              type="number"
              min={1}
              step={1}
              value={seconds}
              onChange={(event) => setSeconds(Number(event.target.value))}
              className="w-24 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200"
            />
            <button
              type="button"
              onClick={() => onStep(seconds)}
              disabled={loading || !(seconds > 0)}
              className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
            >
              Step
            </button>
          </div>
        </>
      )}
    </PanelFrame>
  );
}
