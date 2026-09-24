/** HH:MM of an ISO instant, in UTC so every panel reads the same clock. */
export function clockTime(isoTime: string): string {
  return new Date(isoTime).toISOString().slice(11, 16);
}

/** A plan id without its scenario prefix, for headers too narrow for both. */
export function shortPlanId(planId: string): string {
  return planId.split(":").at(-1) ?? planId;
}
