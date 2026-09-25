# The scenario is immutable and the event log is the replay unit

An `EMERGENCY_TASK` event introduces a new observation request part way through a mission, and the obvious implementation adds that request to the scenario. We decided the scenario never changes after load. The event log is the record of everything that happened afterwards, and the request pool at any simulated instant is the scenario's requests plus every request an applied event introduced. Replay means loading the untouched scenario and reapplying its events in order.

## Considered options

Mutating the scenario is simpler and is what most readers will expect. We rejected it because reproducibility is the project's core claim, and a mutable scenario makes "rerun the same scenario" mean different things before and after an event. The determinism requirement would then have no fixed subject.

## Consequences

The emergency event payload carries its observation windows explicitly rather than calling the `WindowProvider` at injection time, so that the event log alone is enough to reconstruct the mission. Generating windows at injection is the right extension once an orbital provider exists, and it fills the same field.

`reset` clears plans, events, traces, and impacts along with the clock, returning the session to the moment of load. A partial reset that kept plans or events would produce a state that no scenario and event log pair can reproduce, which would quietly break replay.

A future reader may be tempted to let an event write through to the scenario for convenience. That change would invalidate every saved experiment.
