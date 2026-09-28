# Deep spec check: Phase 2 Waves 2–5

Date: 2026-09-28. Repo `main`, HEAD past `ab080ba`. Read-only review.
Sources: `.doc/specs/AMIS_Phase2_Spec.md`, ADRs 0007/0009/0010/0011/0012, `CONTEXT.md`, wave commits `86c5fdf`, `94f92ca`, `051d6dc`+`53c3838`, `f9ae134`.
Verification: backend `.venv/Scripts/python -m pytest -q` → 229 passed. Frontend `npm --prefix frontend run test -- --run` → 99 passed, 46 failed in 2 files (`App.test.tsx`, `MissionMapPanel.test.tsx`, all `TypeError: fetch failed`, needs live backend; pre-existing env issue, not Wave 2–5 logic). Evaluation runner not re-run (handoff notes 13/13 already verified).

## Wave 2 — proof of quality (stories 27–33, decisions 17–20)

| Requirement | Status | Evidence (file:line + test) | Note |
|---|---|---|---|
| S27 second CP planner, `Planner` protocol unchanged | Done | `amis/planning/cp_sat.py:390-401` sig matches greedy; `amis/planning/selection.py:6-12`; no protocol change; no dedicated test | — |
| S28 comparison table over shared missions | Done | `amis/evaluation/comparison.py:86-101` metrics, `:105` 3 examples, `:52-66` orbital N=(3,6,8), `:109` with/without event; `evaluation-report.json` 28 runs | `plan_churn=None` when no event is honest (`:97`) |
| S29 per-run choice recorded | Done | `amis/session.py:118-121` `select_planner`, `:140,:184`; `amis/domain/plan.py:106,121,140` `planner_name`; `amis/api.py:322,324,395`; no dedicated test | Greedy via default, implicit but works |
| S30 deterministic solver settings | Done | `amis/planning/cp_sat.py:433-435` workers=1, seed=0, `max_deterministic_time`; default 1.0 (`:391`); no test | Matches ADR-0009 |
| S31 one-command run, 7 categories, gates, report | Done | `scripts/run_evaluation.py:11`; `amis/evaluation/cases.py:42-50`; 7 dirs/13 files under `amis/data/evaluation/`; `amis/evaluation/runner.py:227-230,142-165` gates; no pytest | Dir names use underscores vs spec hyphens |
| S32 persisted with origin + versions | Done | `amis/evaluation/comparison.py:129-133` `data_origin`+versions; `evaluation-report.json` ortools 9.15/skyfield 1.55/sgp4 2.27 | — |
| S33 simulator disclaimer | Done | `amis/evaluation/runner.py:30-33,269`; in report; no test | — |
| D17 CP model (int-s, literal+interval, no-overlap+frozen, stability, reasons) | Done | `amis/planning/cp_sat.py:309-317,328` int-s + literal + `<=1`; `:287-295,358` frozen + no-overlap; `:374-387,429` stability mirrors `amis/planning/greedy.py:333-345`; `:449,508-563` reasons via greedy checks; no test | Per-sat scoping is Wave-7 extension |
| D17 linear one-way sums | Superseded | `amis/planning/cp_sat.py:361-372` bucketed chains now; `tests/test_wave4_downlink.py:109`, `tests/test_wave6_dynamics.py:181` | Superseded by ADRs 0011/0013, correct |
| D18 status/bound/gap recorded | Done | `amis/planning/cp_sat.py:473-484` status/objective/bound/gap/fallback/version; `tests/test_wave4_downlink.py:114` fallback only | Fallback `cp_sat.py:442-445,481` Done |
| D19 comparison content | Done | Same as S28; medians `comparison.py:122-127`; no test | Generated orbital at several counts confirmed |
| D20 cases as data, independent expectations, session-only runner, stage errors, offline guard | Partial | Expectations independent (`runner.py:113-128`); session-only + stage errors (`runner.py:26-28,36-40,102-103,146,219-223,274`); socket block impl (`:43-60,202`) but no test for it; reason-code coverage bundled (see F2) | Runner imports providers to build session, compliant in spirit |
| T2 zero-violations / utility>=greedy / determinism / report / bad-plan gates / stage errors | Missing | Gates exist (`runner.py:142-165,185-198,227-230`) but `tests/` has no `*eval*/*compar*/*cp*/*select*` and zero refs to `zero_violations\|byte_identical\|run_comparison` | All 6 bullets: implementation without pytest |

## Wave 3 — richer spacecraft (stories 34–37, decisions 21–24)

| Requirement | Status | Evidence | Note |
|---|---|---|---|
| S34/D21 payload outage interval, validation rejects inside | Done | `amis/domain/event.py:104-110,187-188`; `amis/constraints/availability.py:24-30`; `amis/constraints/plan_validation.py:71-75,117-119`; `amis/planning/greedy.py:217-219`; `amis/planning/cp_sat.py:321-323,330-343`; `amis/session.py:399-413,445-460`; `amis/impact.py:30-36,49-59` | Frozen exempt `plan_validation.py:105-107`; no provider change (`windows/orbital.py` zero outage refs) |
| D21 "toggling the satellite flag" | Superseded | `amis/session.py:378-389` keeps base flag, span narrows | Correct per ADR-0010:10-11 |
| S35/D22 derived defaults builder-only | Done | `amis/costs.py:12-19` exact formulas; `frontend/src/panels/MissionBuilder.tsx:29-35,123-130`; zero `amis/` imports of costs; no test | Backend helper unimported; real builder is frontend |
| S36/D23 settling via overlap, durations exclude it, zero=history, CP-SAT ceil | Done | `amis/domain/orbit.py:53`; `amis/constraints/overlap.py:27-40`; `amis/planning/cp_sat.py:100,309`; ADR-0010:19-20 | Enforced via `SlewModel` superset (see creep) |
| S37/D24 culmination option, peak-first, stability kept, CP-SAT tie-break | Done | `amis/domain/orbit.py:54`; `amis/planning/greedy.py:66-80,207-211,333-345,373-385`; `amis/planning/cp_sat.py:345-353,374-387` scale trick | Code correct |
| D24 dedicated culmination+stability replan tests | Missing | grep `culmination` in `tests/` → 0 hits; only `test_replan.py:128` stability w/o culmination | Acceptance gate unmet |
| T3 outage-exact-span / derived-hand-computed / settling / culmination+stability | Missing/Partial | Outage: none (closest `test_wave7_multi_satellite.py:291-325` satellite-scope only); derived: none; settling: Partial (`test_wave6_dynamics.py:53-79` combined slew+settling, `test_constraint_overlap.py:23-48` no gap); culmination: none | 3.5 of 4 bullets lack dedicated tests |

## Wave 4 — ground stations and downlink (stories 38–42, decisions 25–27)

| Requirement | Status | Evidence | Note |
|---|---|---|---|
| S38 station catalogue + opt-in policy | Done | `amis/data/stations/stations.json:3-10` 6 stations mask 5/10; `manifest.json:1-6` hash; `amis/orbital/stations.py:22-36`; `amis/api.py:177-181`; `tests/test_wave4_downlink.py:179-192` | No migration per ADR |
| S39/D25 contacts same search, derived, ids, timeline+map | Done | `amis/windows/orbital.py:27-33,102`; `amis/windows/contacts.py:10,43-57,64`; `amis/session.py:484-503`; no contacts table; `frontend/src/timeline/missionTimelineModel.ts:52-56,413-450`; `frontend/src/map/contactTracks.ts:39-94`; `missionLayers.ts:62-69`; `MissionMapPanel.tsx:193,206,238` | Multi-sat id suffix gated, ADR-0014 scope |
| S40/D26 kind, signed storage, end-release, floor, reservations+prune, no overlap/outage role | Done | `amis/domain/plan.py:20-39`; `migration 0004`; `amis/planning/downlink.py:27-72`; `amis/constraints/resources.py:61-68,104-122,140-149`; `amis/constraints/overlap.py:34-37`; `amis/constraints/plan_validation.py:89-128`; `amis/session.py:678-691`; `tests/test_wave4_downlink.py:96-106` | Energy zero; ordering + prune match ADR exactly |
| D26 request-less rules in diff/churn/traces/metrics/impact | Done | `amis/diff.py:80-83,53-60`; `amis/trace.py:80-82`; `amis/metrics.py:46-49,85-145`; `amis/domain/violation.py:13`; `amis/impact.py:39-57`; `amis/constraints/plan_validation.py:99-103`; covered `test_wave4_downlink.py:150-156` | Each consumer filters by kind; volume is floored actual |
| S41 comm outage invalidates contacts via impact+replan | Done | `amis/domain/event.py:128-149`; `amis/session.py:334-336,462-475,1024-1037`; `amis/windows/contacts.py:67-80`; `tests/test_wave4_downlink.py:134-164` | Rejects unknown station/naive tz/empty span |
| S42 storage rises+falls in UI+API | Done | `frontend/src/state/storageProfile.ts:44-68`; `StorageProfileChart.tsx:8-30`; `amis/api.py:183-190,416-418`; `tests/.../storageProfile.test.ts:15,32` | — |
| T4 contacts-vs-sampler / floor / outage / request-less-no-crash | Done | `tests/test_wave4_downlink.py:46-64` ±2s sampler; `:67-93` floor+volume; `:134-156` outage; `:96-106,167-176` no-crash + no-station case | All 4 bullets named |

## Wave 5 — weather events (stories 43–44, decision 28)

| Requirement | Status | Evidence | Note |
|---|---|---|---|
| S43 threshold rule → CLOUD_BLOCK with source/coverage/threshold | Done | `amis/weather/threshold.py:25-54,80-104`; `amis/domain/event.py:24-28`; `tests/test_weather_threshold.py:69-83,221-240` | At-threshold blocks; skip invalid; exact-coord match |
| S44 raw archive + retrieval time + hash + samples | Done | `scripts/fetch_weather_archive.py:65,70-93`; `amis/weather/archive.py:34-111`; `amis/weather/samples.py:17-22`; `manifest.json:2-14`; `tests/test_weather_archive.py:28-78,81-126` incl. tamper + 6 reject cases | Committed file is `sample:true` excerpt per ADR |
| D28 all-or-nothing evidence, planner blind, offline replay, builder script | Done | `amis/api_schemas.py:292-308`; `amis/session.py:906-931`; grep `amis/planning`+`amis/constraints` weather → none; `tests/test_weather_replay.py:162-254` socket guard + replay + reject partial/wild; `scripts/build_weather_events.py:43-80` offline verdicts | `to_dict` omits absent keys, no migration |
| T5 threshold mapping / offline replay / hash verify | Done | `test_weather_threshold.py:221-240`; `test_weather_replay.py:197-210`; `test_weather_archive.py:28-59` | All 3 bullets named |

## Findings (ranked)

1. Wave 2 testing suite absent. Spec: "each evaluation gate failing on a crafted bad plan" plus bullets "both planners return zero violations on every case, CP-SAT utility at least equal to greedy everywhere, determinism across reruns, comparison report over the case set, runner stage errors naming the stage". Gates exist in `amis/evaluation/runner.py:142-165,185-198,227-230` and data `planner_comparison/cp-sat-at-least-greedy.json`, `determinism/cp-sat-double-run.json`, but no pytest references `run_comparison|zero_violations|byte_identical` and no file `tests/*eval*|*compar*|*cp*|*select*`. Nothing checks the claims mechanically.
2. Wave 3 acceptance gate unmet. Spec D24: "The stability rule interaction is covered by dedicated replan tests before acceptance." `amis/planning/greedy.py:333-345` implements it, but grep `culmination` in `tests/` returns nothing. Same gap for "derived defaults match hand-computed values" (formulas `amis/costs.py:12-19` + `MissionBuilder.tsx:29-35` untested) and "outage events invalidate exactly the actions in span" (only satellite-scoping `tests/test_wave7_multi_satellite.py:291-325`, span-exactness untested; `test_constraint_availability.py:12-23` never passes outage intervals). Settling alone is untested (`test_wave6_dynamics.py:53-79` covers settling+slew combined only). Stale docstring `amis/constraints/availability.py:1-5` ("No MVP event produces an unavailable satellite yet") contradicts `amis/domain/event.py:187`.
3. Wave 2 reason-code and offline-guard partial. Spec D20: "constraint (one per reason code)". All 12 `ReasonCode`s (`amis/domain/enums.py:41-59`) are covered but bundled across 6 files in `constraint/` with `NO_OBSERVATION_WINDOW` in `orbital_window/`, not one file per code. Socket block is implemented (`runner.py:43-60,202`) with no test; only `tests/test_weather_replay.py:181-206` has its own guard.
4. Wave 4 ADR text stale, code ahead. Spec D26/ADR-0011:69-73: "CP-SAT keeps its linear storage sum... An exact reservoir model is deferred to Wave 6." Code now has the exact bucketed reservoir `amis/planning/cp_sat.py:224-266` wired at `:361-363`, proven by `tests/test_wave4_downlink.py:109-115` (`fallback is False`, utility>=greedy). Consequence bullet `0011:99-101` ("CP-SAT is weaker than greedy on storage-bound downlink missions until Wave 6") no longer holds. Superset, not a bug.
5. Wave 2 wording superseded, correctly handled. Spec D17 "one-way battery and storage stay linear sums" is superseded by ADRs 0011/0013; current bucketed chains are the right behavior. Same for D21 "toggling the satellite flag" refined by ADR-0010 (`amis/session.py:378-389`).
6. Wave 5 minor fragilities only. Exact-float target match `amis/weather/threshold.py:46` vs 4-decimal `location_key` (`amis/weather/archive.py:29-31`) could miss on re-rounded refreshes; 30-min tie-break picks earliest (`threshold.py:49-50`, tested `:221-240`) though ADR is silent on ties; fetch script writes `{date}.json` (`fetch_weather_archive.py:77`) while committed file is `sample-2026-09-25.json` (absorbed by manifest indirection). No failures.

## Scope creep

Wave 3 settling rides on the Wave 6 `SlewModel` (`amis/dynamics/slew.py:36-42,81-92`, pairwise angle/rate, altitude, fail-closed) beyond the single-gap spec; `overlap.py:1-8`, `plan_validation.py:15-16` already cite ADR-0013. CP-SAT carries later-wave logic: slew ordering (`cp_sat.py:89-106`), recharge buckets (`:172-221`), downlink chain (`:224-265`), per-satellite scoping (`:276-278,355-372`) — expected post-Wave-2 evolution. Wave 4 multi-sat contact suffix (`contacts.py:54-57`, gated on single-sat) and metrics averaging (`metrics.py:55-70`) are labeled ADR-0014 and byte-identical for single-sat. Wave 5 extras (public `coverage_at`, sort by start/id, CLI flags, round-trips) stay within the pure-rule ADR and are tested. No unrelated product behavior found.

## Verdicts

- Wave 2: Partial — implementation Done (D17 linear sums Superseded correctly), testing bullets Missing.
- Wave 3: Partial — implementation Done (D21 flag wording Superseded correctly), D24/derived/span/culmination tests Missing, one stale docstring.
- Wave 4: Done — all stories, decisions, and testing bullets covered; only ADR-0011 consequence text stale.
- Wave 5: Done — all stories, decision 28, and testing bullets covered literally.
