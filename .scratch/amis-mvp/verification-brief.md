# AMIS MVP — Verification Brief

Copy-paste prompt for a verification agent:

> Verify AMIS MVP implementation against all 15 tickets below. For each checkbox report PASS/FAIL with `file_path:line_number` evidence. Do not infer — read code, run tests if needed. Use vocabulary in `CONTEXT.md`. Flag any use of banned terms.

## Global invariants

- Domain terms exactly as `CONTEXT.md`: Scenario, Satellite, ObservationRequest (no start time), RequestPool, Expired, ObservationWindow (validity flag + reason), ScheduledAction, MissionPlan (immutable, versioned, parent link), Planner/GreedyPlanner, Violation (reason code + request id), MissionState, MissionEvent, Frozen (start <= now), Replan, Impact, ReasonCode, DecisionTrace, PlanDiff, mission utility, plan churn, explanation coverage.
- Word "task" never appears as domain term/type/field/comment. Exception: Ticket 08 event wire name only, docs must say "request".
- No `infeasible plan` error code anywhere. Only 6 API error codes incl. `simulation state` and `plan version conflict`.
- ADR-0001: single test seam = session facade, no HTTP in domain tests. Routes are adapters only — no scheduling/validation/comparison/explanation in handlers. Planner imports no web/ORM/UI. No ORM object reaches planner.
- ADR-0002: Scenario object unchanged after event injection. Reload scenario + replay event log in order = identical mission.
- ADR-0003: Validation covers unfrozen actions only. Frozen unaffordable action never invalidates plan.
- Determinism: same scenario + same steps = identical state/plan. Generated IDs sequential per scenario, recovered from persisted records, not memory.
- No LLM imported anywhere. Trace sentences render from templates keyed by ReasonCode.

## 01 Walking skeleton

- [ ] Domain types exist for all 6 core types, CONTEXT.md names
- [ ] Scenario JSON round-trip lossless
- [ ] Session facade: load scenario, generate windows, plan; returns domain objects
- [ ] Synthetic window provider satisfies window-provider protocol (orbital-swappable without touching planner)
- [ ] GreedyPlanner satisfies planner protocol (scenario, state, requests, windows -> plan)
- [ ] Window containment returns structured Violation (reason code + request id), never bool
- [ ] Demo prints 1-action plan; integration test drives full path via facade, no HTTP

## 02 Constraint engine + multi-request

- [ ] 6 independently-callable checks: window containment, deadline, overlap, projected battery, projected storage, satellite availability; all return Violations with code + id
- [ ] 1 passing + 1 failing unit test per check
- [ ] Resources projected forward in time order; validated at action's own start time. No recharge, idle drain 0, storage never frees, floor at 0
- [ ] 5x20Wh actions rejected when only 25Wh remains (not all pass)
- [ ] Planner sort: priority desc, deadline asc, duration asc, request id asc
- [ ] Plan records every unscheduled request + reason code; empty plan + reasons (no error) when nothing fits
- [ ] `validate_plan` returns all violations in one call; 2 runs identical; availability check tested via hand-built unavailable state; demo prints multi-request plan + unscheduled list

## 03 Clock / accounting / expiry / lifecycle

- [ ] `step(seconds)` advances clock; actions become started then completed; battery drains / storage fills on execution
- [ ] MissionState is value snapshot: clock, battery, storage, availability, active event ids, completed request ids, mission-complete flag (not mutable shared object)
- [ ] Deadline passed + no completed action = Expired, permanent, excluded from all later planning, visible via request's own status
- [ ] Step crossing scenario end clamps at end + marks complete; further step raises simulation-state error
- [ ] Reset returns to load moment, clearing clock, resources, plans, events, traces, impacts; same scenario + steps = identical final state; demo prints state transitions

## 04 Metrics

- [ ] Utility = sum priorities over deduplicated (scheduled ∪ completed) set
- [ ] Computes: completion rate, violation count, planning time ms, battery/storage utilisation vs capacity
- [ ] Expired stay in RequestPool and count against completion rate
- [ ] Every result carries pool (size + id set); churn/coverage fields exist but null here; plain serialisable object, no UI; demo prints metrics

## 05 Cloud block + Impact

- [ ] Inject names request + one of its windows, marks window invalid + reason; records MissionEvent (id, scenario id, type, time, payload); never triggers replan; scenario unchanged
- [ ] Impact written at injection time: event id, evaluated plan id, frozen ids, valid-unfrozen ids, invalid-unfrozen ids + reason codes; later reads return stored record (no recompute)
- [ ] Frozen = start <= now (incl. in-flight started-before-event); Impact splits unfrozen only into valid/invalid (no 3rd class); only blocked-window action invalid; demo prints broken action + code

## 06 Replan / diff / trace / replanning metrics

- [ ] Replan: frozen actions identical in new version; rebuild unfrozen from all unexpired unfrozen requests incl. previously dropped; candidate windows sorted: previous window first if still valid, rest by earliest start
- [ ] New immutable version names parent, old unmutated
- [ ] Diff keyed by request id (reorder-proof), works any two versions; classes: unchanged/moved/inserted/dropped/completed, with old/new starts on move + reason code on every entry
- [ ] Every moved/inserted/dropped has trace: fixed-vocab ReasonCode, triggering event, broken constraint, previous action, new action; template-rendered sentences
- [ ] Replan time separate from initial plan time; churn = changed-unfrozen / earlier-unfrozen; coverage = changed-with-trace / changed; both null on zero denominator
- [ ] Canonical demo: v1 10:20 -> v2 11:15, window-invalidated reason, coverage 1.0, churn ~0; no-fit -> dropped with `no alternative window`; replan with no event = identical new version, churn 0, all unchanged; 2 runs identical JSON after stripping timestamps/timings

## 07 Battery drop

- [ ] Inject names satellite + new battery value, sets state exactly (no clamping); writes Impact naming evaluated plan
- [ ] Frozen in-flight unaffordable action still completes, battery floors at 0; validation does not fail on it
- [ ] Unfrozen unaffordable -> invalid with `insufficient battery`; replan always produces plan (possibly empty) + reason per unscheduled, never error; fixture exists where tight battery drops exactly lowest-priority request with that reason

## 08 Emergency request

- [ ] Payload carries complete ObservationRequest + explicit windows; window provider NOT called; scenario unchanged; RequestPool = scenario requests + all event-introduced requests; reload + replay log reproduces mission
- [ ] Replan considers new request, may displace existing; displaced gets trace `displaced by competing request`; priority-5 ties win on deadline tiebreak, not priority
- [ ] Metrics for 2 versions carry different pool sizes; comparison flags pool mismatch (not straight utility improvement); fixture where priority-5 displaces ≥1 request

## 09 REST API (cloud-block only, generic dispatch)

- [ ] Endpoints: create/read scenario, generate windows, plan, read state, step, inject event, read impact, replan, read plan, read metrics, compare plans, read traces
- [ ] Handlers validate input, call facade, return schema only; stateless (rebuild session from repos each request, write back)
- [ ] Order enforced: windows→plan→step, plan→inject, else simulation-state error
- [ ] Replan carries believed current version; mismatch -> conflict + `plan version conflict` code (double-click safe)
- [ ] Error envelope {code, message, details}, 6 codes; full flow integration-tested over ASGI; OpenAPI schema documents all error codes = source of truth for frontend types; events endpoint generic on type (07/08 need no route change)

## 10 Postgres + compose

- [ ] SQLAlchemy repos implement same protocols as in-memory; no caller above boundary changes
- [ ] Migrations cover: scenarios, satellites, requests, windows, states, plans, actions, events, impacts, traces, experiment results
- [ ] ID counters recover from persisted records; after restart v1/event/v2/impact/traces retrievable; Postgres + DB URL added in this change; no API key required; core workflow offline

## 11 Dashboard shell / load / timeline / state

- [ ] Single screen, independently-mounting panels over shared layout; load demo + generate plan from browser
- [ ] Timeline draws ScheduledActions; state panel: sim time, battery, storage, active event; types derived from OpenAPI (not handwritten); refetch on user action only, never poll
- [ ] Dense dark theme, colour = state/change only; API errors as readable messages + codes; no code/stylesheet/asset from World Monitor (AGPL-3.0-only)

## 12 Event panel + stepping

- [ ] Step from browser, state panel updates; cloud target via request dropdown -> window dropdown populated from that request; never hand-type window id
- [ ] Impact shown after inject (invalid + reasons); inject does NOT replan and UI doesn't imply it; mission-complete + rejected post-end step shown as readable messages

## 13 Replan / stacked timelines / comparison

- [ ] Replan from browser sends displayed version (stale-view safe); v1/v2 stacked vertically; changed requests marked on revised; frozen drawn distinctly from unfrozen
- [ ] Each timeline has unscheduled list beneath (request id, priority, reason code); unscheduled never drawn on timeline; version-conflict shown as readable message

## 14 Trace / metrics / linking

- [ ] Trace panel: each change + code + sentence, chronological; metrics panel side-by-side v1 vs v2; pool size beside every pool-dependent metric; pool-mismatch flagged; null churn/coverage = "N/A" never 0/perfect
- [ ] Click trace -> highlight request on both timelines; full demo completable browser-only; one command starts whole stack

## 15 Map (independent, first to cut)

- [ ] 2D map shows targets + satellite; select request <-> highlight target (both directions); separate panel (removal breaks nothing/test); lightweight 2D lib, no 3D/Cesium; never blocks/gates planning loop
