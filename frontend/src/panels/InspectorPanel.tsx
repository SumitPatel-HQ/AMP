import { useContext, useRef, useState, type ReactNode } from "react";
import { Maximize2, X } from "lucide-react";

import { Presentation } from "./panelPresentation";

/** Shares the existing panel tree and session callbacks; never owns mission data. */
export function InspectorPanel({ title, children, expandable = true }: { title: string; children: ReactNode; expandable?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const origin = useRef<HTMLElement | null>(null);
  const [open, setOpen] = useState(false);
  const scroll = useRef<{ element: HTMLElement; top: number } | null>(null);
  const expand = () => {
    origin.current = document.activeElement as HTMLElement;
    const inspector = origin.current?.closest<HTMLElement>(".amis-inspector");
    scroll.current = inspector ? { element: inspector, top: inspector.scrollTop } : null;
    setOpen(true);
    dialog.current?.showModal();
  };
  return <>
    <div className="amis-inspector-panel" data-presentation="compact">
      <Presentation value={{ mode: "compact", expand: expandable ? expand : undefined }}>{children}</Presentation>
    </div>
    <dialog ref={dialog} aria-label={`${title} full view`} className="amis-expanded-dialog"
      onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}
      onClose={() => { setOpen(false); origin.current?.focus({ preventScroll: true }); if (scroll.current) scroll.current.element.scrollTop = scroll.current.top; }}>
      <header className="amis-expanded-header"><h2>{title}</h2>
        <button type="button" autoFocus aria-label={`Close ${title} full view`} className="amis-settings-close" onClick={() => dialog.current?.close()}><X size={18} /></button>
      </header>
      <div className="amis-expanded-content" data-presentation="expanded">
        {open && <Presentation value={{ mode: "expanded" }}>{children}</Presentation>}
      </div>
    </dialog>
  </>;
}

export function PanelExpandAction() {
  const { expand } = useContext(Presentation);
  return expand ? <button type="button" className="amis-settings-close" aria-label="Expand panel" title="Expand panel" onClick={expand}><Maximize2 size={15} /></button> : null;
}
