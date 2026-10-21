# Third-Party Notices

AMIS was designed with four reference projects open for study, per
`.doc/AMIS_REDESIGN_CONTEXT.md` section 13. This file records what each
one actually contributed, so a reviewer can check licensing obligations
without re-auditing the source tree.

**No third-party source code is copied or adapted anywhere in this
repository.** Every reference below informed AMIS's design at the
concept level only (visual language, panel layout, a shared time axis,
a provider/adapter boundary). Where a reference's approach is followed
closely enough to name in code, the comment says so and states plainly
that it is a conceptual reference, not adapted source — see
`frontend/src/index.css` (World Monitor's dark operations-console
palette) for the one example.

| Reference | Repository | License | What AMIS actually did |
| --- | --- | --- | --- |
| World Monitor | `koala73/worldmonitor` | AGPL-3.0 | Conceptual reference for the dense panel shell, the dark visual language, and the MapLibre + deck.gl overlay approach used by `frontend/src/map/`. No file matches World Monitor's source; AMIS's map layer builders, panel grid, and CSS are original. |
| NASA Open MCT | `nasa/openmct` | Apache-2.0 | Conceptual reference for a single shared time axis with a now marker, activity swimlanes, and event markers, used by `frontend/src/timeline/` and `frontend/src/panels/PlanTimeline.tsx`. The Open MCT plugin architecture was not adopted. |
| orbit.ctrl | `patrickkuei/Satellite-Mission-Control-Dashboard` | See upstream repository | Weak conceptual reference for pairing a data-fetching hook with a small selection store, reflected loosely in `frontend/src/state/useMissionSession.ts`. |
| openmct-mcws | `NASA-AMMOS/openmct-mcws` | See upstream repository | Weak conceptual reference for a provider/adapter boundary between UI and services, reflected loosely in `amis/repositories.py`'s protocol-based repositories. |

Because nothing is materially adapted, this repository carries no
AGPL (or other reference-project) licensing obligation and needs no
`LICENSE` file granting rights to reference-project source. If a future
change does adapt actual reference source rather than just its
concepts, update this table with the specific file, the license terms
that apply, and add the required notice at the top of the adapted file
itself.

## Data sources

| Source | What AMIS used | License / terms | Where |
| --- | --- | --- | --- |
| U.S. Geological Survey, Earthquake Hazards Program GeoJSON feed | Archived earthquake event `us6000u0xi` ("102 km NE of Norsup, Vanuatu", M6.3, 2026-10-08), used to generate the bundled USGS Vanuatu earthquake replay Example's emergency arrival. | USGS-authored data is in the U.S. public domain; USGS requests credit as `U.S. Geological Survey`. See https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits. | Archive and manifest: `amis/data/cues/vanuatu-us6000u0xi-20261008/`. Example bundle: `amis/data/examples/usgs-vanuatu-2026-10-08/`. Credit and the AMIS simulation-policy notice are displayed beside cue evidence in the dashboard and in the Example's briefing. See [ADR-0015](../adr/0015-usgs-cue-replay.md). |

AMIS's earthquake priority, deadline, and imaging-resource values applied
to this data are AMIS simulation policy (`usgs-earthquake-v1`), not USGS
recommendations; this is stated beside the credit wherever the data is
shown.
