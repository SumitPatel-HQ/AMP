# 15: Mission map

**What to build:** A reviewer sees where the observation targets actually are, so the mission has geographic context instead of reading as an abstract chart.

This ticket is deliberately independent and deliberately last in priority. The map is the only component that can be removed without breaking the research claim, and it sits first in the cut order if the sprint runs behind. Build it so that removing it breaks nothing else.

**Blocked by:** 11. Can run in parallel with 12 through 14.

**Status:** ready-for-agent

- [ ] A 2D map shows the observation targets and the satellite
- [ ] Selecting a request elsewhere in the interface highlights its target on the map, and selecting a target highlights the request
- [ ] The map is a separate panel, and removing it breaks no other panel and no test
- [ ] The map is a lightweight 2D library, with no 3D globe and no Cesium
- [ ] The map never blocks or gates any part of the planning loop
