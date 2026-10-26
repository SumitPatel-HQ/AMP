# 02: Build a SOCRATES replay Example

**What to build:** A developer archives SOCRATES predictions and deterministically converts qualifying encounters into Satellite outage inputs. A trainee replays a dated, independently verifiable Example and sees the resulting impact, replan, and source-linked explanations.

**Blocked by:** E-01 — Explain conjunction-derived outages.

**Status:** implemented and verified

**Governing specification:** [Conjunction-derived Satellite outages](spec.md).

**Branch independence:** Continue the E branch after E-01. No A3, C, or D code, data, schema, or merge is required. Keep conjunction policy separate from emergency Cue policy.

- [x] Verify current provider report format, units, probability representation, usage interval, access terms, and attribution against primary sources; document the selected report and encounter identities.
- [x] An explicit developer fetch archives original bytes, exact URL, retrieval time, available source publication/coverage metadata, and SHA-256. Refuse early refreshes under the provider's current interval, silent overwrites, and tight retries after errors.
- [x] Offline loading checks integrity before parsing. Normalize both catalogue ids, UTC TCA, nonnegative distance in kilometers, and probability in [0, 1] using documented conversion. Missing/unsupported probability produces a diagnostic and cannot silently qualify.
- [x] Match either encounter object to stored OrbitalElements NORAD identity. Exclude unmatched rows with a summary, fail explicitly selected unmatched Satellites, and require explicit mapping when multiple Scenario Satellites reuse an identity.
- [x] Canonicalize encounter identity across object-pair orientation; collapse exact normalized duplicates and reject conflicting selected encounters. When both objects are selected Scenario Satellites, generate one outage for each with the correct counterpart.
- [x] Qualify using the versioned threshold policy and require explicit positive pre/post-TCA padding and injection instant. Validate injection no later than outage start, the full outage inside the Scenario horizon, and evidence available by injection. Reject mismatches without clipping or date shifting.
- [x] Record policy, threshold, padding, mapping, encounter identity, and intended injection time in generated inputs. Fixed bytes and policy produce stable sorted output; failures leave no partially published artifact.
- [x] Bundle a real report, matching stored orbital inputs, dated Scenario, generated inputs, and briefing. Name actual independently verifiable encounters; do not fabricate evidence or reuse incompatible report dates.
- [x] The documented Example flow loads offline, creates a baseline, advances to and checks the intended instant, injects through E-01, exposes impact, and separately replans. Evidence and conjunction-specific explanations remain inspectable after reload.
- [x] Verify source-builder boundary/invalid/matching cases and the bundled MissionSession lifecycle, including overlap and offline persisted replay. If no real compatible evidence can be obtained, report the blocker instead of substituting a synthetic event as historical completion.

**Delivery boundary:** Completes E. Excludes operational collision prediction/advice, real maneuver execution, trajectory changes, fuel modeling, live alerts, and restricted CDMs.


## Delivery and verification

- Real Example: [FLOCK 4G-1 briefing](../../../amis/data/examples/socrates-flock-2026-10-27/briefing.md). The archived predictions are FLOCK 4G-1 (62666) / STARLINK-30895 (58418), TCA 2026-10-27 06:13:09.293 and 07:47:05.620 UTC. Source credit: CelesTrak SOCRATES Plus, Dr. T.S. Kelso. The source report is preserved byte-exact with checksum, response headers, retrieval time, nullable publication/coverage, and next fetch time.
- Developer operations and current provider policy: [archive guide](../../../amis/data/conjunctions/README.md). Conjunction conversion is separate from Cue policy. The v1 builder enforces threshold 0.0001 and requires positive explicit padding and injection time.
- Offline replay: `.venv/Scripts/python -m scripts.run_socrates_replay`; add `--replan` for the separate replan, optionally `--database outputs/NEW-NAME.db` for SQLite persistence. The source report and network are not needed. Tests block report reads and socket connections during persisted replay.
- Baseline has four imaging actions. Injection at 05:00 UTC leaves its version active and invalidates OBS-2 and OBS-3. Replanning preserves completed OBS-1, drops OBS-2, moves OBS-3 to 09:02:37 UTC, and retains OBS-4. Distinct overlapping encounter evidence and conjunction-specific traces survive reload.
- Full backend suite: 695 passed (40 E-02 checks). Full frontend suite: 218 passed across 22 files. TypeScript `npx tsc -b` passed. Python `mypy amis` has the exact same 44 diagnostics in 13 files as a clean export of starting commit `f4804cfda47ac107de9759c7c1a275c43cd2a4f3`; no new diagnostics. Final targeted typecheck also reports none in the new modules/scripts.
- CLI conversion reproduced the committed generated artifact byte-for-byte. `git diff --cached --check` passed.

### Standards review

No documented breaches or actionable heuristic smells found. The separate developer boundary, stored orbital inputs, MissionSession replay, and explicit replan follow the repository ADRs.

### Spec review

One finding was corrected: configurable thresholds could previously retain the v1 identity. The builder now rejects thresholds other than 0.0001. Follow-up review confirmed resolution with no new actionable regressions. No unresolved findings on either axis.
