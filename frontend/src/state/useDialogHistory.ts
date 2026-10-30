import { useEffect, useRef, useState } from "react";

export type MissionView = "settings" | "builder" | "load" | "examples" | "feasibility" | null;
type Entry = { owner: string; path: Exclude<MissionView, null>[]; generation: number };
const key = "amisDialog";

/** Only dialog entries are pushed; the dashboard keeps its ordinary Back behavior. */
export function useDialogHistory() {
  const owner = useRef(crypto.randomUUID());
  const generation = useRef(0);
  const path = useRef<Exclude<MissionView, null>[]>([]);
  const pending = useRef(false);
  const [view, setView] = useState<MissionView>(null);
  useEffect(() => {
    const onPop = (event: PopStateEvent) => {
      const entry = event.state?.[key] as Entry | undefined;
      path.current = entry?.owner === owner.current && entry.generation === generation.current ? entry.path : [];
      pending.current = false;
      setView(path.current.at(-1) ?? null);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  function open(next: Exclude<MissionView, null>) {
    if (pending.current || path.current.at(-1) === next) return;
    path.current = [...path.current, next];
    window.history.pushState({ ...window.history.state, [key]: { owner: owner.current, path: path.current, generation: generation.current } }, "");
    setView(next);
  }
  function close() {
    if (pending.current || path.current.length === 0) return;
    pending.current = true;
    window.history.back();
  }
  function complete() {
    if (pending.current) return;
    const depth = path.current.length;
    generation.current += 1; // Forward must never resurrect a submitted form.
    path.current = [];
    setView(null);
    if (depth) {
      pending.current = true;
      window.history.go(-depth);
    }
  }
  return { view, open, close, complete };
}
