# MissionSession is the single test seam

The adaptive planning loop spans simulation, constraints, planning, replanning, explanation, and metrics, and it has to be provable without a frontend. We put one in process facade, `MissionSession`, in front of the whole loop, and every integration test drives that facade rather than HTTP. FastAPI routes became thin adapters over the same facade, holding no scheduling, validation, comparison, or explanation logic.

## Considered options

Testing through HTTP with httpx as the primary seam was the obvious alternative, since it exercises the contract the frontend actually uses. We rejected it because it couples every core test to routing and serialisation, and because the API does not exist until day 3 of a three day sprint, which would leave the two days that build the loop with no test target at all.

Per module unit seams alone were also rejected. They would cover each part and never prove the loop, and the loop is the deliverable.

## Consequences

The SRD's rule that planning must not depend on FastAPI, React, or PostgreSQL becomes enforceable rather than aspirational. If a test drives the entire loop without importing FastAPI, the forbidden coupling cannot have crept in.

API contract tests still exist, but they only check that a route validates its input, calls the facade, and returns the documented schema. They are not where the loop is tested, and they should stay thin. A reviewer who finds scheduling logic in a route handler should treat it as a defect against this decision.
