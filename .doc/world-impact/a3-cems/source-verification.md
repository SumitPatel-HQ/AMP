# CEMS ticket 02 source verification

Verified 2026-10-21 against the owning service and its live API.

- [Rapid Mapping API contract](https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/)
  documents both public endpoints, the `sensitive` boolean (`false` means public),
  event and activation timestamps as UTC, and centroid as WKT POINT (lon lat).
- [General harvest contract](https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/)
  also explicitly specifies geographic longitude-latitude order. The adapter accepts
  only a finite geographic two-dimensional POINT, with no polygon fallback or tiling.
- [Terms](https://mapping.emergency.copernicus.eu/terms-and-conditions/)
  permit reproduction, distribution, public communication, adaptation and combination
  of CEMS On-Demand Mapping information, subject to attribution and applicable law.
  Data carry no quality/suitability warranty. Third-party imagery rights remain separate;
  this bundle contains activation metadata, not imagery or downloaded mapping products.
- [Citation guidelines](https://mapping.emergency.copernicus.eu/about/citation-guidelines/)
  require service/European Union credit and activation identification. Adapted metadata
  and simulation assumptions are identified in the briefing and existing evidence panel.

Selected **EMSR933, Flood in Crete, Greece**. The detail response has
`sensitive: false`, category Flood, eventTime `2026-10-01T07:00:00`, activationTime
`2026-10-04T11:02:00`, and centroid
`POINT (24.978601792058495 35.22506250241993)`.
Offset-free source timestamps are interpreted as UTC because the API contract says UTC;
explicit offsets are normalized to UTC. Contradictory event-after-activation values fail.
Visibility is required on every record and never inferred from endpoint reachability.

The complete original detail response is sufficient to establish identity, visibility,
dates and centroid. No summary response is needed for conversion. It is preserved at
`amis/data/cues/crete-emsr933-20261004/response.json`, with exact requested URL,
timezone-aware retrieval time, filename and SHA-256 in the adjacent manifest.
All original bytes are checksummed before JSON parsing. The earlier research probe
of EMSR932 was not used as an archive or evidence for this Example.

The dated Scenario embeds the matching stored Landsat 8 orbital inputs. It uses the
existing bundled ephemeris and does not fetch new orbital data. The hypothetical
imager, resources and daylight/off-nadir limits are explicitly AMIS assumptions.

Only `python -m scripts.fetch_cems_archive` accesses the network. It validates public
status before writing any response and refuses existing directories. Conversion uses
the shared checksum archive loader, source/id identity, explicit imaging profile and
atomic input publisher. Replay uses the accepted evidence and recorded windows.
