import { PanelExpandAction } from "./InspectorPanel";
import { usePanelPresentation } from "./panelPresentation";
import { Activity, ChartNoAxesCombined, GitCompareArrows, Globe2, ListChecks, TriangleAlert, Rows3, type LucideIcon } from "lucide-react";
import { useId, type ReactNode } from "react";

const PANEL_ICONS: Record<string, LucideIcon> = {
  Mission: ListChecks,
  "Mission map": Globe2,
  "Mission state": Activity,
  "Mission timeline": Rows3,
  Impact: TriangleAlert,
  "Plan comparison": GitCompareArrows,
  "Mission evaluation": ChartNoAxesCombined,
};

/**
 * One region of the mission workspace: a thin title bar over a body that
 * scrolls on its own, so a long list never pushes the regions around it.
 */
export function PanelFrame({
  title,
  meta,
  actions,
  className = "",
  bodyClassName = "p-2",
  children,
}: {
  title: string;
  /** Short context beside the title, such as a count or plan version. */
  meta?: ReactNode;
  /** Right-aligned header content, such as a legend or a view switch. */
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  const titleId = useId();
  const presentation = usePanelPresentation();
  const Icon = PANEL_ICONS[title];
  return (
    <section
      aria-labelledby={titleId}
      data-presentation={presentation.mode}
      className={`amis-panel flex min-h-0 min-w-0 flex-col border border-[var(--amis-border)] bg-[var(--amis-surface)] ${className}`}
    >
      <div className="amis-panel-header flex min-h-10 shrink-0 items-center gap-2 border-b border-[var(--amis-border)] bg-white/[0.02] px-2">
        <h2
          id={titleId}
          className="inline-flex shrink-0 items-center gap-2 truncate text-sm font-semibold text-neutral-200"
        >
          {Icon && <Icon size={15} aria-hidden="true" className="shrink-0 text-neutral-400" />}
          {title}
        </h2>
        {meta === undefined ? null : (
          <span className="min-w-0 truncate text-xs text-neutral-400">{meta}</span>
        )}
        <div className="ml-auto flex shrink-0 items-center">{actions}<PanelExpandAction /></div>
      </div>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}
