# 02: Full constraint engine and multi request planning

**What to build:** A researcher loads a scenario with five to ten observation requests under binding resource limits and gets a plan that respects visibility, timing, and resources, along with a list of what could not be scheduled and why.

This widens the skeleton from one request to a real planning problem. The constraint checks come before the planner, because the explanation layer later generates its text from the reason codes these checks produce.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Six checks exist and are independently callable: window containment, deadline, overlap, projected battery, projected storage, and satellite availability
- [ ] Every check returns violations carrying a reason code and the offending request id
- [ ] One passing and one failing unit test exists for each of the six checks
- [ ] Resources project forward along the plan in time order, and an action is validated against the projection at its own start time rather than against current state
- [ ] Battery never recharges, idle drain is zero, storage never frees, and accounting floors at zero
- [ ] Five actions each costing 20 Wh are rejected when only 25 Wh remains, rather than all passing
- [ ] The planner sorts requests by priority descending, then deadline ascending, then duration ascending, then request id ascending
- [ ] The plan records every unscheduled request with a reason code
- [ ] A scenario where nothing fits produces an empty plan with a reason per request and raises no error, since there is no infeasible plan error code
- [ ] Validating a whole plan returns every violation in one call
- [ ] Two runs of the same scenario produce identical plans
- [ ] The satellite availability check is covered by a unit test built on a hand constructed unavailable state, even though no event produces that state yet
- [ ] The demo script prints a multi request plan including the unscheduled list
