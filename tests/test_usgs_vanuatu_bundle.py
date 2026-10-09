"""Ticket 03: the bundled, real USGS Vanuatu earthquake replay Example.

Unlike ``tests/test_cue_inputs.py``, this file uses the actual committed
archive and generated artifact under
``amis/data/examples/usgs-vanuatu-2026-10-08/`` -- the real, independently
verifiable evidence this ticket selected, not fabricated USGS-shaped
records.
"""

from __future__ import annotations

import contextlib
import json
import socket
from pathlib import Path
from typing import Any

import pytest

import amis.examples as examples_module
from amis.domain import ReasonCode
from amis.examples import examples, usgs_vanuatu_example
from scripts.run_usgs_vanuatu_replay import CUE_INPUTS_PATH, run

BUNDLE_DIR = Path(__file__).resolve().parents[1] / "amis" / "data" / "examples" / "usgs-vanuatu-2026-10-08"


def test_usgs_vanuatu_example_matches_committed_scenario_json():
    """The committed ``scenario.json`` used to build ``cue-inputs.json`` must be
    exactly what the application actually loads; otherwise the bundled
    artifact silently stops describing the running Example."""
    committed = json.loads((BUNDLE_DIR / "scenario.json").read_text(encoding="utf-8"))
    assert usgs_vanuatu_example().to_dict() == committed


def test_usgs_vanuatu_example_survives_an_unrelated_orbital_example_failure(monkeypatch):
    """One bundled orbital Example's builder failing must not withhold another."""

    def _broken_orbital_example() -> None:
        raise ModuleNotFoundError("simulated unrelated failure")

    monkeypatch.setattr(examples_module, "orbital_example", _broken_orbital_example)
    result = examples()
    assert "orbital" not in result
    assert "usgs-vanuatu-2026-10-08" in result


def _cue_entry() -> dict[str, Any]:
    return json.loads(CUE_INPUTS_PATH.read_text(encoding="utf-8"))["inputs"][0]


def test_replay_injects_at_the_cues_exact_recorded_time():
    entry = _cue_entry()
    result = run(replan=False)
    assert result["events"][0]["event_time"] == entry["injection_time"] == "2026-10-08T09:00:07.768000+00:00"


def test_replay_serves_the_emergency_before_the_scenario_ends():
    """Proves the bundled deadline (48h after the quake) outliving the Scenario
    end (capped by the stored element's 14-day validity) does not make the
    request unservable: a real pass still opens before the Scenario ends."""
    scenario = usgs_vanuatu_example()
    entry = _cue_entry()
    cue_request_id = entry["payload"]["request"]["id"]

    result = run(replan=True)
    plan = result["replanned_plan"]
    assert plan["unscheduled"] == []

    cue_action = next(action for action in plan["actions"] if action["request_id"] == cue_request_id)
    assert cue_action["start"] < scenario.end_time.isoformat()

    reason_codes = {
        trace["request_id"]: trace["reason_code"]
        for trace in result["traces"]
    }
    assert reason_codes[cue_request_id] == ReasonCode.HIGHER_PRIORITY_TASK_INSERTED.value


@contextlib.contextmanager
def _block_sockets():
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("network access is disabled during the USGS Vanuatu replay test")

    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]


def test_replay_runs_without_network_access():
    with _block_sockets():
        result = run(replan=True)
    assert result["replanned_plan"]["unscheduled"] == []


@pytest.mark.parametrize("replan", [False, True])
def test_replay_fails_loudly_on_a_late_clock(monkeypatch, replan):
    """A clock already past the cue's recorded time must raise, not inject late."""
    from amis.session import MissionSession

    original_step = MissionSession.step

    def _overshoot(self: MissionSession, seconds: float) -> Any:
        # Advance further than requested so the clock cannot land exactly
        # on the cue's recorded time.
        return original_step(self, seconds + 3600)

    monkeypatch.setattr(MissionSession, "step", _overshoot)
    with pytest.raises(RuntimeError, match="refusing to inject late"):
        run(replan=replan)
