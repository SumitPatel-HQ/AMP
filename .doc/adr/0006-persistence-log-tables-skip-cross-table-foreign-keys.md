# Persistence log tables skip cross-table foreign keys

`ObservationWindowRepository`, `PlanRepository`, `EventRepository`, `ImpactRepository`, and `TraceRepository` each replace their whole table for a scenario on every save. `MissionSessionStore.save()` passes one connection to all of them and commits the SQL changes in one transaction. An impact names the event and the plan it was evaluated against; a decision trace names a plan and, sometimes, an event. We decided those references stay plain, indexed strings rather than foreign keys.

## Considered options

A `RESTRICT` foreign key from `impacts.evaluated_plan_id` to `mission_plans.id` looks like free correctness. It is not free here, because `PlanRepository.replace_for_scenario` deletes every plan row for a scenario and reinserts the same history plus, usually, one new version, in one transaction. The delete briefly removes a plan id that an already-committed impact still references, and `RESTRICT` rejects that delete outright, even though the row reappears immediately after. Every ordinary save after the first event would fail.

A `CASCADE` foreign key trades that failure for silent data loss. Deleting a plan row to replace it would cascade-delete every impact and trace that named it, and the reinsert a few lines later does not undo that cascade. An operator would watch their explanation history disappear on the very save that was supposed to add a decision trace to it.

Both problems trace back to the same cause: `replace_for_scenario` is a whole-table replace, not a diff, and it runs once per table rather than once for every table together. Diffing each table to insert-or-update only the changed rows would remove the hazard, but every one of these tables can have a row change in place, such as `scheduled_actions.status` moving from `planned` to `started` as the clock advances, so the diff has to compare full row contents, not just ids. That is meaningfully more code for a guarantee the database cannot enforce differently anyway, since the tables are written in a fixed order within one HTTP request rather than one transaction spanning all of them.

## Consequences

Scenario ownership stays a real foreign key everywhere (`ON DELETE CASCADE` to `scenarios.id`), because a scenario is added once and never deleted by any code path, so that cascade never fires in practice. A plan's own `scheduled_actions` and `unscheduled_entries` are deleted explicitly by the plan repository before it reinserts them, in the same transaction as the plan rows, rather than left to a database-level cascade, because SQLite does not enforce `ON DELETE CASCADE` unless a pragma is set per connection and PostgreSQL does; relying on cascade there would make the test suite and production disagree about whether orphaned rows get cleaned up.

A SQL reader cannot observe the intermediate deletes in `MissionSessionStore.save()` because the store commits the replacements together. Direct calls to an individual repository can still change one table without its related records. Such callers must coordinate those writes or use the store.

`MissionSessionStore.save()` now writes all SQL records in one transaction. A failed save rolls back the plan, windows, events, impacts, traces, and state together. In-memory repositories still use their own locks and do not offer a cross-repository transaction.
