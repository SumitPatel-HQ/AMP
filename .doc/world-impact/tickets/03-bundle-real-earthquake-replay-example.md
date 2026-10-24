# 03: Bundle a real earthquake replay Example

**What to build:** A trainee can load a bundled, dated earthquake Example offline, create a baseline MissionPlan, advance to the real cue instant, inject it, inspect Impact, and choose to replan through the existing lifecycle controls.

**Blocked by:** 01: Build reproducible USGS cue inputs; 02: Inject, inspect, and map evidence-bearing emergency arrivals.

**Status:** implemented

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

- [x] Select an independently verifiable real USGS earthquake and finish this ticket with its exact source event identifier, source URL, and named committed archive artifact documented. Do not invent a September 28 probe event or assume the mutable feed still contains it. Use a preserved probe record only if its evidence is actually found.
  - Selected `us6000u0xi` (M6.3, "102 km NE of Norsup, Vanuatu", 2026-10-08T09:00:07.768Z), fetched live from `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson` on 2026-10-09 and committed at `amis/data/cues/vanuatu-us6000u0xi-20261008/` (`response.geojson` + `manifest.json`). Not the research's unresolved September 28 probe event.
- [x] Bundle raw evidence, integrity manifest, explicit imaging profile, generated cue input, dated Scenario, and stored orbital inputs. The Example uses matching dates, begins before the earthquake to permit a baseline plan, and has enough horizon to demonstrate a response.
  - `amis/data/examples/usgs-vanuatu-2026-10-08/` bundles `imaging-profile.json`, `scenario.json`, and the generated `cue-inputs.json`; `amis.examples.usgs_vanuatu_example()` builds the identical dated Scenario (2026-10-07T12:00Z-2026-10-08T22:30Z, bounded by the stored Landsat-8 element epoch's 14-day validity) with stored orbital elements and routine baseline demand.
- [x] The briefing names the actual earthquake and separates its facts from hypothetical satellite capabilities, imaging costs, point-target simplification, and AMIS priority/deadline policy.
  - `amis/data/examples/usgs-vanuatu-2026-10-08/briefing.md`, served via `ScenarioSummarySchema.briefing` from `/examples` and shown in the Example library.
- [x] The Example appears in the existing Example library and creates a new Scenario when loaded. Startup and loading use only bundled inputs and make no network call.
  - Registered in `amis.examples.examples()` under `usgs-vanuatu-2026-10-08`; loading follows the existing `/examples/{id}` → `POST /scenarios` path used by every other Example.
- [x] A documented runnable event script uses existing lifecycle operations to advance to the cue's exact simulated instant before injection. It checks timing and fails on a late clock rather than silently injecting late or rewriting the event time. No new exercise engine is introduced.
  - `scripts/run_usgs_vanuatu_replay.py`, built on `amis.session.MissionSession` only; it raises rather than injecting when the clock cannot reach the cue's exact recorded time.
- [x] The accepted emergency event contains source evidence and recorded orbital windows. Injection leaves the baseline plan intact while exposing Impact; manual replan produces ordinary PlanDiff and DecisionTrace results.
  - Verified end-to-end: injection records full evidence and generated windows, baseline actions are unaffected, and `--replan` produces a `HIGHER_PRIORITY_TASK_INSERTED` trace scheduling the emergency request.
- [x] A served emergency is demonstrable with the bundled configuration. Legitimate unserved results elsewhere remain supported and explainable without pipeline failure or invented windows.
  - The bundled profile and orbital geometry produce a feasible window before the policy deadline, and the replan schedules it; ticket 02's existing unserved-request handling is unchanged.
- [x] Frozen actions remain unchanged and expiry remains permanent. The pristine Scenario is unchanged by injection or replan.
  - Unchanged existing behavior; no new code path touches frozen actions, expiry, or the pristine Scenario.
- [x] The pristine Scenario and accepted ordered event log suffice to reproduce functional requests, evidence, windows, plans, and explanations without the source archive or network. Wall-clock planning timings are excluded from functional equality.
  - `scripts/run_usgs_vanuatu_replay.py` reproduces the full loop from `usgs_vanuatu_example()` plus the committed `cue-inputs.json` alone.
- [x] The existing third-party-notices documentation credits the USGS evidence and records the applicable source notice. The Example briefing displays `U.S. Geological Survey` and the simulator-policy notice.
  - Added a Data sources section to `.doc/reference/THIRD_PARTY_NOTICES.md`; the briefing displays `U.S. Geological Survey` and the existing AMIS simulation-policy notice.
