# 01: Walking skeleton, one request through to a printed plan

**What to build:** A researcher runs one command and sees a mission plan. The system loads a scenario holding one satellite and one observation request, generates one synthetic observation window for it, places the request in that window, and prints the resulting plan.

This is the thinnest complete path through the system. Every later ticket widens it rather than adding a layer beneath it. Deliberately keep the scope narrow in every dimension except coverage: one request, one window, one constraint, one planner.

Use the vocabulary in `CONTEXT.md` throughout. Follow ADR-0001, which puts the single test seam at the session facade rather than at HTTP.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Domain types exist for the scenario, satellite, observation request, observation window, scheduled action, and mission plan, named as `CONTEXT.md` names them
- [ ] The word "task" appears nowhere as a domain term, in a type name, a field name, or a comment
- [ ] A scenario serialises to JSON, deserialises, and every value survives unchanged
- [ ] The session facade exposes loading a scenario, generating windows, and planning, and returns domain objects rather than framework types
- [ ] The synthetic window provider satisfies a window provider protocol, so an orbital provider can replace it later without touching the planner
- [ ] The greedy planner satisfies a planner protocol taking a scenario, a mission state, a set of requests, and a set of windows, and returning a plan
- [ ] The window containment check returns a structured violation carrying a reason code and the request id, never a bare boolean
- [ ] Running the demo script prints a plan holding one scheduled action
- [ ] The planner imports no web framework, no ORM, and nothing UI facing
- [ ] An integration test drives the whole path through the session facade with no HTTP involved
