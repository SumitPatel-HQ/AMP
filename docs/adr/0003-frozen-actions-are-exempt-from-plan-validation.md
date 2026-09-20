# Frozen actions are exempt from plan validation

An action is frozen once its start time is at or before the current simulated time, and replanning may never move, drop, or recost it. We decided that `validate_plan` covers unfrozen actions only. A frozen action records what happened rather than claiming it was affordable, so validating it asks the system to relitigate the past.

## Considered options

Validating the whole plan is the obvious reading of "the revised plan must be feasible". It fails on a reachable case. If a `BATTERY_DROP` sets the battery to 35 Wh while an action needing 40 Wh is already in flight, that action is frozen and will complete, but a whole plan validation would fail forever over something nobody can change. Every subsequent plan version would inherit the failure.

Clamping the event so the battery can never fall below what in flight actions need was also rejected. It silently rewrites the user's input, so the state panel would show 38 Wh after they asked for 35.

## Consequences

Resource accounting floors at zero. In the case above the observation completes, the battery reaches zero, and every unfrozen action then fails with `INSUFFICIENT_BATTERY`, producing an empty forward plan. That is the correct result and it makes a good demonstration, because the empty plan carries a reason code per request rather than an error.

A reader who sees validation skipping part of a plan will assume it is a bug. It is not. Extending validation to frozen actions reintroduces the permanent failure described above.
