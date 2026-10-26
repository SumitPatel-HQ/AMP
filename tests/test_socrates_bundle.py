"""Real report conversion and the confirmed MissionSession lifecycle seam."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import socket

import pytest

BUNDLE = Path(__file__).resolve().parents[1] / 'amis/data/examples/socrates-flock-2026-10-27'
ARCHIVE = BUNDLE.parents[1] / 'conjunctions/2026-10-26'


def test_bundled_inputs_rebuild_exactly_and_orbit_is_original(tmp_path, monkeypatch):
    from amis.conjunctions.archive import load_archive
    from amis.conjunctions.builder import build_inputs
    from amis.examples import socrates_flock_example
    from amis.orbital.validation import preview
    from scripts.build_socrates_inputs import publish

    monkeypatch.setattr(socket.socket, 'connect', lambda *args: pytest.fail('network forbidden'))
    scenario = socrates_flock_example()
    original = json.loads((BUNDLE / 'conjunction-inputs.json').read_bytes())
    result = build_inputs(load_archive(ARCHIVE / 'manifest.json'), scenario,
                          injection_time=datetime.fromisoformat('2026-10-27T05:00:00+00:00'),
                          pre_padding_s=3600, post_padding_s=3600, satellite_ids=('SAT-FLOCK',),
                          encounter_ids=tuple(i['payload']['conjunction']['encounter_id'] for i in original['inputs']))
    path = tmp_path / 'inputs.json'
    publish(path, result)
    assert path.read_bytes() == (BUNDLE / 'conjunction-inputs.json').read_bytes()
    orbit_meta = json.loads((ARCHIVE / 'orbit-62666-manifest.json').read_bytes())
    raw = (ARCHIVE / 'orbit-62666.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == orbit_meta['sha256']
    assert scenario.satellite.orbit.omm == json.loads(raw)[0]
    assert preview(scenario)['errors'] == []


def test_injection_exposes_overlap_impact_and_replan_remains_explicit():
    from scripts.run_socrates_replay import run

    result = run(replan=False)
    assert result['active_plan'] == result['baseline_at_injection']
    assert result['active_plan']['id'] == result['baseline_plan']['id']
    assert 'replanned_plan' not in result
    assert len(result['events']) == 2
    assert all(e['event_time'] == '2026-10-27T05:00:00+00:00' for e in result['events'])
    assert len(result['impacts'][-1]['invalid_unfrozen_action_ids']) == 2
    assert len(set(result['impacts'][-1]['invalid_unfrozen_action_ids'])) == 2
    first, second = [e['payload'] for e in result['events']]
    assert first['outage_end'] > second['outage_start']


def test_offline_persisted_replay_keeps_evidence_traces_frozen_actions_and_determinism(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from amis.db.repositories import build_repositories
    from amis.repositories import MissionSessionStore
    from amis.windows.selection import ScenarioWindowProvider
    from scripts.run_socrates_replay import run

    read = Path.read_bytes
    def offline(path):
        if path.resolve().is_relative_to(ARCHIVE.resolve()):
            pytest.fail('source report unavailable during replay')
        return read(path)
    monkeypatch.setattr(Path, 'read_bytes', offline)
    monkeypatch.setattr(socket.socket, 'connect', lambda *args: pytest.fail('network forbidden'))
    database = tmp_path / 'replay.db'
    result = run(replan=True, database=database)
    assert result['state_after'] == result['state_at_injection']
    before = {a['request_id']: a for a in result['baseline_at_injection']['actions']}
    after = {a['request_id']: a for a in result['replanned_plan']['actions']}
    assert after['OBS-1'] == before['OBS-1']  # Completed before injection; frozen action is unchanged.
    assert set(after) == {'OBS-1', 'OBS-3', 'OBS-4'}
    assert after['OBS-3']['start'] >= result['events'][1]['payload']['outage_end']
    traces = {t['request_id']: t for t in result['traces']}
    assert traces['OBS-2']['reason_code'] == 'COLLISION_AVOIDANCE_OUTAGE'
    assert traces['OBS-3']['reason_code'] == 'COLLISION_AVOIDANCE_OUTAGE'
    engine = create_engine(f'sqlite:///{database}')
    try:
        restored = MissionSessionStore(build_repositories(engine), window_provider=ScenarioWindowProvider()).load('SCN-SOCRATES-FLOCK-2026-10-27')
        assert [e.to_dict() for e in restored.get_events()] == result['events']
        assert [t.to_dict() for t in restored.get_traces()] == result['traces']
        assert restored.get_plan().to_dict() == result['replanned_plan']
    finally:
        engine.dispose()


def test_runner_refuses_clock_mismatch(monkeypatch):
    from amis.session import MissionSession
    from scripts.run_socrates_replay import run
    step = MissionSession.step
    monkeypatch.setattr(MissionSession, 'step', lambda self, seconds: step(self, seconds + 1))
    with pytest.raises(RuntimeError, match='refusing to inject late'):
        run()


def test_example_is_registered_with_source_briefing():
    from amis.examples import examples, example_briefings
    assert 'socrates-flock-2026-10-27' in examples()
    assert '58418' in example_briefings()['socrates-flock-2026-10-27']
