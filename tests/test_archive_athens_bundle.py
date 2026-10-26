"""Real CDSE metadata with explicitly hypothetical capacity-constrained imaging."""

import json
import socket
from pathlib import Path

from amis.session import MissionSession
from amis.windows.selection import ScenarioWindowProvider


BUNDLE = Path(__file__).resolve().parents[1] / "amis/data/examples/archive-athens-2026-10-26"


def test_athens_example_releases_future_imaging_to_competing_demand():
    from amis.examples import archive_athens_example, examples
    from scripts.run_archive_athens_replay import run

    scenario = archive_athens_example()
    assert examples()["archive-athens-2026-10-26"] == scenario
    assert scenario.to_dict() == json.loads((BUNDLE / "scenario.json").read_bytes())
    result = run(replan=True)
    assert [a["request_id"] for a in result["baseline_plan"]["actions"]] == ["OBS-FROZEN", "OBS-ARCHIVE"]
    assert [a["request_id"] for a in result["replanned_plan"]["actions"]] == ["OBS-FROZEN", "OBS-COMPETING"]
    assert result["events"][0]["payload"]["item_id"] == "S2A_MSIL2A_20260908T091331_N0512_R050_T35SKC_20260908T141908"
    assert result["events"][0]["event_time"] == "2026-10-26T07:05:00+00:00"
    assert result["metrics_after"]["archive_satisfied_count"] == 1
    assert result["metrics_after"]["archive_satisfied_utility"] == 4
    assert result["metrics_after"]["mission_utility"] == 8
    assert result["metrics_after"]["total_fulfilled_utility"] == 12
    assert result["metrics_after"]["completion_rate"] == 0


def test_archive_injection_keeps_affected_baseline_until_explicit_replan():
    from scripts.run_archive_athens_replay import run

    result = run(replan=False)
    assert "replanned_plan" not in result
    assert result["active_plan"]["id"] == result["baseline_plan"]["id"]
    assert len(result["impact"]["invalid_unfrozen_action_ids"]) == 1
    assert result["metrics_after"]["mission_utility"] == 9
    assert result["metrics_after"]["total_fulfilled_utility"] == 9


def test_real_archive_inputs_rebuild_to_identical_bytes_offline(tmp_path, monkeypatch):
    from amis.archive_check import write_archive_inputs
    from amis.examples import archive_athens_example

    def blocked(*args, **kwargs):
        raise AssertionError("network unavailable during offline conversion")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    artifact_path = tmp_path / "archive-inputs.json"
    manifest = BUNDLE.parents[1] / "imagery/athens-sentinel2-20261026/manifest.json"
    requirements = json.loads((BUNDLE / "requirements.json").read_bytes())
    write_archive_inputs(artifact_path, manifest, archive_athens_example(), requirements)
    assert artifact_path.read_bytes() == (BUNDLE / "archive-inputs.json").read_bytes()


def test_example_persists_and_replays_with_no_catalogue_or_archive_files(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from amis.db.repositories import build_repositories
    from amis.repositories import MissionSessionStore
    from scripts.run_archive_athens_replay import run

    original_read = Path.read_bytes

    def read_without_archive(path):
        if path.resolve().is_relative_to((BUNDLE.parents[1] / "imagery").resolve()):
            raise AssertionError("archive files unavailable during replay")
        return original_read(path)

    def blocked(*args, **kwargs):
        raise AssertionError("catalogue unavailable during replay")

    monkeypatch.setattr(Path, "read_bytes", read_without_archive)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    database = tmp_path / "athens.db"
    result = run(replan=True, database=database)
    assert result["state_at_injection"] == result["state_after"]
    engine = create_engine(f"sqlite:///{database}")
    store = MissionSessionStore(build_repositories(engine), window_provider=ScenarioWindowProvider())
    try:
        restored = store.load("SCN-ARCHIVE-ATHENS")
        assert restored.get_events()[0].to_dict() == result["events"][0]
        assert restored.get_metrics().to_dict() == result["metrics_after"]
        assert restored.get_metrics(restored.get_plans()[0].id).archive_satisfied_count == 0
        assert next(r for r in restored.get_request_pool() if r.id == "OBS-ARCHIVE").status.value == "satisfied_by_archive"
        restored.step(3600)
        assert set(restored.get_state().completed_request_ids) == {"OBS-FROZEN", "OBS-COMPETING"}
        assert restored.get_state().battery_wh == 0
        assert next(r for r in restored.get_request_pool() if r.id == "OBS-ARCHIVE").status.value == "satisfied_by_archive"
    finally:
        engine.dispose()


def test_replay_refuses_a_clock_that_misses_the_intended_injection_time(monkeypatch):
    import pytest
    from scripts.run_archive_athens_replay import run

    original_step = MissionSession.step

    def overshoot(self, seconds):
        return original_step(self, seconds + 60)

    monkeypatch.setattr(MissionSession, "step", overshoot)
    with pytest.raises(RuntimeError, match="refusing to inject late"):
        run(replan=True)


def test_registered_example_api_exposes_the_dated_scenario_and_briefing():
    from fastapi.testclient import TestClient
    from amis.api import create_app

    client = TestClient(create_app())
    summary = next(s for s in client.get("/examples").json() if s["id"] == "archive-athens-2026-10-26")
    assert "Scene cloud cover" in summary["briefing"]
    assert "Copernicus Sentinel data 2026" in summary["briefing"]
    response = client.get("/examples/archive-athens-2026-10-26")
    assert response.status_code == 200
    assert response.json()["window_policy"]["provider"] == "synthetic"
