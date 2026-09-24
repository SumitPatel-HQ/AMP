import { useId, type ReactNode } from "react";

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
  return (
    <section
      aria-labelledby={titleId}
      className={`flex min-h-0 min-w-0 flex-col border border-[var(--amis-border)] bg-[var(--amis-surface)] ${className}`}
    >
      <div className="flex h-6 shrink-0 items-center gap-2 border-b border-[var(--amis-border)] bg-white/[0.02] px-2">
        <h2
          id={titleId}
          className="shrink-0 truncate text-[11px] font-semibold uppercase tracking-wider text-neutral-200"
        >
          {title}
        </h2>
        {meta === undefined ? null : (
          <span className="min-w-0 truncate text-[10px] text-neutral-500">{meta}</span>
        )}
        {actions === undefined ? null : <div className="ml-auto flex shrink-0 items-center">{actions}</div>}
      </div>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}
