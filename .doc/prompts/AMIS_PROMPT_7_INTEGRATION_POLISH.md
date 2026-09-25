# Prompt 7 — Cross-Surface Integration + UX/Visual Polish + Cleanup

Extracted from `AMIS_REDESIGN_CONTEXT.md`. This file is authoritative for Prompt 7 implementation.

**References:** use all three reference projects only for the areas assigned to them. AMIS remains authoritative.

This is not a redesign-from-scratch prompt. It is the integration pass after all primary workflows exist.

Preserve Prompts 1–6, including the Prompt 3 `vis-timeline` timeline, Prompt 4 event→impact→replan workflow (`./AMIS_PROMPT_4_EVENT_IMPACT_REPLAN.md`), Prompt 5 comparison/trace surface (`./AMIS_PROMPT_5_PLAN_COMPARISON_TRACE.md`), and Prompt 6 metrics/audit outcomes (`./AMIS_PROMPT_6_METRICS_CONTRACT_AUDIT.md`).

## Implement

- finish synchronized selection across requests/windows, map, timeline, events, plan comparison and traces;
- make hover/focus/highlight states consistent;
- ensure selected objects remain understandable when moving between panels;
- refine loading, empty, error, stale/conflict and completed-mission states;
- improve keyboard/focus behavior for primary controls where practical;
- refine responsive behavior for target desktop/laptop widths without sacrificing operational density;
- normalize spacing, typography, borders, panel chrome and status semantics into one coherent visual system;
- reduce decorative card styling and wasted whitespace;
- ensure the map and timeline remain the dominant operational surfaces;
- remove obsolete components/styles left by the old dashboard only after confirming they are unused;
- perform reasonable render/performance cleanup (avoid unnecessary refetch loops/re-renders; still no polling);
- verify the canonical cloud, battery and emergency workflows end-to-end through the UI.

## Final verification

- frontend build/typecheck passes;
- relevant frontend tests pass;
- backend regression tests pass if Prompt 6 changed APIs;
- no console-breaking errors in the canonical flow;
- all user actions use real backend data;
- final UI visually communicates the research story: **Plan -> Disruption -> Impact -> Adaptive Replan -> Explanation -> Evaluation**.
