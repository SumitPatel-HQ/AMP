# Handoff: deep spec check of Phase 2 Waves 2–5

**For:** Muse 1.3 Spark (or any reviewer agent)
**Date:** 2026-09-28
**Repo:** `D:/LearningHub/CollegeProjects/AMP`, branch `main`, HEAD `ab080ba` or later
**Mode:** read-only review. Do not edit code. Write findings to the report file named below.

## Why

A two-axis review (spec and standards) of Waves 1–7 checked Waves 1, 6 and 7
in depth. Waves 2, 3 and 5 got only a quick check of file layout and names,
and Wave 4 only a light check. This task closes that gap: trace every Wave 2–5
spec decision and user story to code and tests, and report what is missing,
partial or wrong.

## Current state (already verified, do not redo)

- Backend: `.venv/Scripts/python -m pytest -q` gives 229 passed.
- Evaluation: `.venv/Scripts/python -m amis.evaluation.runner` gives 13/13
  cases and all 4 gates passing. It rewrites `evaluation-report.json`; restore
  that file with `git checkout -- evaluation-report.json` afterwards if the
  diff is only timings.
- Wave 6 (slew, recharge) and Wave 7 (multiple satellites) are reviewed and
  fixed. CP-SAT was restructured in `ab080ba`: `_ModelBuilder`, pairwise slew
  order literals, a bucketed battery chain when recharge is on, and a bucketed
  storage chain when downlinks exist. Re-check those only where they touch
  Wave 2–4 requirements (for example decision 17's "linear sums" wording,
  which Waves 4 and 6 later superseded by ADR).

## Sources

- Spec: `.doc/specs/AMIS_Phase2_Spec.md`. Wave 2–5 user stories are 27–44,
  implementation decisions are 17–28, plus the per-wave testing bullets near
  the end of the file.
- Background: `.doc/prompts/Real Scenario Research prompt.md` and
  `AMIS_Real_Scenario_Research.md`. Skim these only when a decision is
  ambiguous.
- ADRs: `.doc/adr/0009` (planner selection, CP-SAT determinism), `0010`
  (Wave 3 spacecraft realism), `0011` (downlink), `0012` (weather events). A
  later ADR can supersede a spec line. When it does, record the finding as
  "superseded by ADR-00xx", not "missing".
- Glossary: `CONTEXT.md`.
- Wave commits: `86c5fdf` (Wave 2), `94f92ca` (Wave 3), `051d6dc` and
  `53c3838` (Wave 4), `f9ae134` (Wave 5). Use `git show --stat <sha>` to find
  the files for each wave.

## What to check, per wave

**Wave 2 (decisions 17–20, stories 27–33)**
- CP-SAT implements the `Planner` protocol with no simulation, replan or UI
  changes. Check: integer seconds, presence literal plus optional interval per
  request-window, no-overlap including frozen actions, a stability term that
  mirrors greedy, and unscheduled reasons coming from the existing checks.
- Determinism: one worker, fixed seed, work-based limit. Status, objective
  bound and optimality gap are recorded in `solver_details`.
- Planner choice is selected per run and recorded in the plan (story 29).
- The comparison covers the three examples plus generated orbital missions at
  several request counts, with and without events, and reports every metric
  story 28 and decision 19 list. It is persisted with data origin and library
  versions. Check whether the "generated orbital missions at several request
  counts" part really exists.
- Evaluation cases are stored as data files. Check:
  - all 7 categories exist;
  - there is one constraint case per reason code (list every `ReasonCode` and
    check each one is covered);
  - expectations are written independently of planner output;
  - the runner drives `MissionSession` only and names the failing stage;
  - the disclaimer is printed;
  - a socket-blocking test enforces the offline rule.

**Wave 3 (decisions 21–24, stories 34–37)**
- Payload outage uses the reserved unavailability event type over an
  interval, and validation rejects actions inside the span.
- Derived cost defaults live in the builder only; planner and constraints are
  unchanged.
- Settling time is enforced through the overlap rule. The window-meaning ADR
  (`0007`) records whether durations include settling time.
- Culmination placement is an option. Dedicated replan tests cover how it
  interacts with the stability rule.

**Wave 4 (decisions 25–27, stories 38–42)**
- Contacts use the same event-search call as targets, with a 5–10° mask, and
  appear on the timeline and map (check the frontend under `frontend/src/`).
- Actions have a kind field. A downlink action carries a station and contact
  reference, not a request. Storage falls by rate × duration, floored at zero.
- Plan diff, churn, traces and metrics each define explicitly how actions
  with no request are handled. Check each one in code.
- A communication outage invalidates the overlapping contacts through the
  impact and replan path.
- Storage visibly rises and falls across the mission (story 42), in both the
  UI and the API.

**Wave 5 (decision 28, stories 43–44)**
- An offline ingest script stores raw responses with retrieval time and hash,
  plus normalised coverage samples.
- A threshold rule produces `CLOUD_BLOCK` events whose payloads carry source,
  coverage and threshold.
- The planner never reads weather data (grep planners and constraints for any
  weather import).
- Replays read recorded values only, with no network access.

Also run the testing bullets for Waves 2–5 at the end of the spec. For each
bullet, name the test that covers it, or report that none does.

## How to work (keep usage low)

1. Read the spec sections for Waves 2–5 once, then the four ADRs.
2. For each requirement, find the code with grep, read only the relevant
   function, and find the test that covers it.
3. Don't dump whole diffs. `git show --stat <sha>` plus targeted reads is
   enough.
4. Run pytest once at the end, and the frontend tests
   (`npm --prefix frontend run test -- --run`) once, if Node is available.

## Output

Write `.doc/audits/WAVE2-5_Deep_Spec_Check_Report.md` with:

- One table per wave with columns: requirement (story or decision number) |
  status (Done / Partial / Missing / Wrong / Superseded) | evidence
  (`file:line` and test name) | note.
- A findings list, ranked by severity. Quote the spec line and cite
  `file:line` for each finding.
- A scope-creep section for behaviour that no spec line asks for.
- A final verdict line for each wave.

Keep the report under 800 words, not counting the tables. Report facts only.
Do not suggest fixes unless a finding would be ambiguous without one.
