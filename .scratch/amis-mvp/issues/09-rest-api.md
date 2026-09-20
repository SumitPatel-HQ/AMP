# 09: REST API

**What to build:** The working loop becomes reachable over HTTP. A caller drives the whole mission through JSON endpoints and gets the same answers the session facade gives, with the loop's order enforced and every failure carrying a machine readable code.

The routes are adapters, not logic. Follow ADR-0001: a route that schedules, validates, compares, or explains anything is a defect against it.

Build this against the cloud block event only. The events endpoint dispatches generically on event type, so the other two types need no route change when they land.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Endpoints exist for creating and reading a scenario, generating windows, planning, reading state, stepping, injecting an event, reading the stored impact, replanning, reading a plan, reading a plan's metrics, comparing two plans, and reading a plan's traces
- [ ] Every route validates its input, calls the facade, and returns a schema, with no scheduling, validation, comparison, or explanation logic in a handler
- [ ] The session holds no state between requests, and each endpoint rebuilds it from the repositories, acts, and writes back
- [ ] Loop order is enforced: windows before planning, a plan before stepping, a plan before injecting an event, with a simulation state error otherwise
- [ ] The replan request carries the plan version the caller believes is current, and a mismatch returns a conflict with the plan version conflict code, so a double click cannot write two next versions
- [ ] Errors return an envelope carrying a code, a message, and a details object, drawn from the six codes, with no infeasible plan code among them
- [ ] The whole mission flow runs through integration tests over the ASGI transport
- [ ] The generated OpenAPI schema documents every error code and is the source of truth for the frontend types
- [ ] The events endpoint dispatches on event type generically, so adding the remaining two types requires no route change
