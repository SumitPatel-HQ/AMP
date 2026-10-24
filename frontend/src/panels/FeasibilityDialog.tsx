import { useRef, useState } from "react";
import { ApiError, fetchFeasibility } from "../api/amis";
import type { FeasibilitySchema, ScenarioSchema } from "../api/client";
import {
  FEASIBILITY_EXCLUDES,
  FEASIBILITY_INCLUDES,
  FEASIBILITY_PROMISE,
  FEASIBILITY_STATE_LABEL,
  feasibilityQuery,
  rowStateForSatellite,
  resultForScenario,
  toUtcInput,
  type FeasibilityForm,
  type FeasibilityRowState,
} from "../state/feasibility";
import type { MissionSessionError } from "../state/types";
import { CONTROL_BUTTON, CONTROL_INPUT } from "./controls";
import { ErrorBanner } from "./ErrorBanner";

const STATE_STYLE: Record<FeasibilityRowState, string> = {
  earliest: "text-emerald-300",
  suitable: "text-neutral-300",
  no_suitable_window: "text-amber-300",
  satellite_unavailable: "text-red-300",
};

/**
 * Every satellite id the Scenario carries. The backend sends the canonical
 * Wave 7 `satellites` list beside the legacy single `satellite`; the dashboard's
 * generated Scenario type predates the list, so it is read defensively here.
 */
function satelliteIds(scenario: ScenarioSchema): string[] {
  // Wave-7 payloads carry the canonical satellites list beside the legacy satellite.
  const listed = (scenario as ScenarioSchema & { satellites?: { id: string }[] | null }).satellites;
  return listed?.map((item) => item.id) ?? [scenario.satellite.id];
}

function formatTime(value: string | null): string {
  return value === null ? "—" : `${new Date(value).toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

function Results({ result }: { result: FeasibilitySchema }) {
  return (
    <div aria-label="Feasibility results" className="mt-3 space-y-2 text-xs">
      <p className="text-neutral-400">
        {`Candidate ${result.target_lat}, ${result.target_lon} · ${result.duration_s} s · deadline ${formatTime(result.deadline)}`}
        {result.satellite_id === null ? " · all satellites" : ` · ${result.satellite_id} only`}
      </p>
      <p aria-label="Time basis" className="text-neutral-400">
        {`Searched ${formatTime(result.search_start)} to ${formatTime(result.search_end)}: from the Scenario start, independent of the mission clock, to the earlier of Scenario end and deadline.`}
      </p>
      <p className="font-medium text-neutral-200">
        {result.earliest_satellite_id === null
          ? "No satellite has a suitable window."
          : `Earliest suitable satellite: ${result.earliest_satellite_id}`}
      </p>
      <table className="w-full border-collapse text-left">
        <thead className="text-[10px] uppercase tracking-wide text-neutral-500">
          <tr>
            <th className="py-1 pr-2 font-normal">Satellite</th>
            <th className="py-1 pr-2 font-normal">Result</th>
            <th className="py-1 pr-2 font-normal">Window</th>
            <th className="py-1 pr-2 font-normal">Earliest start</th>
            <th className="py-1 font-normal">Latest finish</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => {
            const state = rowStateForSatellite(row, result.earliest_satellite_id);
            return (
              <tr key={row.satellite_id} data-state={state} className="border-t border-neutral-800 align-top">
                <td className="py-1 pr-2 font-mono text-neutral-100">{row.satellite_id}</td>
                <td className={`py-1 pr-2 ${STATE_STYLE[state]}`}>{FEASIBILITY_STATE_LABEL[state]}</td>
                <td className="py-1 pr-2 text-neutral-300">
                  {row.window_id === null ? "—" : (
                    <>
                      <span className="block font-mono">{row.window_id}</span>
                      <span className="text-[10px] text-neutral-500">{`${formatTime(row.window_start)} – ${formatTime(row.window_end)}`}</span>
                    </>
                  )}
                </td>
                <td className="py-1 pr-2 tabular-nums text-neutral-200">{formatTime(row.earliest_start)}</td>
                <td className="py-1 tabular-nums text-neutral-200">{formatTime(row.latest_finish)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Window-only feasibility for a hypothetical candidate. The query is read-only
 * on the backend; this dialog has no submit or reserve action. Replacing any
 * Scenario input resets the form and results, including pending replies.
 */
export function FeasibilityDialog({
  scenario,
  onClose,
}: {
  scenario: ScenarioSchema;
  onClose: () => void;
}) {
  return <CandidateWindowComparison key={JSON.stringify(scenario)} scenario={scenario} onClose={onClose} />;
}

function CandidateWindowComparison({ scenario, onClose }: { scenario: ScenarioSchema; onClose: () => void }) {
  const [form, setForm] = useState<FeasibilityForm>(() => ({
    lat: "",
    lon: "",
    durationS: "",
    deadlineUtc: toUtcInput(scenario.end_time),
    satelliteId: "",
  }));
  const [result, setResult] = useState<FeasibilitySchema | null>(null);
  const [error, setError] = useState<MissionSessionError | null>(null);
  const [busy, setBusy] = useState(false);
  // Only the latest query may answer; an earlier one resolving late is dropped.
  const latest = useRef(0);
  const shown = resultForScenario(result, scenario.id);

  const updateField = (key: keyof FeasibilityForm) => (event: { target: { value: string } }) => {
    latest.current += 1;
    setBusy(false);
    setResult(null);
    setError(null);
    setForm((current) => ({ ...current, [key]: event.target.value }));
  };

  async function compare() {
    setResult(null);
    const query = feasibilityQuery(form);
    if (typeof query === "string") {
      setError({ code: "CLIENT_ERROR", message: query, details: {} });
      return;
    }
    const token = ++latest.current;
    setBusy(true);
    setError(null);
    try {
      const answer = await fetchFeasibility(scenario.id, query);
      if (token === latest.current) setResult(answer);
    } catch (caught) {
      if (token !== latest.current) return;
      setResult(null);
      setError(caught instanceof ApiError
        ? { code: caught.code, message: caught.message, details: caught.details }
        : { code: "CLIENT_ERROR", message: String(caught), details: {} });
    } finally {
      if (token === latest.current) setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/80 p-8" role="dialog" aria-label="Window-only feasibility">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded border border-neutral-700 bg-[#101318] p-4 text-neutral-100 shadow-2xl">
        <div className="mb-2 flex justify-between">
          <h2 className="font-semibold">Window-only feasibility</h2>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <p aria-label="Feasibility scope" className="mb-3 rounded-sm border border-amber-900 bg-amber-950/30 p-2 text-[11px] text-amber-100">
          {`Compares each satellite's earliest suitable observation window for ${scenario.name}. Accounts for ${FEASIBILITY_INCLUDES}. Excludes ${FEASIBILITY_EXCLUDES}. ${FEASIBILITY_PROMISE}`}
        </p>
        <form
          className="flex flex-wrap items-end gap-2 text-[10px] uppercase text-neutral-500"
          onSubmit={(event) => {
            event.preventDefault();
            void compare();
          }}
        >
          <label className="flex flex-col gap-0.5">Latitude
            <input aria-label="Latitude" type="number" step="any" value={form.lat} onChange={updateField("lat")} className={`${CONTROL_INPUT} w-24`} />
          </label>
          <label className="flex flex-col gap-0.5">Longitude
            <input aria-label="Longitude" type="number" step="any" value={form.lon} onChange={updateField("lon")} className={`${CONTROL_INPUT} w-24`} />
          </label>
          <label className="flex flex-col gap-0.5">Duration (s)
            <input aria-label="Duration (s)" type="number" step="any" value={form.durationS} onChange={updateField("durationS")} className={`${CONTROL_INPUT} w-20`} />
          </label>
          <label className="flex flex-col gap-0.5">Deadline (UTC)
            <input aria-label="Deadline (UTC)" type="datetime-local" step="1" value={form.deadlineUtc} onChange={updateField("deadlineUtc")} className={CONTROL_INPUT} />
          </label>
          <label className="flex flex-col gap-0.5">Satellite
            <select aria-label="Satellite" value={form.satelliteId} onChange={updateField("satelliteId")} className={CONTROL_INPUT}>
              <option value="">All satellites</option>
              {satelliteIds(scenario).map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={busy} className={CONTROL_BUTTON}>
            {busy ? "Comparing…" : "Compare windows"}
          </button>
        </form>
        {error === null ? null : (
          <div className="mt-3"><ErrorBanner error={error} onDismiss={() => setError(null)} /></div>
        )}
        {shown === null ? null : <Results result={shown} />}
      </div>
    </div>
  );
}
