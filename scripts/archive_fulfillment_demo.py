"""Reproduce D-01's synthetic evidence transition without network access."""

import json
from pathlib import Path

from amis.demo import CanonicalWindowProvider
from amis.session import MissionSession


def main() -> None:
    fixture = Path(__file__).resolve().parents[1] / "amis/data/examples/archive-synthetic-fulfillment"
    session = MissionSession(window_provider=CanonicalWindowProvider())
    session.load_scenario(fixture / "scenario.json")
    session.generate_windows()
    baseline = session.plan()
    session.step(300)
    event_input = json.loads((fixture / "event-input.json").read_text(encoding="utf-8"))
    accepted = session.inject_event(event_input["event_type"], event_input["payload"])
    print("SYNTHETIC catalogue evidence; no image product verified.")
    print(json.dumps(accepted.to_dict(), indent=2))
    print("Active plan remains affected until explicit replan:", session.get_plan().id)
    print(json.dumps(session.get_last_impact().to_dict(), indent=2))
    revised = session.replan()
    print("Explicit replan:", baseline.id, "->", revised.id)
    print(json.dumps(session.compare_versions(1, 2).to_dict(), indent=2))
    print(json.dumps(session.get_metrics().to_dict(), indent=2))


if __name__ == "__main__":
    main()
