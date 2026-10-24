# 02: Build a SOCRATES replay Example

**What to build:** A developer archives SOCRATES predictions and deterministically converts qualifying encounters into Satellite outage inputs. A trainee replays a dated, independently verifiable Example and sees the resulting impact, replan, and source-linked explanations.

**Blocked by:** E-01 — Explain conjunction-derived outages.

**Status:** ready-for-agent

**Governing specification:** [Conjunction-derived Satellite outages](spec.md).

**Branch independence:** Continue the E branch after E-01. No A3, C, or D code, data, schema, or merge is required. Keep conjunction policy separate from emergency Cue policy.

- [ ] Verify current provider report format, units, probability representation, usage interval, access terms, and attribution against primary sources; document the selected report and encounter identities.
- [ ] An explicit developer fetch archives original bytes, exact URL, retrieval time, available source publication/coverage metadata, and SHA-256. Refuse early refreshes under the provider's current interval, silent overwrites, and tight retries after errors.
- [ ] Offline loading checks integrity before parsing. Normalize both catalogue ids, UTC TCA, nonnegative distance in kilometers, and probability in [0, 1] using documented conversion. Missing/unsupported probability produces a diagnostic and cannot silently qualify.
- [ ] Match either encounter object to stored OrbitalElements NORAD identity. Exclude unmatched rows with a summary, fail explicitly selected unmatched Satellites, and require explicit mapping when multiple Scenario Satellites reuse an identity.
- [ ] Canonicalize encounter identity across object-pair orientation; collapse exact normalized duplicates and reject conflicting selected encounters. When both objects are selected Scenario Satellites, generate one outage for each with the correct counterpart.
- [ ] Qualify using the versioned threshold policy and require explicit positive pre/post-TCA padding and injection instant. Validate injection no later than outage start, the full outage inside the Scenario horizon, and evidence available by injection. Reject mismatches without clipping or date shifting.
- [ ] Record policy, threshold, padding, mapping, encounter identity, and intended injection time in generated inputs. Fixed bytes and policy produce stable sorted output; failures leave no partially published artifact.
- [ ] Bundle a real report, matching stored orbital inputs, dated Scenario, generated inputs, and briefing. Name actual independently verifiable encounters; do not fabricate evidence or reuse incompatible report dates.
- [ ] The documented Example flow loads offline, creates a baseline, advances to and checks the intended instant, injects through E-01, exposes impact, and separately replans. Evidence and conjunction-specific explanations remain inspectable after reload.
- [ ] Verify source-builder boundary/invalid/matching cases and the bundled MissionSession lifecycle, including overlap and offline persisted replay. If no real compatible evidence can be obtained, report the blocker instead of substituting a synthetic event as historical completion.

**Delivery boundary:** Completes E. Excludes operational collision prediction/advice, real maneuver execution, trajectory changes, fuel modeling, live alerts, and restricted CDMs.
