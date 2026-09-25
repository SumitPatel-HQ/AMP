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
