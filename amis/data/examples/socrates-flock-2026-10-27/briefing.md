# FLOCK 4G-1: archived conjunction predictions

This is a dated training mission on 2026-10-27, 04:00–10:00 UTC. It uses a real stored FLOCK 4G-1 orbit (NORAD 62666), with hypothetical payload capability, requests, resources, and outage assumptions. It does not reconstruct Planet's mission or confirm any maneuver.

Source credit: **CelesTrak SOCRATES Plus, Dr. T.S. Kelso**. Original report: https://celestrak.org/SOCRATES/sort-minRange.csv. The immutable local copy is `amis/data/conjunctions/2026-10-26/report.csv`, SHA-256 `a1ed99d1c54750caa3803727a3867718191e831717ee986666dd4bfa160aff28`. A current download may differ; search the archived bytes by catalogue pair and UTC TCA to verify these predictions:

| First object | Second object | UTC TCA | Distance (km) | Maximum probability |
| --- | --- | --- | --- | --- |
| STARLINK-30895 (58418) | FLOCK 4G-1 (62666) | 2026-10-27 06:13:09.293 | 0.518 | 0.0002385 |
| STARLINK-30895 (58418) | FLOCK 4G-1 (62666) | 2026-10-27 07:47:05.620 | 0.583 | 0.0001888 |

These are distinct encounters, both above the simulation policy `socrates-outage-v1` threshold of 0.0001. Maximum probability is a source prediction, not a measured collision outcome. The policy assumes **one hour before and after each TCA**, yielding outages 05:13:09.293–07:13:09.293 and 06:47:05.620–08:47:05.620 UTC. The intervals overlap. This padding was chosen for training, not inferred from a maneuver report.

Both events are injected at **05:00 UTC**, after the original report retrieval (2026-10-26 07:31:09.633806 UTC). Source publication and coverage were not established by the CSV; retrieval is the conservative availability bound. The HTTP Last-Modified header is preserved without treating it as proof of publication.

The orbital input is separately archived from `https://celestrak.org/NORAD/elements/gp.php?CATNR=62666&FORMAT=json`, with original bytes, retrieval time, and checksum. Its epoch is 2026-10-25 11:12:01.939968 UTC. It is a compatible dated snapshot, not a claim that SOCRATES used these exact elements. Orbital visibility uses this stored orbit with a 30-degree off-nadir limit. Sunlight filtering and sunlight recharge are explicitly disabled, allowing offline replay outside the bundled Sun ephemeris range. Requests are hypothetical sensor opportunities; this is not an optical feasibility claim.

## Replay from the repository root

```powershell
# Build baseline, advance exactly to 05:00, inject, inspect impact, persist/reload.
.venv/Scripts/python -m scripts.run_socrates_replay

# A separate explicit replan, also persisted and reloaded:
.venv/Scripts/python -m scripts.run_socrates_replay --replan --database outputs/socrates-replay.db
```

Use a new database filename per run. No report, orbital catalogue, or network is read by replay: only the bundled Scenario and generated inputs. The first observation is completed before injection and remains frozen. OBS-2 and OBS-3 become invalid, while OBS-4 remains feasible. Injection leaves the baseline active. The explicit replan drops OBS-2 and moves OBS-3 to 09:02:37 UTC, both with `COLLISION_AVOIDANCE_OUTAGE` traces linking the recorded evidence; reloading retains event evidence, impacts, and traces. Loading this Example in the dashboard creates its pristine Scenario; apply the generated payloads at 05:00 to follow the same flow using E-01 event inspection.

No maneuver confirmation, fuel use, delta-v, or trajectory change is modeled. This Example is not operational collision-avoidance advice.
