import { useEffect, useRef, useState } from "react";
import { BookOpen, FolderOpen, Search, X } from "lucide-react";
import { fetchExamples, fetchMissions } from "../api/amis";
import type { ScenarioSummarySchema } from "../api/client";

export function MissionLibrary({ mode, onClose, onChoose, error: loadError }: {
  mode: "load" | "examples";
  onClose: () => void;
  onChoose: (id: string) => Promise<boolean>;
  error?: string | null;
}) {
  const openerRef = useRef(document.activeElement);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [items, setItems] = useState<ScenarioSummarySchema[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const opener = openerRef.current;
    const dialog = dialogRef.current!;
    const parent = document.getElementById("mission-settings");
    const matchParentSize = () => {
      if (!parent) return;
      const bounds = parent.getBoundingClientRect();
      dialog.style.setProperty("--library-parent-height", `${bounds.height}px`);
      dialog.style.setProperty("--library-parent-width", `${bounds.width}px`);
    };
    matchParentSize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(matchParentSize);
    if (parent) observer?.observe(parent);
    dialog.showModal();
    return () => {
      observer?.disconnect();
      dialog.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);
  useEffect(() => {
    let active = true;
    (mode === "load" ? fetchMissions() : fetchExamples())
      .then(result => { if (active) setItems(result); })
      .catch((cause: unknown) => { if (active) setError(String(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [mode, retry]);
  const title = mode === "load" ? "Load mission" : "Browse examples";
  const Icon = mode === "load" ? FolderOpen : BookOpen;
  const filtered = items.filter(item => [item.name, item.id, item.provider, item.briefing, item.start_time, item.end_time].join(" ").toLowerCase().includes(query.trim().toLowerCase()));
  async function choose(id: string) {
    if (busy) return;
    setSelected(id);
    setBusy(true);
    setError(null);
    try { await onChoose(id); }
    catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialogRef} className="amis-settings-modal amis-library-modal" aria-labelledby="library-title" aria-describedby="library-subtitle" onCancel={event => { event.preventDefault(); event.stopPropagation(); onClose(); }} onClick={event => {
    if (event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
  }}>
    <div className="amis-settings-header">
      <div><h2 id="library-title">{title}</h2><p id="library-subtitle">{mode === "load" ? "Continue a saved mission. Use the mission ID to distinguish similar names." : "Explore a scenario and load it into your workspace."}</p></div>
      <button type="button" className="amis-settings-close" aria-label={`Close ${title}`} onClick={onClose}><X size={20} aria-hidden="true" /></button>
    </div>
    <label className="amis-library-search"><Search size={18} aria-hidden="true" /><input autoFocus type="search" aria-label="Search scenarios" placeholder="Search by name, provider or mission ID…" value={query} onChange={event => setQuery(event.target.value)} /></label>
    {(error || loadError) && <div role="alert" className="amis-library-error">{error || loadError}{error && !busy && <button type="button" onClick={() => { setLoading(true); setError(null); setRetry(value => value + 1); }}>Retry list</button>}</div>}
    <div className="amis-library-content" aria-busy={loading || busy}>
      {loading ? <p role="status">Loading {mode === "load" ? "missions" : "examples"}…</p> : filtered.length === 0 ? <p role="status">{query ? "No scenarios match your search." : error ? "Unable to retrieve scenarios." : mode === "load" ? "No saved missions yet." : "No examples available."}</p> :
      <ul className="amis-library-list">{filtered.map(item => <li key={item.id} className={`amis-library-card${selected === item.id ? " amis-library-selected" : ""}`}>
        <button type="button" className="amis-library-choice" disabled={busy} aria-label={`Load ${item.name} (${item.id})`} onClick={() => void choose(item.id)}>
          <span className="amis-settings-card-icon"><Icon size={20} aria-hidden="true" /></span>
          <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{item.name}</span><span className="amis-library-meta">{item.provider} · {item.start_time.slice(0, 10)} – {item.end_time.slice(0, 10)} UTC</span><span className="amis-library-id" title={item.id}>{item.id}</span>{item.briefing && <span className="amis-library-preview">{item.briefing}</span>}{busy && selected === item.id && <span role="status">Loading mission…</span>}</span>
        </button>
        {item.briefing && <details className="amis-library-details"><summary>Full briefing</summary><div>{item.briefing}</div></details>}
      </li>)}</ul>}
    </div>
    <footer className="amis-library-footer"><span>{!loading && `${filtered.length} ${filtered.length === 1 ? "scenario" : "scenarios"}`}</span><button type="button" onClick={onClose}>Cancel</button></footer>
  </dialog>;
}
