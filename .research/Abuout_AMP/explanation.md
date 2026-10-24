AMIS currently uses a deterministic scenario because the first objective was to prove the complete adaptive mission-planning loop independently of external systems: generate a plan, simulate execution, introduce a disruption, identify its impact, replan the remaining mission, explain the changes, and measure the result.

The synthetic scenario is therefore not the final source of mission data. It is the first implementation of a replaceable scenario and observation-window layer.

To move toward a realistic Earth-observation scenario, AMIS progressively replaces simplified inputs with higher-fidelity inputs. Synthetic observation windows can be replaced with windows calculated from satellite orbital data and target coordinates using orbital propagation. The spacecraft model can then incorporate more realistic battery, storage, payload, pointing, slew and availability constraints. Ground-station visibility and downlink activities can be introduced so onboard storage becomes part of the full observation-to-downlink mission cycle.

Environmental conditions such as cloud cover can then enter AMIS as mission-state updates rather than manually injected demo events. New observation requests can similarly arrive during execution, allowing AMIS to determine their impact on the current mission and adapt the remaining plan.

The core planning architecture does not need to be replaced during this transition. Observation requests, observation windows, constraints, MissionPlan versions, simulation, impact analysis, adaptive replanning, decision traces and metrics remain the same conceptual pipeline. What changes is the fidelity and source of the information entering those components.

This gives AMIS a progression from a deterministic research demonstrator, to a physically realistic simulator, to a real-data mission replay platform, and eventually to an operations-like adaptive mission-planning system. It remains a planning and decision-support system rather than a satellite command-and-control system.
