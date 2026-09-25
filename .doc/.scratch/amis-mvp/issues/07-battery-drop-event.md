# 07: Battery drop event

**What to build:** A researcher drops the satellite's battery mid mission and watches the forward plan collapse with a reason attached to every request it could no longer fit, while the observation already in flight still completes.

This is the event that exercises ADR-0003. A frozen action that the drop made unaffordable must not make the plan permanently invalid.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Injecting a battery drop names a satellite and a new battery value and updates the mission state to exactly that value, with no clamping to protect in flight work
- [ ] An impact record is written naming the plan it was evaluated against
- [ ] A frozen in flight action that can no longer afford itself still completes, and the battery floors at zero
- [ ] Validating the resulting plan does not fail over that frozen action
- [ ] Unfrozen actions that no longer fit become invalid with the insufficient battery reason
- [ ] Replanning produces a plan, possibly an empty one, carrying a reason per unscheduled request rather than raising an error
- [ ] A fixture variant exists where the battery is tight enough to drop exactly one request, the lowest priority one, with the insufficient battery reason
