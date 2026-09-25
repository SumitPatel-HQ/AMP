# Prompt 6 — Mission Evaluation Metrics + Frontend/Backend Contract Audit + Proven Fixes

Extracted from `AMIS_REDESIGN_CONTEXT.md`. This file is authoritative for Prompt 6 implementation.

**Primary source:** AMIS metrics/domain/API.

This prompt intentionally combines metrics with the contract audit because, by this point, every major user workflow exists. The agent can now identify actual API gaps from implementation evidence rather than speculating. Backend changes are allowed here only when the audit proves they are needed.

Preserve Prompts 1–5, including the Prompt 3 `vis-timeline` timeline, Prompt 4 event→impact→replan workflow (`./AMIS_PROMPT_4_EVENT_IMPACT_REPLAN.md`), and Prompt 5 comparison/trace surface (`./AMIS_PROMPT_5_PLAN_COMPARISON_TRACE.md`).

## Part A - Metrics UX

- present utility, completion, violations, resource utilization, plan churn, explanation coverage and request-pool context compactly;
- associate metrics with the exact plan/version they describe;
- make before/after comparison understandable where both plans are available;
- respect `null` as N/A for empty denominators; never render N/A as 0%;
- visibly flag when compared metrics use different request pools;
- avoid decorative charts when a compact value/delta/status communicates the metric better;
- use Recharts only where a real chart adds information (never for the mission timeline — timeline is `vis-timeline` per Prompt 3).

## Part B - Contract audit

For each redesigned surface/workflow, produce an explicit matrix:

`UI requirement -> current frontend source -> API endpoint/DTO -> domain object -> persistence/source -> status (supported / awkward / missing)`

Audit at least:

- mission header/state;
- requests/windows;
- map;
- timeline (`vis-timeline`);
- events;
- persisted impact;
- replanning;
- plan comparison;
- decision traces;
- metrics.

## Part C - Targeted fixes

- fix only gaps demonstrated by the matrix;
- prefer a small read endpoint/DTO/projection over changing planner/domain behavior;
- keep MissionSession as facade;
- preserve scenario immutability/event-log semantics;
- preserve deterministic domain behavior;
- update generated OpenAPI TypeScript types after API changes;
- add/update backend and frontend tests for every contract change.

## Do not

- perform a general backend cleanup;
- replace the planner/replanner because the UI would prefer a different shape;
- add speculative APIs for future features;
- introduce database-shaped DTOs into React.

## Acceptance criteria

Metrics correctly describe specific plans; the audit is written down; every backend change maps to a demonstrated UI requirement; no unexplained architectural rewrite occurs; all relevant backend tests and frontend build/typecheck pass.
