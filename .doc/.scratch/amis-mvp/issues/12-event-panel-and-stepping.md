# 12: Event panel and stepping

**What to build:** A reviewer advances mission time from the browser, then blocks a specific observation window with a cloud event chosen from dropdowns, and sees which scheduled actions that broke.

The dropdowns are required rather than convenient. Without them nothing in the interface reveals which windows exist, and the whole point is that a reviewer never opens a terminal or reads JSON.

**Blocked by:** 11.

**Status:** ready-for-agent

- [ ] Stepping the simulation works from the browser and the state panel updates to match
- [ ] A cloud block target is chosen through a request dropdown followed by a window dropdown populated from that request's windows
- [ ] No window id is ever typed by hand
- [ ] The impact appears after injection, showing which actions became invalid and the reason for each
- [ ] Injecting an event does not replan, and the interface does not imply that it did
- [ ] The mission complete state and a rejected step past the end both show as readable messages
