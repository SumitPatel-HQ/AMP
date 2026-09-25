# 08: Emergency request event

**What to build:** A researcher injects an urgent high priority observation request part way through a mission and watches it take a slot, displacing existing work, with the displacement explained and the changed request pool reported honestly.

This is the event that exercises ADR-0002. The scenario must not change, because it is the fixed subject that reproducibility depends on.

The event type keeps its wire name, which contains the word this project otherwise bans as a domain term. Its documentation says request.

**Blocked by:** 06. Can run in parallel with 07.

**Status:** ready-for-agent

- [ ] The event payload carries a complete observation request together with its explicit observation windows, and the window provider is not called at injection time
- [ ] The scenario object is unchanged after injection
- [ ] The request pool at any instant is the scenario's requests plus every request an applied event introduced
- [ ] Loading the untouched scenario and reapplying the event log in order reproduces the same mission
- [ ] Replanning considers the new request and may displace an existing one
- [ ] A displaced request receives a trace with the displaced by competing request reason, which is the renamed code, since a request at priority 5 ties with existing priority 5 work and wins on the deadline tiebreak rather than on priority
- [ ] Metrics results for the two versions carry different request pool sizes, and the comparison flags the mismatch rather than presenting the utility rise as a straight improvement
- [ ] A fixture variant exists where a priority 5 emergency request displaces at least one existing request
