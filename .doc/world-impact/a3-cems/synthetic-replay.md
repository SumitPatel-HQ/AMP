# Synthetic CEMS arrival walkthrough (ticket 01)

This fixture is invented training data, not a historical CEMS activation. Its code,
flood category, centroid and dates are synthetic. Stored Landsat 8 orbital inputs and
hypothetical imaging capabilities come from the existing orbital Example. The linked
Copernicus service homepage does not corroborate the invented activation. Historical
fetching, conversion and the real Example are A3-02.

From the repository root, with the project dependencies installed:

```powershell
python -m scripts.run_synthetic_cems_replay
python -m scripts.run_synthetic_cems_replay --replan
```

The first command generates the baseline, advances exactly five simulated minutes to
the synthetic activation, injects through MissionSession, and prints the accepted event
with generated orbital windows and impact. It leaves replanning explicit. The second
also replans and prints PlanDiff, DecisionTrace and ordinary emergency-response metrics.
An empty window list or an unserved arrival is a valid result. Duration 30 seconds,
energy 20 Wh and storage 100 MB are explicit synthetic imaging-profile choices.
Priority 5 and deadline activation plus 24 hours are AMIS policy `cems-centroid-v1`.

To inspect the same arrival in the running dashboard, export API bodies into a new
scratch directory (the command refuses an existing directory):

```powershell
python -m scripts.run_synthetic_cems_replay --export-dir "$env:TEMP/amis-cems-01"
$api = 'http://127.0.0.1:8000'
$fixture = "$env:TEMP/amis-cems-01"
Invoke-RestMethod "$api/scenarios" -Method Post -ContentType 'application/json' -InFile "$fixture/scenario.json"
$id = 'SCN-SYNTHETIC-CEMS'
Invoke-RestMethod "$api/scenarios/$id/windows/generate" -Method Post
Invoke-RestMethod "$api/scenarios/$id/plan" -Method Post
Invoke-RestMethod "$api/scenarios/$id/simulation/step" -Method Post -ContentType 'application/json' -Body '{"seconds":300}'
Invoke-RestMethod "$api/scenarios/$id/events" -Method Post -ContentType 'application/json' -InFile "$fixture/event.json"
```

Open or reload the dashboard and select `SYNTHETIC CEMS centroid training`. Inspect
EVT-001 in Events or its Cue marker on the map. Both show identity, category, source
and activation times, source credit/link, and “activation centroid; point approximation.”
The request and event are linked; reloading does not add a marker. Use **Replan** when
ready, then inspect the comparison, traces, Metrics and Timeline. Response begins at
the accepted activation instant; achieved response appears only when imaging starts.
An unscheduled request has null latency, and can expire after its deadline. Reset
removes the arrival and marker. Reloading before reset reconstructs the recorded evidence
and windows from persistence.

The event API accepts only the event body, not an `injection_time` envelope. It rejects
an activation whose timestamp differs from the current clock; do not rewrite source
dates to fit a Scenario. Reuse a fresh Scenario/reset before repeating this fixture.
