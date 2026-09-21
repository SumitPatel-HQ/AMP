import type { ReactNode } from "react";

export function PanelFrame({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded border border-neutral-800 bg-neutral-950 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
        {title}
      </h2>
      {children}
    </section>
  );
}
