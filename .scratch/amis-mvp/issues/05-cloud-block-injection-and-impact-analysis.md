# 05: Cloud block injection and impact analysis

**What to build:** A researcher injects a cloud block over one observation window and sees exactly which scheduled actions it broke, before deciding whether to repair anything.

Injection and replanning stay separate operations. That separation is what makes the demonstration a cause and then an effect rather than a black box, and it lets the impact be inspected on its own.

**Blocked by:** 03.

**Status:** ready-for-agent

- [ ] Injecting a cloud block names a request and one of its windows, and marks that window invalid with a reason
- [ ] Injection records a mission event carrying its id, the scenario id, the type, the time, and the payload
- [ ] Injection never triggers replanning
- [ ] An impact record is written at injection time and holds the event id, the id of the plan it was evaluated against, the frozen action ids, the valid unfrozen action ids, the invalid unfrozen action ids, and the reason codes behind the invalid ones
- [ ] Reading the impact later returns the stored record rather than recomputing it, so the answer does not change with when it is read
- [ ] An action is frozen when its start time is at or before the current simulated time, which includes an action that started before the event and has not yet finished
- [ ] Impact splits unfrozen actions two ways only, valid and invalid, with no third class
- [ ] Only the action using the blocked window becomes invalid, absent real knock on resource or timing effects
- [ ] The scenario object is unchanged after injection
- [ ] The demo script prints which action broke and the reason code
