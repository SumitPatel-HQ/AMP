# USGS Vanuatu earthquake replay Example bundle

Ticket 03's bundled, offline, dated earthquake replay. All files here are
committed inputs; nothing is fetched at application startup or Example
load.

- `briefing.md` — the trainee-facing briefing, served by `/examples` and
  shown in the Example library.
- `scenario.json` — the dated Scenario used to generate `cue-inputs.json`
  below. `amis.examples.usgs_vanuatu_example()` builds the identical
  Scenario in code; this file documents and reproduces that generation
  step.
- `imaging-profile.json` — the explicit author-supplied imaging profile
  (duration, energy cost, storage cost) for the earthquake request. These
  are AMIS Example authoring choices, not USGS facts or real satellite
  capabilities.
- `cue-inputs.json` — the generated developer cue input, produced by the
  command below from the committed USGS archive at
  `amis/data/cues/vanuatu-us6000u0xi-20261008/`. It is not an accepted
  MissionEvent; `scripts/run_usgs_vanuatu_replay.py` injects it at its
  intended time using the existing mission lifecycle.

## Why the request's deadline outlives the Scenario

`cue-inputs.json`'s request carries a `2026-10-10T09:00:07.768Z` deadline:
the real USGS `green`-alert policy offset (48 hours from the earthquake,
`amis/cues/rules.py`'s `ALERT_POLICY`), computed and recorded exactly as
ticket 01 requires. The Scenario itself ends at `2026-10-08T22:30:00Z`,
inside the stored Landsat 8 element's 14-day validity window
(`amis/orbital/validation.py`) — the real orbital-element age, not this
Example's authoring choice, is what caps the horizon. The deadline is
therefore never the binding constraint here: whatever the planner
schedules must land before `2026-10-08T22:30:00Z` regardless of the later
deadline. `scripts/run_usgs_vanuatu_replay.py --replan` demonstrates this
is still reachable: with the bundled profile and the Scenario's wider
60-degree off-nadir window policy, a real daylight pass over the
epicenter opens at `2026-10-08T21:58:41Z`, and the replan schedules the
request there with a `HIGHER_PRIORITY_TASK_INSERTED` trace and zero
unscheduled requests. `tests/test_usgs_vanuatu_bundle.py` asserts this
servable outcome so it cannot regress silently.

Regenerate `cue-inputs.json` deterministically from the committed inputs:

```powershell
python scripts/build_cue_events.py amis/data/examples/usgs-vanuatu-2026-10-08/scenario.json --archive-manifest amis/data/cues/vanuatu-us6000u0xi-20261008/manifest.json --imaging-profile amis/data/examples/usgs-vanuatu-2026-10-08/imaging-profile.json --event-id us6000u0xi --out amis/data/examples/usgs-vanuatu-2026-10-08/cue-inputs.json
```

Replay the mission offline, advancing to the earthquake's exact simulated
time before injecting it:

```powershell
python scripts/run_usgs_vanuatu_replay.py
python scripts/run_usgs_vanuatu_replay.py --replan
```

Source earthquake: U.S. Geological Survey, event `us6000u0xi`, M6.3,
"102 km NE of Norsup, Vanuatu", 2026-10-08T09:00:07.768Z. See
`briefing.md` for the full fact/assumption separation and
[ADR-0015](../../../.doc/adr/0015-usgs-cue-replay.md) for the policy and
replay-boundary decisions.
