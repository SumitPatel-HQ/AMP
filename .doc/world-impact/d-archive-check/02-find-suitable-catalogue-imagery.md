# 02: Find suitable catalogue imagery offline

**What to build:** A developer archives STAC search results and deterministically selects imagery against explicit request requirements. A trainee replays a real archive-satisfaction Example and sees another ObservationRequest use capacity released by the explicit replan.

**Blocked by:** D-01 — Fulfill requests through recorded archive evidence.

**Status:** ready-for-agent

**Governing specification:** [Archive-first imagery satisfaction](spec.md).

**Branch independence:** Continue the D branch after D-01. No A3, E, or C code, requester attribution, fairness metric, data, or merge is required.

- [ ] Verify current Copernicus Data Space STAC endpoint, collection/filter/pagination contracts, geometry/metadata units, access terms, and attribution against primary sources; document actual selected collection/item identities.
- [ ] An explicit developer operation completes search pagination before archiving original pages, request parameters, URLs, retrieval times, checksums, and completion metadata. A failed/partial search cannot be represented as no coverage or published as complete.
- [ ] Offline conversion verifies all checksums before selection. Require an explicit profile for allowed collections, acquisition interval, cloud percentage, ground-sample distance, required viewing limits, and author-confirmed sensor/product suitability.
- [ ] Validate actual scene-footprint coverage of the point, including its boundary, under documented geographic geometry semantics. Bounding-box overlap alone cannot qualify; unsupported/invalid geometry gives a diagnostic.
- [ ] Normalize measured metadata in documented units. Every required criterion must pass; missing or nonfinite values cannot become favorable defaults. State that scene cloud percentage does not guarantee clear target pixels or product-content suitability.
- [ ] Acquisition instants/intervals must lie wholly inside the allowed profile interval and no later than satisfaction. Archived search retrieval must be no later than satisfaction, preventing historical look-ahead without assuming availability from acquisition date alone.
- [ ] Use `archive-point-v1` selection: newest acquisition end, then lower cloud percentage, then collection/item id. Collapse exact duplicate identities and fail conflicting selected identities. No match emits a documented result with no MissionEvent.
- [ ] Require explicit injection time within the Scenario horizon and after request arrival. Reject date mismatches without shifting/clipping; publish stable generated evidence inputs atomically after all selected requests validate.
- [ ] Bundle real verifiable catalogue evidence, a manifest, explicit profile, dated Scenario, inputs, and briefing. No image download is required; state that qualification is metadata-based and no image-content verification occurred.
- [ ] The offline Example creates a baseline with competing demand, injects through D-01 at the checked intended time, exposes impact, and explicitly replans so another request demonstrably uses the released capacity. Show evidence, distinct outcome, attribution, and separate acquisition/fulfillment metrics after reload.
- [ ] Verify archive-builder corruption/pagination failures, coverage boundaries, time intervals, availability, missing metadata, thresholds, ties, duplicates, and no-match behavior. Verify the Example lifecycle and persisted replay with catalogue access and archive files unavailable.

**Delivery boundary:** Completes D. Excludes image processing/download, pixel-quality guarantees, mosaics/area coverage, live catalogue lookup, sensor modeling, automatic replanning, and changes to acquisition utility.
