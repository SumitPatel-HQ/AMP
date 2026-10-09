import { useEffect, useState } from "react";
import { fetchExamples, fetchMissions } from "../api/amis";
import type { ScenarioSummarySchema } from "../api/client";

export function MissionLibrary({ mode, onClose, onChoose }: {
  mode: "load" | "examples";
  onClose: () => void;
  onChoose: (id: string) => Promise<void>;
}) {
  const [items, setItems] = useState<ScenarioSummarySchema[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    (mode === "load" ? fetchMissions() : fetchExamples()).then(setItems).catch((cause: unknown) => setError(String(cause)));
  }, [mode]);
  return <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/80 p-8" role="dialog" aria-label={mode === "load" ? "Load mission" : "Examples"}>
    <div className="w-full max-w-xl rounded border border-neutral-700 bg-[#101318] p-4 text-neutral-100 shadow-2xl">
      <div className="mb-4 flex justify-between"><h2 className="font-semibold">{mode === "load" ? "Load mission" : "Examples"}</h2><button onClick={onClose}>Close</button></div>
      {error && <p role="alert" className="text-red-400">{error}</p>}
      {items.length === 0 && !error && <p className="text-sm text-neutral-500">{mode === "load" ? "No saved missions yet." : "Loading examples…"}</p>}
      <ul className="max-h-[70vh] space-y-2 overflow-y-auto">{items.map((item) => <li key={item.id}>
        <button disabled={busy} className="w-full rounded border border-neutral-700 p-3 text-left hover:border-sky-700 disabled:opacity-50" onClick={async () => { setBusy(true); await onChoose(item.id); setBusy(false); onClose(); }}>
          <span className="block text-sm font-medium">{item.name}</span>
          <span className="text-xs text-neutral-500">{item.id} · {item.provider} · {new Date(item.start_time).toISOString().slice(0, 10)}–{new Date(item.end_time).toISOString().slice(0, 10)}</span>
          {item.briefing && <p className="mt-2 whitespace-pre-line text-xs text-neutral-400">{item.briefing}</p>}
        </button>
      </li>)}</ul>
    </div>
  </div>;
}
