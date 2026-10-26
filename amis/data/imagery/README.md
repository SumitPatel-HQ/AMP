# Developer imagery archives

Only an explicit developer fetch uses the network:

```powershell
python -m scripts.fetch_imagery_archive --source-url "https://stac.dataspace.copernicus.eu/v1/search?collections=sentinel-2-l2a&bbox=23.72%2C37.97%2C23.74%2C37.99&datetime=2026-09-01T00%3A00%3A00Z%2F2026-09-10T23%3A59%3A59Z&filter-lang=cql2-text&filter=eo%3Acloud_cover+%3C%3D+20&limit=2" --archive-dir amis/data/imagery/my-new-search
```

The destination must be new. Original response bytes are preserved per page,
with request URLs/parameters, retrieval times, SHA-256 digests and pagination
completion in `manifest.json`. All pages are retrieved and validated before
the directory is published. A fetch error, unsupported pagination, cycle,
page limit, malformed response or mismatched count fails the entire operation.
No partial search is published as complete or interpreted as no coverage.

This first adapter supports CDSE STAC v1 GET searches and plain GET next links
on the same service, including relative links. POST/body/header pagination
fails explicitly. `--max-pages` bounds the operation; reaching it while a next
link remains is an error. The manifest does not prove a cryptographic catalogue
signature: it checks recorded byte integrity, requests and pagination chain.

Offline build uses no network:

```powershell
python -m scripts.build_imagery_events scenario.json --archive-manifest amis/data/imagery/my-new-search/manifest.json --requirements requirements.json --out archive-inputs.json
```

Requirements map request IDs to exactly `injection_time` and `profile`. Each
profile explicitly supplies version, allowed collections, acquisition_start,
acquisition_end, max_cloud_cover_pct, max_gsd_m and sensor_product_assertion.
Optional max_view_angle_deg limits the selected catalogue viewing angle in
degrees. For Sentinel-2, `view:incidence_angle` is preferred, with
`view:off_nadir` used only when incidence is absent or null. These are distinct
physical angles; this is an explicit metadata-selection policy, not a geometric
conversion. Invalid or over-limit incidence is never replaced by a more
favorable fallback. The initial adapter supports Sentinel-2 L1C and L2A; it
diagnoses other collections rather than inventing sensor/product suitability.

An optional `--arrival-events accepted-events.json` accepts an array of recorded
EMERGENCY_TASK MissionEvents from this Scenario. Their request identities and
event times establish pool membership. Initial requests enter at Scenario start.
Injection must follow arrival, be within the half-open Scenario interval and
not follow expiry. Date mismatches are errors; they are never shifted/clipped.

All page digests are checked before qualification, even pages without the
selected scene. Only item-level `gsd` (meters) and `eo:cloud_cover` (percent)
are used; missing required metadata fails. Acquisition intervals are retained
whole, bounded by the inclusive profile interval and satisfaction time. Search
completion retrieval must precede satisfaction. `updated`/`published` values
never establish historical availability.

Coverage follows ADR-0017: boundary-inclusive geographic point coverage against
simple Polygon exterior rings, straight longitude/latitude edges, no holes or
longitude spans of 180 degrees or more. Invalid or unsupported geometry is
diagnosed and cannot qualify. Bounding boxes are search hints only.

Selection policy `archive-point-v1` orders by newest acquisition end, lower
cloud, collection ID, then item ID. Exact item duplicates collapse. A conflicting
identity with any qualifying variant fails conversion. Rejected candidates
retain diagnostics. No-match is an explicit result with **no event**. Every
requested requirement is checked before complete deterministic output replaces
the destination atomically. The CLI protects archive, Scenario, requirements
and arrival inputs from replacement.

Cloud cover is scene metadata, not clear-target-pixel assurance. Item GSD does
not describe all bands or establish a user's need. Qualification is under an
explicit author profile; no image download or content verification occurs.
Runtime reads accepted events, never these archives.

See the [Athens Example](../examples/archive-athens-2026-10-26/README.md) and
[source verification](../../../.doc/world-impact/d-archive-check/source-verification.md).
