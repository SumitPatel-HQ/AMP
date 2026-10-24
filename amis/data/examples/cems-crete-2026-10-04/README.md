# Real CEMS Example: EMSR933

The Scenario stores its own orbital elements and checksums, matching the existing
2026-09-25 catalogue and bundled Sun ephemeris. Its horizon is October 4-6, 2026.
Application startup, loading and replay never fetch source data.

Archive: `amis/data/cues/crete-emsr933-20261004/manifest.json` and original
`response.json`. Profile and generated inputs are beside this file.

From the repository root:

```powershell
python -m scripts.run_cems_crete_replay
python -m scripts.run_cems_crete_replay --replan
python -m scripts.build_cue_events amis/data/examples/cems-crete-2026-10-04/scenario.json --archive-manifest amis/data/cues/crete-emsr933-20261004/manifest.json --imaging-profile amis/data/examples/cems-crete-2026-10-04/imaging-profile.json --all --out amis/data/examples/cems-crete-2026-10-04/cue-inputs.json
```

To fetch a new archive deliberately (existing directories are refused):

```powershell
python -m scripts.fetch_cems_archive EMSR933 path/to/new-archive
```

For dashboard use, load the Example, generate windows, plan, advance 39720
seconds, and submit the first input's event_type and payload through the existing
emergency-arrival API. Developer metadata and injection_time are not API fields.
Select Replan separately. See the briefing for limitations and credit.
