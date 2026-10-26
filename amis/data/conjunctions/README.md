# SOCRATES archive and developer operations

Verified against primary provider documentation on 2026-10-26:

- [SOCRATES format](https://celestrak.org/SOCRATES/socrates-format.php): headered RFC 4180 CSV, both catalogue identities, UTC TCA, kilometer range. `MAX_PROB` scientific notation is parsed directly as a fraction, never divided by 100. Unsupported or absent values produce diagnostics and cannot qualify.
- [SOCRATES methodology](https://celestrak.org/SOCRATES/): this is a screening prediction, with maximum probability calculated under source assumptions; it is not proof of a collision or maneuver.
- [Usage policy](https://celestrak.org/usage-policy.php): download once per update; the currently stated SOCRATES cadence is 10–11 hours. We conservatively enforce 11 hours and stop on every non-200 response, including redirects. No automatic retries. A longer Retry-After extends the cooldown.

Access is public without credentials. The cited policy describes free access subject to usage limits; no separate SOCRATES redistribution license or mandatory attribution wording was established from these pages. We preserve source identity and credit CelesTrak and Dr. T.S. Kelso throughout rather than claiming a public-domain license.

Only this explicit developer operation contacts the report endpoint:

```powershell
.venv/Scripts/python -m scripts.fetch_socrates_archive --archive-dir amis/data/conjunctions/NEW-DATE
```

Keep the default `outputs/socrates-fetch-state.json` shared across all destination directories; do not delete or change it to bypass cooldown. It records attempted requests before network access, including failures. A lock prevents concurrent attempts sharing that state. Investigate a stale lock after interruption manually. Coordinate with other machines sharing a public IP. Recheck the linked policy before future refreshes; the verified interval is versioned in metadata, not a permanent claim about provider policy. Existing archive directories are never replaced. Original response bytes, response filename, exact URL, headers, retrieval time, checksum, and next allowed fetch time are preserved. Publication and coverage remain null unless independently established; HTTP metadata is not silently promoted to source publication.

The 2026-10-26 archive contains the complete 22,187,030-byte response (195,380 rows); selected encounter identities and the dated orbital provenance are documented in the Example briefing. Keep raw evidence byte-exact across platforms. Offline loading verifies SHA-256 before parsing. The Scenario stores its own normalized orbital copy.

Rebuild the bundled inputs to a **new** output path:

```powershell
.venv/Scripts/python -m scripts.build_socrates_inputs --manifest amis/data/conjunctions/2026-10-26/manifest.json --scenario amis/data/examples/socrates-flock-2026-10-27/scenario.json --injection-time 2026-10-27T05:00:00+00:00 --pre-padding-s 3600 --post-padding-s 3600 --satellite SAT-FLOCK --encounter socrates:58418:62666:2026-10-27T06:13:09.293000+00:00 --encounter socrates:58418:62666:2026-10-27T07:47:05.620000+00:00 --output outputs/socrates-inputs.json
```

`--mapping` optionally takes a JSON object from NORAD identity to selected Satellite id when several Scenario Satellites reuse an identity. Names never control matching. Repeat `--satellite`/`--encounter` to select; omission considers all, which can intentionally fail if qualifying rows do not fit the horizon. Every selected encounter receives the explicit invocation's injection time and padding; use separate invocations for different author policies. Output records both source orientation and canonical pair/TCA identity. Exact normalized duplicates collapse; selected conflicts fail. Conversion validates everything before exclusively publishing a complete file. Different encounters stay distinct; their overlapping intervals are applied by MissionSession.

The builder enforces threshold 0.0001 for `socrates-outage-v1`. `--threshold` makes that value explicit; a different threshold requires a separately defined versioned policy, rather than silently relabeling a different rule as v1.
