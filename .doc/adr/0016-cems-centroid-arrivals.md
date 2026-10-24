# CEMS activation centroids as recorded emergency arrivals

Status: accepted for A3 tickets 01 and 02.

One CEMS activation becomes one point ObservationRequest using its supplied activation
centroid. This preserves the existing point-target and utility model without implying
coverage of its AOIs. Inspection says “activation centroid; point approximation” and
states that no area-coverage guarantee is modeled. Polygon tiling was rejected because
it would multiply request counts and change utility semantics.

Policy `cems-centroid-v1` assigns priority 5 and a deadline exactly 24 hours after
activation. These are AMIS simulation assumptions, not Copernicus recommendations or
operational response commitments. Category is descriptive, not severity. An author must
supply duration, energy, storage, and any satellite assignment explicitly. Source/id
request identifiers use the existing Cue identity helper; a repeated accepted activation
is rejected even if it uses a different request id.

The additive evidence contract is `source=cems`, activation code as `source_event_id`,
`alert_level=unknown`, required `category`, `activation_time`, `source_url`, and
`centroid_policy_version`, plus optional `source_event_time`. Timestamps must be UTC
(`Z` or zero offset); source event time may not follow activation. Earthquake magnitude
and significance are forbidden. Other sources cannot carry CEMS fields. New fields
are omitted from manual and USGS payloads. The API and domain share evidence validation.

MissionSession requires activation time to equal its simulated clock, inside the
half-open Scenario interval. Before generating missing orbital windows it validates
evidence, coordinates, explicit imaging values, policy, assignment, and duplicate
identity. It records accepted identity, time, and windows, including an empty result.
The pristine Scenario stays unchanged; impact inspection and replan remain separate.
Persistence and replay use Scenario plus accepted events, without source archives or
network access; response uses the existing source-independent B metrics and timeline.

The [synthetic runner](../../scripts/run_synthetic_cems_replay.py) and
[replay instructions](../world-impact/a3-cems/synthetic-replay.md) deliberately identify
no historical activation. The homepage source link is a service reference, not evidence
of the synthetic disaster. A3-02 must verify public/non-sensitive source records and
preserve archive evidence before bundling a historical Example.

Attribution follows the owning service's [citation guidelines](https://mapping.emergency.copernicus.eu/about/citation-guidelines/)
and [terms](https://mapping.emergency.copernicus.eu/terms-and-conditions/), checked
2026-10-21: display the service name, activation year, European Union credit, activation
code, and public source link beside the evidence. AMIS policy is identified separately.

Ticket 02 adds the verified EMSR933 Crete flood Example. The developer fetch preserves
the entire public detail response, only after requiring `sensitive` to be exactly false.
The shared archive manifest records exact URL, retrieval time, filename and checksum;
offline loading verifies bytes before parsing. Source timestamps without offsets are
UTC under the documented API contract. Only two-dimensional geographic WKT POINT
centroids are supported. Equal normalized identities collapse and conflicts fail;
arrival times must remain inside the half-open Scenario interval. The shared atomic
publisher writes deterministic inputs only after the whole selection validates.
See [source verification](../world-impact/a3-cems/source-verification.md) and the
[real Example briefing](../../amis/data/examples/cems-crete-2026-10-04/briefing.md).
