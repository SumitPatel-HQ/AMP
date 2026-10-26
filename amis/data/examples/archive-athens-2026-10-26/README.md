# Real Athens catalogue evidence, hypothetical Satellite capacity

This Example combines real Sentinel-2 metadata with explicitly synthetic
observation windows and Satellite resources. It makes no claim about real
Satellite tasking or the content of an image product.

## Replay

From the repository root:

```powershell
.venv\Scripts\python -m scripts.run_archive_athens_replay
.venv\Scripts\python -m scripts.run_archive_athens_replay --replan
.venv\Scripts\python -m scripts.run_archive_athens_replay --replan --database outputs/athens-new.db
```

The first command leaves the old plan visibly affected. The second explicitly
replans. The optional database must be a new SQLite file; the script saves and
reloads through the normal MissionSessionStore. Replay reads only scenario.json
and archive-inputs.json, never the catalogue or original archive.

At 07:00 the baseline schedules OBS-FROZEN (priority 5) and OBS-ARCHIVE (4),
using the 80 Wh budget. At 07:05 the first action has started and consumed
40 Wh. The script checks that exact intended instant before injection.
After explicit replan, OBS-COMPETING (3) replaces only the unfrozen imaging.
The frozen action, spent 40 Wh and occupied storage are preserved.

Acquisition utility goes from 9 to 8. Archive utility is 4, and union-based
total fulfilled utility is 12 after replan (three unique requests).
Before replan, planned acquisition plus archive counts OBS-ARCHIVE once.
Historical Plan V1 excludes the later archive transition. Completion remains
zero until imaging finishes; archive fulfillment never becomes an imaging
completion or resource refund. Final imaging completion covers OBS-FROZEN
and OBS-COMPETING, with no imaging completion for OBS-ARCHIVE.

## Rebuild without network

```powershell
.venv\Scripts\python -m scripts.build_imagery_events amis/data/examples/archive-athens-2026-10-26/scenario.json --archive-manifest amis/data/imagery/athens-sentinel2-20261026/manifest.json --requirements amis/data/examples/archive-athens-2026-10-26/requirements.json --out outputs/athens-inputs.json
```

The rebuilt bytes match committed archive-inputs.json. It records the explicit
profile, normalized evidence, original source-page digest, conservative search
availability time, and checked injection instant. Refreshing the source is an
explicit developer fetch into a **new** archive directory; changing search
results never changes this replay. See [archive operations](../../imagery/README.md).

## Dashboard

Choose Examples → Athens archive imagery releases simulated capacity, create
the baseline plan, step 300 seconds, then choose Event → Archive fulfillment.
Paste the `payload` from archive-inputs.json (do not paste its injection_time
wrapper). Confirm the mission clock is 2026-10-26T07:05:00Z before recording.
Inspect the distinct request badge, source item, profile/quality, attribution,
affected old plan, map and timeline. Replan separately and inspect the PlanDiff
and acquisition/fulfillment totals. Reload the saved mission to inspect its
preserved evidence and status. Loading an Example never injects or replans.

## Evidence and limits

Collection: sentinel-2-l2a. Selected item:
S2A_MSIL2A_20260908T091331_N0512_R050_T35SKC_20260908T141908.
Acquisition: 2026-09-08T09:13:31.024Z; cloud 0.46%; item GSD 10 m.
Search completed: 2026-10-26T05:55:02.376253Z, before satisfaction.
The original three-page search, six actual item identities, request parameters,
retrieval times and digests are in `../../imagery/athens-sentinel2-20261026/`.

Copernicus Sentinel data 2026; Copernicus Data Space Ecosystem catalogue
metadata. Scene cloud percentage does not guarantee cloud-free target pixels.
The author accepts this optical product and dated interval for an illustrative
need; item GSD is not a claim about all bands or operational suitability. No
image download, processing, product opening or pixel/content verification
occurred. [Primary sources and live verification](../../../../.doc/world-impact/d-archive-check/source-verification.md)
document the current API and attribution terms.
