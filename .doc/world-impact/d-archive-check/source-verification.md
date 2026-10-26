# D-02 source verification — 2026-10-26 UTC

This implementation rechecked primary documentation and made unauthenticated
live metadata requests. It did not download an image product. Search response
bytes are committed under `amis/data/imagery/athens-sentinel2-20261026/`.

## API and observed contracts

The [CDSE STAC documentation](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
identifies `https://stac.dataspace.copernicus.eu/v1/` as the current service
and deprecates the older catalogue-host STAC endpoint. It documents collection
queries, GET/POST searches and CQL2/query/fields/sort extensions. This adapter
uses GET searches only, without field suppression, so footprint and required
metadata remain available.

Live probes of the [root](https://stac.dataspace.copernicus.eu/v1/),
[Sentinel-2 L2A collection](https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a)
and its [queryables](https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a/queryables)
succeeded. The collection's license value was `other` with a link to the
Sentinel legal notice. Its cloud queryable explicitly describes percent with
bounds 0–100. Actual selected items carry item-level `gsd`, `eo:cloud_cover`,
acquisition timestamps, Polygon geometry and self links.

The archived GET search used collection sentinel-2-l2a, bbox
23.72,37.97,23.74,37.99, acquisition September 1–10, 2026, CQL2 text
`eo:cloud_cover <= 20`, and page limit 2. The exact encoded URL and each actual
next URL are preserved in the manifest. Three pages returned two items each;
the last page had no next link. Pagination links were method GET with a token
in the URL. No authentication was needed for these catalogue requests; this
does not imply anonymous image-product download access.

The [STAC Item Search specification](https://raw.githubusercontent.com/radiantearth/stac-api-spec/v1.0.0/item-search/README.md)
defines next-link pagination and optional method/header/body/merge controls.
This first integration follows plain GET next links, including relative URLs,
and rejects unsupported controls. It validates page counts, returned counts,
optional matched counts, retrieval order and chain termination before publishing.
These checks establish completion of the recorded response chain, not a
guarantee about unseen catalogue records or future catalogue consistency.

## Geometry, quality and time interpretation

[STAC Items](https://raw.githubusercontent.com/radiantearth/stac-spec/v1.1.0/item-spec/item-spec.md)
use GeoJSON geometry and support acquisition instants or start/end intervals.
AMIS retains the full interval, ranks its end, and uses straight geographic
longitude/latitude polygon edges with inclusive boundary point coverage.
This deliberately restricted runtime rejects holes, MultiPolygon, invalid
rings and longitude spans of 180 degrees or more. Search bbox overlap alone
cannot qualify. The six actual footprints supported this interpretation and
covered the Athens target at 23.73 E, 37.98 N.

[STAC common metadata](https://raw.githubusercontent.com/radiantearth/stac-spec/v1.1.0/commons/common-metadata.md)
defines `gsd` in meters and explains that nominal GSD can vary with wavelength
and geometry. AMIS uses the item's measured metadata, not a collection summary
or an asset selected for its most favorable resolution. The author must
explicitly accept the sensor/product need.

The [EO extension](https://raw.githubusercontent.com/stac-extensions/eo/v2.0.0/README.md)
defines scene cloud percentage. It does not certify clear pixels at the target.
The [view extension](https://raw.githubusercontent.com/stac-extensions/view/v1.0.0/README.md)
distinguishes sensor off-nadir and surface incidence angles. Optional AMIS
max_view_angle_deg uses only view:off_nadir. These CDSE items supply incidence
angle, so the Example requires no off-nadir limit. Missing required values
never receive favorable defaults.

Availability is established conservatively from completion of the archived
search: `2026-10-26T05:55:02.376253+00:00`. Satisfaction occurs later at
07:05 UTC that day. Item acquisition, mutable updated/published fields and
processing times are not historical-availability proofs. The Scenario is
dated accordingly; no date is shifted to simulate an earlier catalogue.

## Actual catalogue identities

All six items belong to sentinel-2-l2a:

- S2A_MSIL2A_20260908T091331_N0512_R050_T35SKC_20260908T141908
- S2A_MSIL2A_20260908T091331_N0512_R050_T34SGH_20260908T141908
- S2C_MSIL2A_20260906T090551_N0512_R050_T35SKC_20260906T124208
- S2C_MSIL2A_20260906T090551_N0512_R050_T34SGH_20260906T124208
- S2B_MSIL2A_20260901T090549_N0512_R050_T35SKC_20260901T113204
- S2B_MSIL2A_20260901T090549_N0512_R050_T34SGH_20260901T113204

The [selected item](https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a/items/S2A_MSIL2A_20260908T091331_N0512_R050_T35SKC_20260908T141908)
was acquired 2026-09-08T09:13:31.024Z with cloud 0.46% and item GSD 10 m.
The same-instant T34SGH item has cloud 0.92%; the other four acquisitions are
older. Thus archive-point-v1 selects T35SKC. Its source is original page 1,
SHA-256 `f792d85f091258a2ade3dc71966439352baa9353368fa13b3919428372f1f6b0`.
The event carries that digest and enough normalized evidence for replay
without the archive; the manifest preserves every page's digest separately.

## Access and source credit

The [CDSE terms](https://dataspace.copernicus.eu/terms-and-conditions)
separate Sentinel data access from other portal materials and link the
[European Commission Sentinel legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).
The notice permits reuse/distribution subject to its conditions, requires
source attribution and disclaims quality/suitability warranties. Its credit
forms distinguish unchanged data from adapted data. This repository preserves
the Sentinel catalogue responses unchanged; it does not redistribute portal
page text, imagery, previews or downloaded products.

The recorded source credit is “Copernicus Sentinel data 2026; Copernicus Data
Space Ecosystem catalogue metadata”. Normalized AMIS evidence and synthetic
planning decisions are identified separately. Any future product processing or
broader collection integration must recheck its own terms; no general license
inference is made from the collection's `other` value.
