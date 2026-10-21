# EMSR933: Crete flood activation replay

Real activation: EMSR933, Flood in Crete, Greece; category Flood.
Event: 2026-10-01 07:00 UTC. Activation: 2026-10-04 11:02 UTC.
Source: https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR933

The source-provided coordinate is the **activation centroid; point approximation**
(longitude 24.978601792058495, latitude 35.22506250241993). Observing this
point provides no area-coverage guarantee for Crete or the eight source AOIs.

Copernicus Emergency Management Service (© European Union, 2026), EMSR933.
Adapted activation metadata; this simulation is not a Copernicus product or an
operational response commitment.

AMIS policy cems-centroid-v1 assumes priority 5 and a deadline 24 hours after
activation, independent of category. The explicit author profile assumes a
30-second exposure, 20 Wh and 100 MB, with assignment left to the planner.
The hypothetical agile imager uses a stored Landsat 8 orbital snapshot, a
60-degree off-nadir limit and 10-degree minimum Sun elevation. These are
training assumptions, not claims about Landsat 8 tasking capabilities.

Load the Example, generate windows and create a baseline MissionPlan. Advance
exactly 126120 seconds from Scenario start (2026-10-04 00:00 UTC), then inject
the event body in cue-inputs.json. Inspect impact before choosing Replan.
The CLI performs this lifecycle offline:
`python -m scripts.run_cems_crete_replay` (impact only), or
`python -m scripts.run_cems_crete_replay --replan` (explicit replan).
With these stored inputs, replan schedules the centroid at 2026-10-05 08:01:51 UTC.
B reports planned latency until the clock reaches acquisition, then achieved
latency. Less suitable windows or profiles may leave an arrival unserved.

Inspect the accepted event, Cue map marker, timeline and emergency response
metrics. Saved missions reconstruct these from the pristine Scenario and
accepted events, including recorded windows, without source archives or
network access. Reset removes the arrival. Loading alone never injects it.
