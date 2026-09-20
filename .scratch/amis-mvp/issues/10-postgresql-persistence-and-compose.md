# 10: PostgreSQL persistence and compose

**What to build:** A researcher restarts the backend and their experiment is still there. Plans, events, impacts, and traces survive, and the whole stack starts with one command.

The repository protocols already exist from the in memory implementation. This swaps the implementation behind them and changes nothing above.

Postgres joins Docker Compose in this change rather than earlier. A database service that nothing connects to invites an hour of investigation into whether persistence is wired.

**Blocked by:** 09.

**Status:** ready-for-agent

- [ ] SQLAlchemy repositories implement the same protocols the in memory ones implement, and no caller above the repository boundary changes
- [ ] Migrations cover scenarios, satellites, observation requests, observation windows, mission states, mission plans, scheduled actions, mission events, impacts, decision traces, and experiment results
- [ ] No ORM object reaches the planner; repositories convert persistence records into domain models at the boundary
- [ ] Id counters recover from the persisted records rather than from memory, so they survive a restart without colliding
- [ ] After a restart, version 1, the event, version 2, the impact, and the traces are all still retrievable
- [ ] Postgres is added to Docker Compose in this same change, alongside the database URL setting
- [ ] Nothing in the stack requires an API key, and the core workflow still runs offline
