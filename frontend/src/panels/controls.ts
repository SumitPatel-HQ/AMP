const CONTROL_SHAPE = "h-8 whitespace-nowrap rounded-md border px-2 text-xs disabled:opacity-40 disabled:cursor-not-allowed";

/** The compact bordered button every mission control shares. */
export const CONTROL_BUTTON = `${CONTROL_SHAPE} border-mission-control-border bg-neutral-900 text-neutral-200 hover:bg-neutral-800`;

/** Event injection: the disruption control, in the event colour. */
export const EVENT_BUTTON = `${CONTROL_SHAPE} border-amber-700/60 bg-neutral-900 text-amber-200 hover:bg-amber-950/60`;
export const EVENT_BUTTON_OPEN = `${CONTROL_SHAPE} border-amber-500/70 bg-amber-950/60 text-amber-100`;

/** Replan, promoted to the primary action while an impact awaits an answer. */
export const REPLAN_BUTTON = `${CONTROL_SHAPE} border-sky-800/60 bg-neutral-900 text-sky-200 hover:bg-sky-950/60`;
export const REPLAN_BUTTON_PRIMARY = `${CONTROL_SHAPE} border-sky-500/70 bg-sky-800/70 text-sky-50 hover:bg-sky-700/70`;

/** The matching select and number-input treatment. */
export const CONTROL_INPUT =
  "h-8 rounded-md border border-mission-control-border bg-neutral-900 px-1.5 text-xs text-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed";
