# Synthetic conjunction training replay (E-01)

Run from the repository root:

```powershell
.venv/Scripts/python.exe scripts/run_synthetic_conjunction_replay.py
```

The script emits a pristine Scenario, the accepted MissionEvent, pre-replan Impact, and post-replan DecisionTraces as JSON. It advances the MissionSession clock to the explicit injection instant, checks it, injects the outage, asserts that injection leaves the plan unchanged, and separately replans. It then reconstructs from the pristine Scenario and recorded event with the network forbidden and checks the same impact and explanations.

This is **synthetic training evidence**, not an archived conjunction or a dated orbital demonstration. The stored catalogue identity only exercises identity matching. The canonical observation windows are synthetic and do not use orbit propagation. Counterpart 99999, probability, distance, TCA, and padding are invented training inputs. No real historical provenance or maneuver is claimed.

To inject into an API mission, POST the emitted `event` object's `event_type` and `payload` to `/scenarios/{scenario_id}/events` after loading the emitted Scenario, generating windows, creating a plan, and stepping to the emitted `event_time` (60 seconds after Scenario start). The production provider recognizes the canonical request IDs. Inspect `/scenarios/{scenario_id}/impact` using the API's documented impact route, then invoke the explicit replan operation. Event inspection, impact, and Satellite state show the evidence; comparison traces show the causal reason and event link.

The optional payload key `conjunction` is one complete group; omit it for a manual outage. UTC dates may be serialized as `Z` or `+00:00`. Required keys and units are documented in ADR-0018 and OpenAPI. The entire assumed outage must fit the Scenario horizon and injection must be no later than its start. The policy threshold 0.0001 does not confirm a maneuver. Orbit change, fuel use, delta-v, and maneuver confirmation are not modeled.
