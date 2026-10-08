# 03: Bundle a real earthquake replay Example

**What to build:** A trainee can load a bundled, dated earthquake Example offline, create a baseline MissionPlan, advance to the real cue instant, inject it, inspect Impact, and choose to replan through the existing lifecycle controls.

**Blocked by:** 01: Build reproducible USGS cue inputs; 02: Inject, inspect, and map evidence-bearing emergency arrivals.

**Status:** ready-for-agent

**Scope:** This ticket belongs to the A1+B-only implementation batch. Other world-impact research features remain outside this batch and require separate planning; completing these tickets does not complete the research roadmap.

- [ ] Select an independently verifiable real USGS earthquake and finish this ticket with its exact source event identifier, source URL, and named committed archive artifact documented. Do not invent a September 28 probe event or assume the mutable feed still contains it. Use a preserved probe record only if its evidence is actually found.
- [ ] Bundle raw evidence, integrity manifest, explicit imaging profile, generated cue input, dated Scenario, and stored orbital inputs. The Example uses matching dates, begins before the earthquake to permit a baseline plan, and has enough horizon to demonstrate a response.
- [ ] The briefing names the actual earthquake and separates its facts from hypothetical satellite capabilities, imaging costs, point-target simplification, and AMIS priority/deadline policy.
- [ ] The Example appears in the existing Example library and creates a new Scenario when loaded. Startup and loading use only bundled inputs and make no network call.
- [ ] A documented runnable event script uses existing lifecycle operations to advance to the cue's exact simulated instant before injection. It checks timing and fails on a late clock rather than silently injecting late or rewriting the event time. No new exercise engine is introduced.
- [ ] The accepted emergency event contains source evidence and recorded orbital windows. Injection leaves the baseline plan intact while exposing Impact; manual replan produces ordinary PlanDiff and DecisionTrace results.
- [ ] A served emergency is demonstrable with the bundled configuration. Legitimate unserved results elsewhere remain supported and explainable without pipeline failure or invented windows.
- [ ] Frozen actions remain unchanged and expiry remains permanent. The pristine Scenario is unchanged by injection or replan.
- [ ] The pristine Scenario and accepted ordered event log suffice to reproduce functional requests, evidence, windows, plans, and explanations without the source archive or network. Wall-clock planning timings are excluded from functional equality.
- [ ] The existing third-party-notices documentation credits the USGS evidence and records the applicable source notice. The Example briefing displays `U.S. Geological Survey` and the simulator-policy notice.
