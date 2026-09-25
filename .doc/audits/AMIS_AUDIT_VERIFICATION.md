# AMIS Full-System Audit — Independent Verification

Independent re-verification of `AMIS_FULL_SYSTEM_AUDIT.md` (GAP-01..GAP-12). Every
claim below was checked against the actual source at the cited locations,
reproduced with a runnable script or the live test suite where practical, and
cross-checked against `.doc/specs/AMIS_SRD.md` / other spec docs where the
audit invoked a requirement. Commands and outputs are trimmed for readability;
exact commands are listed in the final section.

---

## GAP-01 — Production wiring defaults to `SyntheticWindowProvider` (Critical, Integration)

**Verdict: CONFIRMED**

Evidence:
- `amis/main.py:20-28` (`build_app`) calls `create_app()` with no `window_provider`
  argument whenever `AMIS_DATABASE_URL` is unset, and even in the DB-backed
  branch only passes `build_repositories(engine)`, never a `window_provider`.
- `amis/api.py:71-94` (`create_app`) defaults `window_provider: WindowProvider | None = None`
  and forwards it unchanged into `MissionSessionStore`.
- `amis/repositories.py:298-303` (`MissionSessionStore._new_session`) passes
  `self.window_provider` (which is `None`) straight into `MissionSession(...)`.
- `amis/session.py:75` — `self._window_provider = window_provider or SyntheticWindowProvider()`.
- `amis/windows/synthetic.py:14-29` — `SyntheticWindowProvider` emits exactly
  one window per request, spanning `scenario.start_time` → `scenario.end_time`.

Live reproduction (`amis.session.MissionSession()` with default ctor, exactly
what `build_app()`/`create_app()` wire in production, against
`amis.demo.build_canonical_replan_scenario()` which is also what
`GET /demo/scenario` serves the frontend):

```
scheduled:   [('OBS-A', '2026-09-21T10:00:00+00:00', ...)]
unscheduled: [('OBS-B','TIME_OVERLAP'), ('OBS-C','TIME_OVERLAP'), ('OBS-D','TIME_OVERLAP'), ('OBS-E','TIME_OVERLAP')]
```

Only the highest-priority request is ever scheduled; every other request
collides at the identical start instant because every window spans the same
scenario range and (per GAP-04) the planner never tries a second start time.
`CanonicalWindowProvider` (the one that actually produces the "OBS-B has two
windows, cloud-block moves it" demo) lives only in `amis/demo.py` and is
injected explicitly by every test and by `amis.demo.run_canonical_replan_demo()`
— never by `amis.main.build_app()` or `amis.api.create_app()`'s default.

**Fix direction:** wire `CanonicalWindowProvider` (or an equivalent
multi-window provider) as the default passed from `amis/main.py`, or make
`create_app`'s default something richer than `SyntheticWindowProvider` for
non-test callers.

---

## GAP-02 — `mission_events`/`impacts`/`decision_traces` ids collide across scenarios (Critical, Persistence)

**Verdict: CONFIRMED — and broader than stated (not Postgres-specific)**

Evidence:
- `amis/db/schema.py:177-235` — `mission_events`, `impacts`, `decision_traces`
  all declare only `Column("id", String, primary_key=True)`; `scenario_id` is a
  plain indexed column, unlike `observation_windows`/`observation_requests`
  (`scenario_id` + `id` composite PK, lines 64-102) and `scheduled_actions`/
  `unscheduled_entries` (`plan_id` + `id`/`request_id` composite PK, lines
  142-175).
- `amis/ids.py:15-19` — `EVENT_ID_PREFIX="EVT"`, `IMPACT_ID_PREFIX="IMP"`,
  `TRACE_ID_PREFIX="TRACE"` are module-level constants, not scenario-scoped.
  Contrast `amis/repositories.py:298-303`, where `MissionSessionStore._new_session`
  explicitly scopes only the **plan** id prefix
  (`plan_id_prefix=f"{scenario_id}:PLAN"`) — events/impacts/traces get no such
  treatment, so `next_id`/`next_number` in `amis/ids.py:28-38` restart at
  `EVT-001`/`IMP-001`/`TRACE-001` for every scenario.

Live reproduction (two different scenarios, each recording its first cloud-block
event, against an **in-memory SQLite** engine — no Postgres needed):

```
scenario1 first event id: EVT-001
FAILED as predicted: IntegrityError (sqlite3.IntegrityError) UNIQUE constraint failed: mission_events.id
[parameters: ('EVT-001', 'SCN-002-OTHER', ...)]
```

The audit frames this as a PostgreSQL/Compose-specific risk; it is not —
it reproduces identically on SQLite, which is what `tests/test_sql_persistence.py`
itself uses, meaning it was one multi-scenario test away from being caught by
the existing suite (see GAP-11).

**Fix direction:** scope `EVENT_ID_PREFIX`/`IMPACT_ID_PREFIX`/`TRACE_ID_PREFIX`
per scenario the same way `plan_id_prefix` already is, or add `scenario_id` to
each table's primary key.

---

## GAP-03 — `ResourceProjection.available_at` is commit-order-dependent, not time-order-dependent (High, Planner)

**Verdict: CONFIRMED**

The module docstring (`amis/constraints/resources.py:1-10`) asserts the
projection is checked "at its own start time, not against the satellite's
current totals" — but `available_at` (lines 61-68) only iterates
`self._committed`, the list built by insertion order, filtering by
`action.start <= at`. Since `amis/planning/greedy.py:79-93` commits actions in
**priority order**, a higher-priority action with a *later* start time can be
validated and committed before a lower-priority, *earlier*-starting action is
even considered — so when the earlier action is later checked, the
higher-priority action's cost is correctly excluded (start > at), but the
reverse never gets reconciled: nothing ever re-checks the higher-priority
action's own feasibility against resources an earlier-time action will have
already consumed by then.

Reproduction: a battery of 15 Wh; `R-HI` (priority 5) windowed at hour 2, costs
10 Wh; `R-LO` (priority 1) windowed at hour 0, costs 10 Wh. Greedy planner
processes `R-HI` first (nothing committed yet → passes), then `R-LO` (nothing
committed with `start<=0` → also passes). Both scheduled:

```
scheduled: [('R-HI', '...T02:00:00', 10.0), ('R-LO', '...T00:00:00', 10.0)]
unscheduled: []
violation_count reported: 0

validate_plan violations: [Violation(reason_code=INSUFFICIENT_BATTERY, request_id='R-HI',
                                      details={'required_wh': 10.0, 'available_wh': 5.0})]
```

`validate_plan` (which sorts actions chronologically and commits in that order
— `amis/constraints/plan_validation.py:44`) correctly finds that by 02:00 only
5 Wh remains (10 already spent by `R-LO` at 00:00), so `R-HI` actually cannot
afford itself — a real violation the planner's own commit path missed.

**Fix direction:** in `GreedyPlanner.plan`, commit frozen/placed actions to
`ResourceProjection` in chronological (start-time) order, or re-run
`validate_plan` at the end of planning and treat any resulting violation as a
plan failure rather than trusting the per-candidate check alone.

---

## GAP-04 — Single candidate start time per window (High, Planner)

**Verdict: CONFIRMED**

`amis/planning/greedy.py:116-118`:
```python
for window in candidates:
    candidate_start = max(window.start, mission_state.simulated_time)
    candidate_end = candidate_start + timedelta(seconds=request.duration_s)
```
Exactly one instant is tried per candidate window; there is no scan for an
earlier/later free slot inside a window wider than the request's duration.

Reproduction: one 2-hour-wide window shared by two 10-minute requests
(`R-1` priority 5, `R-2` priority 4), no resource constraints:

```
scheduled:   [('R-1', '2026-01-01T00:00:00+00:00')]
unscheduled: [('R-2', 'TIME_OVERLAP')]
```

`R-2` is dropped even though 1h50m of free time remains in the same window
(00:10–02:00) — the planner never tried anything but 00:00 for `R-2`.

**Fix direction:** when `check_overlap` fails, retry with a later candidate
start inside the same window (e.g. immediately after the conflicting action's
end) before giving up on that window.

---

## GAP-05 — No lifecycle guards on `plan()`/`generate_windows()`/`replan()` (High, Replanning/Lifecycle)

**Verdict: CONFIRMED**

- `amis/session.py:100-118` (`plan()`) never checks `self._plans` is empty, and
  `previous_plan` is never passed, so a second call always produces a fresh
  `version=1, parent_plan_id=None` plan.
- `amis/session.py:91-94` (`generate_windows()`) unconditionally overwrites
  `self._windows` from the provider, discarding any `valid=False` mutation an
  earlier `inject_event(CLOUD_BLOCK, ...)` made (`session.py:292-303`).

Reproduction:
```
p1: PLAN-001 1 None
p2: PLAN-002 1 None
all plans: [('PLAN-001', 1, None), ('PLAN-002', 1, None)]   # two version=1 plans, no lineage

invalidated before regenerate: ['WIN-OBS-A-1']
invalidated after regenerate:  []   # the cloud-block invalidation is silently erased
```

- `frontend/src/panels/MissionBar.tsx:206` — the "Generate plan" button's
  `disabled` expression is `loading || scenario === null || missionState?.mission_complete === true`.
  This is a **partial** overstatement in the audit's framing ("keeps it
  enabled always" is not literally true — it is disabled while loading, before
  a scenario loads, and after mission completion), but the substantive claim
  holds: there is no `plan !== null` guard, so it stays clickable with a plan
  already in flight, and `frontend/src/state/useMissionSession.ts:189-197`
  (`generatePlan`) has no such guard either — it calls
  `generateWindows`+`plan` unconditionally. The bug is reachable from the UI.

**Fix direction:** make `plan()` reject (or route through `replan()`-style
versioning) when a plan already exists, and make `generate_windows()` either
refuse to run after events have invalidated windows, or re-apply the recorded
invalidations after regenerating.

---

## GAP-06 — `MissionSessionStore.save()` is not atomic (Medium, Persistence)

**Verdict: CONFIRMED** (exact op count is 6 in `save()`, 7 counting `scenarios.add` in `create()` — immaterial to the defect)

`amis/repositories.py:272-296` (`save`) calls, in sequence: `plans.replace_for_scenario`,
`windows.replace_for_scenario`, `events.replace_for_scenario`,
`impacts.replace_for_scenario`, `traces.replace_for_scenario`, `states.put`.
Every one of these, in `amis/db/repositories.py`, opens its own
`with self._engine.begin() as conn:` (e.g. lines 139, 182, 329, 367, 406,
447/451) — six independent transactions. A crash or exception between any two
of these leaves the scenario's stored state inconsistent (e.g. an
invalidated window persisted with no corresponding event row, exactly as the
audit describes).

**Fix direction:** thread one `Connection`/transaction through all six writes
in `save()` (each `Sql*Repository` method would need to accept an optional
external connection instead of always opening its own).

---

## GAP-07 — Emergency event payload bypasses tz-aware/interval validation (High, Event validation)

**Verdict: CONFIRMED — full end-to-end reproduction**

- `amis/api_schemas.py:69-77` (`ObservationWindowSchema`) has no validator
  checking `start < end`.
- `amis/api_schemas.py:35-44` (`ObservationRequestSchema`) has no tz-aware
  validator on `deadline`; the only tz check lives on `ScenarioSchema.validate_scenario`
  (lines 55-66), which iterates `self.requests` — i.e. only requests embedded
  in a `POST /scenarios` payload. `EmergencyTaskPayloadSchema.request` (line 134)
  is a bare `ObservationRequestSchema`, never routed through `ScenarioSchema`,
  so this check is skipped entirely for the emergency-event path.
- `amis/session.py:711-751` (`_validate_emergency_request`) checks id
  uniqueness, window ownership, and satellite id — never window ordering or
  timezone-awareness.

Live reproduction via `TestClient` against `create_app(window_provider=CanonicalWindowProvider())`:
posted an `EMERGENCY_TASK` event with a naive `deadline` ("2026-09-21T09:00:00",
no offset) and an inverted window (`end` before `start`):

```
inject naive/inverted emergency event: 201 Created   # accepted, should have been rejected
step after bad event: 500  (unhandled)
TypeError: can't compare offset-naive and offset-aware datetimes
  at amis/session.py:540, in _update_request_statuses_after_step
    elif state.simulated_time > request.deadline:
```

The route table in `amis/api.py` (all `@app.post`/`@app.get` handlers) has
**no reset endpoint** — `MissionSession.reset()` exists (`session.py:497-500`)
but is never exposed over HTTP — confirming the audit's "no reset route to
recover" claim: every subsequent `step`/`replan` call on that scenario 500s
forever.

**Fix direction:** add `start < end` and tz-aware validators to
`ObservationWindowSchema`/`ObservationRequestSchema` directly (not only inside
`ScenarioSchema`), so both the scenario-create and the emergency-event paths
get the same guarantees.

---

## GAP-08 — Decision traces misattribute all changes to the latest event only (Medium, Replanning/DecisionTrace)

**Verdict: CONFIRMED**

`amis/session.py:598-600` (`_triggering_event_id`) calls `_latest_impact_for(plan)`
(lines 586-596), which returns only the most recent impact evaluated against
the previous plan, then uses `impact.event_id` unconditionally as the single
`event_id` for every trace `build_traces` produces (lines 156-164).

Reproduction: injected `EVT-001` (cloud block) then `EVT-002` (battery drop)
before a single `replan()`:

```
events: ['EVT-001', 'EVT-002']
trace event attributions: {'EVT-002'}
```

Every trace from that replan is attributed to `EVT-002` only; any change
actually caused by `EVT-001` is misattributed.

**Fix direction:** `build_traces` needs a per-request-id or per-impact event
attribution (e.g. carry the impact chain since the previous plan, not just the
latest one) rather than a single scalar `event_id`.

---

## GAP-09 — `violation_count` counts drops, not `validate_plan()` violations (Medium, Domain/Metrics)

**Verdict: CONFIRMED**

- `amis/planning/greedy.py:180` — `violation_count=len(unscheduled)`.
- `.doc/specs/AMIS_SRD.md:530,546-548` — section "17. Metrics" → "Constraint
  Violations" → "Number of validation violations in the resulting plan."
  (verbatim citation matches; confirmed the audit did not misquote the spec.)

Both reproductions above double as confirmation:
- Canonical demo (GAP-01 repro): `violation_count: 4` while the plan itself is
  fully valid — the 4 are just dropped requests, not `validate_plan` failures.
- GAP-03 repro: `violation_count reported: 0` while `validate_plan` finds a
  genuine `INSUFFICIENT_BATTERY` violation — the exact inversion the audit
  describes (0 when there should be ≥1, nonzero when there should be 0).

**Fix direction:** compute `violation_count` from `len(validate_plan(...))`
against the constructed plan, not from `len(unscheduled)`.

---

## GAP-10 — `compare_plans` misclassifies newly-arrived requests (Medium, Replanning/Diff)

**Verdict: CONFIRMED**

- `amis/diff.py:112-114` — a newly-scheduled request (`before=None, after=not None`)
  gets `PlanChangeType.INSERTED` with `reason_code = recorded_reason or ReasonCode.ALTERNATIVE_WINDOW_AVAILABLE`.
  Traced through `amis/session.py:602-611` (`_impact_reasons_by_request`),
  `recorded_reason` is looked up via `request_by_action_id`, which is built
  from the **previous** plan's actions only (line 606) — a request that had no
  action in the previous plan (i.e., every newly-arrived emergency request)
  can never have an entry there, so `recorded_reason` is always `None` for
  this case and the fallback fires unconditionally in practice, not just "in
  the worst case."
- `amis/diff.py:120-124` (final `else` branch) — a request unscheduled in both
  versions (`before=None, after=None`) is classified `PlanChangeType.UNCHANGED`/
  `REQUEST_UNCHANGED`, **ignoring** the `unscheduled_reason` parameter entirely
  for this branch (it's only consulted in the `DROPPED` branch above it) — so
  a newly-arrived-but-still-unscheduled emergency request reads as "unchanged"
  even though it did not exist in the previous plan at all.
- `frontend/src/state/planComparison.ts:60-66,115-117` confirms the
  documented workaround: a `newlyArrivedUnscheduled` flag computed independently
  in the frontend (`!knownInParent.has(...) && unscheduledInRevised.has(...)`),
  with an explicit comment: "such a request as UNCHANGED, so the flag keeps it
  from reading as a request the replan simply ignored." Covered by
  `frontend/src/state/planComparison.test.ts:206-211`.

**Fix direction:** `compare_plans`/`_classify` needs a "known in parent's
request pool" signal (not just parent's actions/unscheduled) to distinguish
a genuinely new request from a pre-existing one, and should surface
`unscheduled_reason` in the "unscheduled-in-both" branch too.

---

## GAP-11 — Test coverage gaps (Medium, Test coverage)

**Verdict: CONFIRMED**

- Every REST test explicitly injects `CanonicalWindowProvider`:
  `tests/test_rest_api.py` lines 60, 370, 385, 456, 506, 566, 602, 619, 691 —
  9 occurrences, all `create_app(window_provider=CanonicalWindowProvider())`;
  none exercises `amis.main.build_app()` or `create_app()`'s real default.
- `tests/test_sql_persistence.py` (`grep def test_`) has no test that creates
  two *different* scenario ids and persists events/impacts/traces for both —
  the closest, `test_a_second_scenario_with_the_same_id_is_rejected` (line 164),
  tests the opposite case (same id rejected on the `scenarios` table), not
  cross-scenario collision on `mission_events`/`impacts`/`decision_traces`. My
  GAP-02 repro confirms this exact gap would have caught the bug.
- `tests/test_greedy_planner.py` (`grep def test_`) has 9 tests, none of which
  place a lower-priority action's window earlier in time than a higher-priority
  action's window (GAP-03), and none shares one window across two requests to
  probe whether the planner searches for a second slot (GAP-04).
- Full suite run: `pytest -q` → **136 passed**, 0 failed — consistent with the
  claim that these code paths are simply never exercised, not that they're
  covered and passing.

**Fix direction:** add one `test_sql_persistence.py` case with two distinct
scenario ids each recording an event, one `test_greedy_planner.py` case with
priority/time order inverted, and one with two requests sharing a single wide
window; add at least one REST test that builds the app via
`amis.main.build_app()`-equivalent default wiring.

---

## GAP-12 — `THIRD_PARTY_NOTICES.md` is a template, not a real notice, and points at a missing `LICENSE` (Low, Licensing)

**Verdict: CONFIRMED**

- `.doc/reference/THIRD_PARTY_NOTICES.md` is 6 lines total, and its entire
  content is a C-style comment block ("Portions adapted from World Monitor...
  Licensed under GNU AGPL v3. See LICENSE and THIRD_PARTY_NOTICES.md.") — i.e.
  it is literally the template header, not an actual notices document with
  attributed portions.
- No `LICENSE` file exists anywhere in the repo root (`find . -iname "LICENSE*"`
  returned nothing outside `.venv`/`node_modules`/`.git`).
- `grep -rl "AGPL\|THIRD_PARTY"` across `amis/**/*.py` and `frontend/src/**/*.{ts,tsx}`
  found **zero** source files carrying this header — confirming no AMIS source
  file actually uses the template it's supposedly the header for.
- `frontend/src/index.css:4-8` independently and correctly states: "the
  palette follows the dark operations-console treatment of koala73/worldmonitor
  (conceptual reference, no source copied)" — directly contradicting the
  notices file's implication that AGPL-licensed portions were adapted.

This is a real self-contradiction in the repo (a notices file asserting AGPL
provenance and pointing at a nonexistent LICENSE, next to a source comment
correctly disclaiming any copying) — low severity since it affects no shipped
functionality, but genuinely misleading if read at face value by a reviewer or
downstream consumer.

**Fix direction:** either delete `THIRD_PARTY_NOTICES.md` (nothing currently
requires it, since `index.css` already carries the accurate "conceptual
reference only" disclosure) or replace its content with an actual notices
list and add the referenced `LICENSE` file.

---

## Additional findings (not in the original audit)

1. **GAP-02 is not Postgres-specific.** The audit frames it as a risk that
   surfaces "under PostgreSQL/Compose." My reproduction shows it fails
   identically on plain in-memory SQLite — the same engine
   `tests/test_sql_persistence.py` already uses — meaning the existing test
   infrastructure could catch this today with one added test, no Postgres
   required. This slightly changes the risk framing: it's not a
   deploy-environment quirk, it's a schema defect that any real usage with
   >1 scenario will hit immediately, including local dev on SQLite.

2. **No HTTP reset endpoint exists at all**, independent of GAP-07. Once a
   scenario's session enters a bad state (via GAP-07's naive-timestamp bug, or
   for any other reason), there is no REST route to call `MissionSession.reset()`
   — `amis/api.py`'s route table has no `/scenarios/{id}/reset` or similar.
   This compounds GAP-05 and GAP-07: there is currently no API-level recovery
   path for a corrupted scenario short of restarting the process (in-memory
   store) or manually deleting rows (SQL store).

3. **GAP-09/GAP-03 interact directly** — confirmed empirically in the GAP-03
   repro: `violation_count` reports 0 for a plan that `validate_plan` proves
   invalid, so a user could see a "0 violations" plan that is not actually
   feasible. This is the same scenario the audit describes in GAP-09 as
   hypothetical; it's fully reproducible, not merely theoretical.

No other load-bearing defects were found in the spec docs that the audit
missed; the SRD, PRD, Implementation Guide, Build Spec and ADRs read as
internally consistent with each other on the points checked (violation_count
definition, ADR-0003 frozen-action exemption, ADR-0006 cross-table FK
rationale).

---

## Verification commands run

```bash
# Backend suite
.venv/Scripts/python -m pytest -q
# => 136 passed in 3.19s

# Frontend suite
cd frontend && npx vitest run --environment jsdom
# => Test Files  12 passed (12); Tests  139 passed (139)

# GAP-01 / GAP-04: production default window provider + single-candidate-start repro
.venv/Scripts/python -c "<inline script loading MissionSession() default ctor
  against amis.demo.build_canonical_replan_scenario(), printing scheduled/unscheduled>"

# GAP-02: cross-scenario id collision on SQLite
.venv/Scripts/python -c "<inline script creating two scenarios via
  MissionSessionStore against an in-memory sqlite engine, injecting a cloud
  block event in each, saving both>"
# => IntegrityError (sqlite3.IntegrityError) UNIQUE constraint failed: mission_events.id

# GAP-03: priority-vs-time commit order repro
.venv/Scripts/python -c "<inline script: R-HI priority 5 windowed late,
  R-LO priority 1 windowed early, 15 Wh battery, both requests cost 10 Wh each;
  compares GreedyPlanner output against amis.constraints.plan_validation.validate_plan>"

# GAP-04: shared-window repro
.venv/Scripts/python -c "<inline script: one 2h window shared by two 10-minute
  requests of different priority, no resource constraints>"

# GAP-05: duplicate plan() calls + generate_windows() erasing invalidation
.venv/Scripts/python -c "<inline script calling session.plan() twice, and
  calling generate_windows() again after a cloud-block event>"

# GAP-07: end-to-end emergency-event bad-timestamp repro via FastAPI TestClient
.venv/Scripts/python -c "<inline script: POST /scenarios, windows/generate,
  plan, then POST /events with a naive deadline + inverted window, then
  POST /simulation/step>"
# => events: 201 Created; simulation/step: 500 TypeError (naive vs aware datetimes)

# GAP-08: multi-event-before-one-replan attribution repro
.venv/Scripts/python -c "<inline script: inject cloud block then battery drop,
  single replan(), inspect get_traces() event_id set>"

# Code reads (file:line evidence cited throughout):
#   amis/main.py, amis/api.py, amis/session.py, amis/repositories.py,
#   amis/db/repositories.py, amis/db/schema.py, amis/ids.py,
#   amis/planning/greedy.py, amis/constraints/resources.py,
#   amis/constraints/plan_validation.py, amis/api_schemas.py, amis/diff.py,
#   amis/windows/synthetic.py, amis/demo.py,
#   frontend/src/panels/MissionBar.tsx, frontend/src/state/useMissionSession.ts,
#   frontend/src/state/planComparison.ts, frontend/src/index.css,
#   .doc/reference/THIRD_PARTY_NOTICES.md, .doc/specs/AMIS_SRD.md

grep -rn "CanonicalWindowProvider" tests/
grep -n "def test_" tests/test_sql_persistence.py tests/test_greedy_planner.py
grep -rn "AGPL\|THIRD_PARTY" amis/ frontend/src/   # => no matches (confirms GAP-12)
find . -iname "LICENSE*"   # => no matches outside .venv/node_modules/.git
```
