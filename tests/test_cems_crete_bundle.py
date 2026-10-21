"""Actual archived EMSR933 Example through the agreed MissionSession seam."""
import json
import socket
from datetime import datetime
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from amis.cues.archive import load_archive
from amis.cues.cems import build_cems_inputs
from amis.cues.rules import ImagingProfile, write_cue_inputs
from amis.db.repositories import build_repositories
from amis.db.schema import metadata
from amis.examples import cems_crete_example, examples, example_briefings
from amis.repositories import MissionSessionStore
from amis.session import MissionSession
from amis.windows.selection import ScenarioWindowProvider
from scripts.run_cems_crete_replay import CUE_INPUTS_PATH, run

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'amis/data/cues/crete-emsr933-20261004/manifest.json'

def test_real_bundle_is_reproducible_and_registered(tmp_path):
    scenario = cems_crete_example()
    assert examples()['cems-crete-2026-10-04'] == scenario
    assert 'point approximation' in example_briefings()['cems-crete-2026-10-04']
    artifact = build_cems_inputs(load_archive(MANIFEST), scenario, ImagingProfile(30,20,100))
    output = tmp_path/'inputs.json'
    write_cue_inputs(output,artifact)
    assert output.read_bytes() == CUE_INPUTS_PATH.read_bytes()

@pytest.mark.parametrize('replan',[False,True])
def test_runner_offline_exact_arrival_and_explicit_replan(monkeypatch,replan):
    def forbidden(*args,**kwargs):
        raise AssertionError('network forbidden')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    result=run(replan=replan)
    assert result['events'][0]['event_time'] == '2026-10-04T11:02:00+00:00'
    assert result['events'][0]['payload']['source_event_id'] == 'EMSR933'
    assert len(result['impacts']) == 1
    assert ('replanned_plan' in result) == replan
    if replan:
        assert result['replanned_plan']['unscheduled'] == []
        assert result['metrics']['emergency_response'][0]['planned_start_time'] is not None


def test_real_persisted_lifecycle_replays_without_archives_or_network(tmp_path,monkeypatch):
    scenario=cems_crete_example()
    entry=json.loads(CUE_INPUTS_PATH.read_bytes())['inputs'][0]
    def forbidden(*args,**kwargs):
        raise AssertionError('archive and network forbidden')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr('amis.cues.archive.load_archive',forbidden)
    monkeypatch.chdir(tmp_path)
    engine=create_engine(f'sqlite:///{tmp_path / "mission.db"}')
    metadata.create_all(engine)
    provider=ScenarioWindowProvider()
    store=MissionSessionStore(build_repositories(engine),window_provider=provider)
    session=store.create(scenario)
    session.generate_windows(); session.plan()
    instant=datetime.fromisoformat(entry['injection_time'])
    session.step((instant-scenario.start_time).total_seconds())
    event=session.inject_event(entry['event_type'],entry['payload'])
    assert session.get_plan().version == 1
    plan=session.replan()
    response=session.get_metrics().emergency_response[0]
    assert response.planned_start_time is not None
    session.step((response.planned_start_time-session.get_state().simulated_time).total_seconds())
    assert session.get_metrics().emergency_response[0].achieved_start_time == response.planned_start_time
    store.save(session); engine.dispose()
    engine=create_engine(f'sqlite:///{tmp_path / "mission.db"}')
    restored=MissionSessionStore(build_repositories(engine),window_provider=provider).load(scenario.id)
    assert restored.get_events() == (event,)
    assert restored.get_metrics().emergency_response == session.get_metrics().emergency_response
    replay=MissionSession(window_provider=provider)
    replay.load_scenario(scenario); replay.generate_windows(); replay.plan()
    replay.step((instant-scenario.start_time).total_seconds())
    replay.inject_event(event.event_type,event.to_dict()['payload'])
    replay_plan=replay.replan()
    assert replay.get_windows() == session.get_windows()
    assert [(a.request_id,a.start) for a in replay_plan.actions] == [(a.request_id,a.start) for a in plan.actions]
    assert restored.get_scenario() == scenario
    restored.reset()
    assert restored.get_events() == ()
    engine.dispose()
