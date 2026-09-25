# Prompt 5 — Plan Comparison + Decision Trace / Explainability

Extracted from `AMIS_REDESIGN_CONTEXT.md`. This file is authoritative for Prompt 5 implementation.

These are combined because they answer one question together: **What changed, and why did AMIS change it?** Implementing them separately would create duplicate selection and layout work.

Preserve Prompts 1–4, especially the Prompt 3 `vis-timeline` mission timeline, the Prompt 2 map behavior, the shared selection model, and the Impact vs Plan Diff distinction defined in `./AMIS_PROMPT_4_EVENT_IMPACT_REPLAN.md`.

## Primary source

AMIS plan-diff and DecisionTrace backend data.

## Reference

Open MCT for inspection/detail interaction patterns only. Do not adopt unrelated architecture.

## Implement

- create a focused Plan Vn ↔ Vn+1 comparison surface associated with the Prompt 3 `vis-timeline` rather than an isolated generic card;
- represent backend diff statuses such as UNCHANGED, MOVED, INSERTED, DROPPED and COMPLETED exactly according to available API/domain data;
- show old/new placement details where relevant;
- pair each changed request/action with its actual DecisionTrace/reason data when available;
- selecting a diff row should highlight the corresponding `vis-timeline` item/group and, when applicable, map target/request;
- selecting a trace should highlight the mission object/change it explains;
- make reason codes readable with concise labels, but preserve the canonical code and do not invent causal explanations;
- distinguish planning/replanning traces from expiry traces where relevant;
- keep unchanged items visually quieter so changed items dominate analysis.

## Do not

- calculate an alternative diff client-side when backend comparison exists;
- use LLM-generated explanations;
- imply a trace explains a change if the backend does not link/support it;
- hide dropped/unscheduled requests just because they have no timeline range;
- reimplement Prompt 4 Impact UI; keep Impact (what became invalid) separate from Plan Diff (what changed after replanning).

## Acceptance criteria

After a replan, a reviewer can select a changed request and immediately determine its previous state, new state, change classification and backend-supported reason.
