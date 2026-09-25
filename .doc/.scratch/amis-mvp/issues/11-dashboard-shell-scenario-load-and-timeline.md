# 11: Dashboard shell, scenario load, initial timeline, and state panel

**What to build:** A reviewer opens a browser, loads the demo scenario, generates a plan, and sees it drawn on a mission timeline beside a live readout of simulated time, battery, and storage.

One operational screen, no navigation. The panel layout here is what every later frontend ticket mounts into, so establish it properly.

World Monitor informs the shape of this screen and nothing else. It is licensed AGPL-3.0-only, so no code and no assets come from it.

**Blocked by:** 09.

**Status:** ready-for-agent

- [ ] One screen shows everything, with panels mounting independently over a shared layout so one can be added, reordered, or removed without touching the others
- [ ] Loading the demo scenario and generating a plan both work from the browser
- [ ] A timeline draws the plan's scheduled actions
- [ ] A state panel shows the simulated time, battery, storage, and the active event
- [ ] Frontend types derive from the generated OpenAPI schema rather than being hand written
- [ ] The dashboard refetches only when the user acts and never polls
- [ ] The theme is dense and dark, with colour reserved for state and change rather than decoration
- [ ] API errors appear as readable messages carrying their codes
- [ ] No code, stylesheet, or asset is copied from World Monitor
