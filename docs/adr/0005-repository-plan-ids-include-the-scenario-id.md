# Repository plan ids include the scenario id

The REST contract reads plans through `/plans/{id}`, while plan counters restart for each scenario. Without a scenario qualifier, two scenarios both produce `PLAN-001`, and the route cannot identify either plan reliably.

Repository-backed sessions use `{scenario_id}:PLAN-{number}`. For example, the first plan for `SCN-002` is `SCN-002:PLAN-001`. The numeric counter still starts at one for each scenario and recovers from that scenario's stored plans. A caller treats the full id as opaque.

Direct `MissionSession` use keeps the `PLAN-{number}` default. This preserves the facade's deterministic test output when no repository or cross-scenario lookup exists. `MissionSessionStore` supplies the scenario-qualified prefix at the persistence boundary.

## Considered options

Adding the scenario id to every plan route would remove the ambiguity, but it would change the ticket's REST contract. A global plan counter would keep short ids, but it would make one scenario's output depend on which other scenarios ran first.

## Consequences

In-memory and SQL plan repositories can look up a plan by its full id without hidden active-scenario state. PostgreSQL persistence must store the full id and recover the next number using the scenario-qualified prefix. Parent plan ids, impact records, metrics, comparisons, and traces use the same full id.
