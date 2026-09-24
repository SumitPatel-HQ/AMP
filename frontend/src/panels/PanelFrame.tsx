import type { ReactNode } from "react";

/**
 * One region of the mission workspace: a thin title bar over a body that
 * scrolls on its own, so a long list never pushes the regions around it.
 */
export function PanelFrame({
  title,
  meta,
  className = "",
  bodyClassName = "p-2",
  children,
}: {
  title: string;
  /** Short context beside the title, such as a count or plan version. */
  meta?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`flex min-h-0 min-w-0 flex-col border border-[var(--amis-border)] bg-[var(--amis-surface)] ${className}`}
    >
      <div className="flex h-7 shrink-0 items-center gap-2 border-b border-[var(--amis-border)] bg-white/[0.02] px-2.5">
        <h2 className="truncate text-[11px] font-semibold uppercase tracking-wider text-neutral-300">
          {title}
        </h2>
        {meta === undefined ? null : (
          <span className="truncate text-[10px] text-neutral-500">{meta}</span>
        )}
      </div>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}
