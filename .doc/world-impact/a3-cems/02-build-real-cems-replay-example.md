# 02: Build and replay a real CEMS Example

**What to build:** A developer archives a real public activation and produces deterministic centroid-based emergency inputs. A trainee loads its dated Example offline, injects the activation at the exact time, inspects impact, and explicitly replans with source evidence and response results visible.

**Blocked by:** A3-01 — Inject and inspect CEMS arrivals.

**Status:** implemented

**Governing specification:** [A3 CEMS activation replay](spec.md).

**Branch independence:** Continue the A3 branch after A3-01. No E, C, or D code, schema, fixture, requester identity, or merge is required. Reuse A1+B archive/identifier/profile behavior through additive changes.

- [x] Verify current CEMS public endpoints, timestamp/geometry conventions, visibility flags, redistribution terms, and attribution requirements against primary sources; document the exact selected activation code and source evidence.
- [x] Fetch only through an explicit developer operation. Archive all required original response bytes with exact URLs, timezone-aware retrieval times, filenames, and SHA-256 checksums; refuse silent overwrites.
- [x] Establish that the selected activation is public and non-sensitive. Reject selections whose visibility is unknown; do not publish sensitive content or credentials.
- [x] Offline loading verifies checksums before normalization. Missing files, incomplete source records, invalid timestamps, or unsupported/ambiguous centroid geometry fail with actionable diagnostics before output publication.
- [x] Normalize the documented WKT axis order to a valid geographic point. Use one source-provided centroid per activation, with no polygon tiling or invented centroid fallback.
- [x] Require explicit duration, energy, storage, and optional Satellite assignment. Generate policy-versioned inputs with activation time as intended injection time and a source/id-derived request identity.
- [x] Equal normalized duplicates collapse, conflicting activation identities fail, out-of-Scenario arrivals fail without time shifting, and fixed evidence/profile/policy produce byte-stable output in deterministic order. Publish atomically.
- [x] Bundle a verifiable actual activation, manifest/raw evidence, generated inputs, matching stored orbital inputs, dated Scenario, and briefing. Do not treat the research's historical probe as an existing archive or invent event identifiers.
- [x] Loading the Example makes no network request. Its documented runner creates a baseline MissionPlan, advances to and checks the exact activation instant, injects using A3-01, exposes impact, and performs replan only as an explicit separate choice.
- [x] The dashboard/map/timeline display the real evidence, centroid approximation, required attribution, policy assumptions, and B response or unserved result after injection, replan, persistence reconstruction, and reload.
- [x] Verify the archive-builder seam for corruption, parsing, duplicates, profiles, policy/time boundaries, and deterministic publication; verify the bundled lifecycle through MissionSession and offline replay without source archives or network access.

**Delivery boundary:** Completes A3. Excludes live polling, activation revisions, area coverage, new sensor models, and new training infrastructure.

## Delivery

- Real activation EMSR933 (Flood in Crete, Greece), archived with public visibility,
  original bytes, URL, UTC retrieval time and SHA-256. Source verification:
  [evidence and terms](source-verification.md).
- Offline builder: `python -m scripts.build_cue_events` with the CEMS manifest,
  explicit profile and `--all`. Developer-only fetch: `python -m scripts.fetch_cems_archive`.
- Registered Example `cems-crete-2026-10-04` includes stored orbital inputs,
  dated Scenario, deterministic inputs and briefing. Run
  `python -m scripts.run_cems_crete_replay`, adding `--replan` explicitly.
- Verification: 523 backend tests and 201 frontend tests pass; TypeScript,
  production build and lint pass (three warnings in unchanged frontend files).
  Python mypy has the same 32 errors in the same eight files as starting commit
  6703f0b under the same current checker; no new diagnostics.
- MissionSession tests cover actual archive regeneration, exact arrival, impact,
  explicit replan, achieved response, SQLite reconstruction, reset and recorded-event
  replay with archive loading and network access forbidden. Dashboard evidence tests
  use the actual generated input and verify credit, centroid and deduplication.
- Standards review found and corrected a clock-advance typo in the briefing and
  README (39720 seconds). Spec review reported no actionable findings.
- Live dashboard checks confirmed Example loading and briefing, baseline plan,
  exact-time HTTP injection, impact and evidence/attribution, explicit UI replan,
  B planned response (20 h 59 min 51 s), reload/reselection and reset. Existing
  map rendering may fetch basemap tiles; source loading/conversion/replay remain
  offline. Git attributes preserve archived and generated bytes on Windows checkout.
