# 03: Simulation clock, resource accounting, expiry, and lifecycle

**What to build:** A researcher advances mission time and watches the state change. Actions start and complete, battery drains, storage fills, requests whose deadlines pass are lost, and the mission reaches a definite end.

This is what makes a plan something that happens rather than something that exists, and it introduces the frozen and expired properties that replanning depends on later.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] Stepping advances the clock by a given number of seconds
- [ ] Actions become started and then completed as simulated time passes them, and battery and storage change as observations execute
- [ ] The mission state is a value snapshot carrying the clock, battery, storage, availability, active event ids, completed request ids, and a mission complete flag, rather than a mutable object modules edit
- [ ] A request whose deadline passes with no completed action becomes expired, and expiry is permanent
- [ ] Expired requests are excluded from every later planning problem
- [ ] Expiry is visible through the request's own status, since a decision trace for expiry is deferred
- [ ] A step that would cross the scenario end time clamps at the end and marks the mission complete
- [ ] A further step after the mission completes raises a simulation state error
- [ ] Resetting returns the session to the moment of load, clearing plans, events, traces, and impacts along with the clock and resources
- [ ] The same scenario and the same step sequence produce an identical final state across repeated runs
- [ ] The demo script steps through a mission and prints the state transitions
