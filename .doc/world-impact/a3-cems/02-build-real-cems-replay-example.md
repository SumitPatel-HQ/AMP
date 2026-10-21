# 02: Build and replay a real CEMS Example

**What to build:** A developer archives a real public activation and produces deterministic centroid-based emergency inputs. A trainee loads its dated Example offline, injects the activation at the exact time, inspects impact, and explicitly replans with source evidence and response results visible.

**Blocked by:** A3-01 — Inject and inspect CEMS arrivals.

**Status:** ready-for-agent

**Governing specification:** [A3 CEMS activation replay](spec.md).

**Branch independence:** Continue the A3 branch after A3-01. No E, C, or D code, schema, fixture, requester identity, or merge is required. Reuse A1+B archive/identifier/profile behavior through additive changes.

- [ ] Verify current CEMS public endpoints, timestamp/geometry conventions, visibility flags, redistribution terms, and attribution requirements against primary sources; document the exact selected activation code and source evidence.
- [ ] Fetch only through an explicit developer operation. Archive all required original response bytes with exact URLs, timezone-aware retrieval times, filenames, and SHA-256 checksums; refuse silent overwrites.
- [ ] Establish that the selected activation is public and non-sensitive. Reject selections whose visibility is unknown; do not publish sensitive content or credentials.
- [ ] Offline loading verifies checksums before normalization. Missing files, incomplete source records, invalid timestamps, or unsupported/ambiguous centroid geometry fail with actionable diagnostics before output publication.
- [ ] Normalize the documented WKT axis order to a valid geographic point. Use one source-provided centroid per activation, with no polygon tiling or invented centroid fallback.
- [ ] Require explicit duration, energy, storage, and optional Satellite assignment. Generate policy-versioned inputs with activation time as intended injection time and a source/id-derived request identity.
- [ ] Equal normalized duplicates collapse, conflicting activation identities fail, out-of-Scenario arrivals fail without time shifting, and fixed evidence/profile/policy produce byte-stable output in deterministic order. Publish atomically.
- [ ] Bundle a verifiable actual activation, manifest/raw evidence, generated inputs, matching stored orbital inputs, dated Scenario, and briefing. Do not treat the research's historical probe as an existing archive or invent event identifiers.
- [ ] Loading the Example makes no network request. Its documented runner creates a baseline MissionPlan, advances to and checks the exact activation instant, injects using A3-01, exposes impact, and performs replan only as an explicit separate choice.
- [ ] The dashboard/map/timeline display the real evidence, centroid approximation, required attribution, policy assumptions, and B response or unserved result after injection, replan, persistence reconstruction, and reload.
- [ ] Verify the archive-builder seam for corruption, parsing, duplicates, profiles, policy/time boundaries, and deterministic publication; verify the bundled lifecycle through MissionSession and offline replay without source archives or network access.

**Delivery boundary:** Completes A3. Excludes live polling, activation revisions, area coverage, new sensor models, and new training infrastructure.
