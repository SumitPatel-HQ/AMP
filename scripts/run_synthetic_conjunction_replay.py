"""Synthetic training evidence, explicit replan, and network-free replay."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amis.demo import CanonicalWindowProvider, build_canonical_replan_scenario
from amis.domain import MissionEvent, Scenario
from amis.orbital.elements import catalogue
from amis.session import MissionSession


def prepared(scenario: Scenario) -> MissionSession:
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(scenario)
    session.generate_windows()
    session.plan()
    return session


def main() -> None:
    base = build_canonical_replan_scenario()
    scenario = replace(base, satellites=(replace(base.satellite, orbit=catalogue()[0]),))
    session = prepared(scenario)
    injection_time = scenario.start_time + timedelta(seconds=60)
    session.step((injection_time - session.get_state().simulated_time).total_seconds())
    assert session.get_state().simulated_time == injection_time
    previous = session.get_plan()
    action = next(a for a in previous.actions if a.request_id == "OBS-B")
    event = session.inject_event("SATELLITE_UNAVAILABLE", {
        "satellite_id": action.satellite_id,
        "outage_start": action.start.isoformat(), "outage_end": action.end.isoformat(),
        "conjunction": {
            "source": "synthetic training fixture; no historical provenance",
            "encounter_id": "synthetic-training-1",
            "matched_norad_id": scenario.satellite.orbit.norad_id,
            "counterpart_norad_id": 99999,
            "tca": (action.start + timedelta(minutes=5)).isoformat(),
            "miss_distance_km": 0.25, "maximum_probability": 0.0002,
            "threshold": 0.0001, "policy_version": "socrates-outage-v1",
            "pre_padding_s": 300, "post_padding_s": 300,
        },
    })
    assert session.get_plan() == previous
    impact = session.get_last_impact()
    session.replan()
    recorded = event.to_dict()
    with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
        replay = prepared(Scenario.from_dict(scenario.to_dict()))
        restored = MissionEvent.from_dict(recorded)
        replay.step((restored.event_time - replay.get_state().simulated_time).total_seconds())
        assert replay.get_state().simulated_time == restored.event_time
        replay.inject_event(restored.event_type, restored.payload)
        replay.replan()
        assert replay.get_last_impact() == impact
        assert replay.get_traces() == session.get_traces()
        assert replay.get_plan().actions == session.get_plan().actions
    print(json.dumps({"notice": "SYNTHETIC TRAINING EVIDENCE; no confirmed maneuver",
                      "scenario": scenario.to_dict(), "event": recorded,
                      "impact": impact.to_dict(), "traces": [t.to_dict() for t in session.get_traces()],
                      "offline_replay": "passed"}, indent=2))


if __name__ == "__main__":
    main()
