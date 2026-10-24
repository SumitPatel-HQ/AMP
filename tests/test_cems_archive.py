"""Archive-builder seam; all records in this file are synthetic test data."""
import json
from datetime import datetime, timezone
from dataclasses import replace
import pytest
from amis.cues.archive import store_archive, load_archive
from amis.cues.rules import ImagingProfile, write_cue_inputs
from amis.cues.cems import build_cems_inputs
from amis.examples import usgs_vanuatu_example

PROFILE = ImagingProfile(30, 20, 100)

def record(**changes):
    result = dict(code='SYNTHETIC-001', name='Synthetic flood', category='Flood', sensitive=False,
                eventTime='2026-10-01T07:00:00', activationTime='2026-10-04T11:02:00',
                centroid='POINT (24.9786 35.2250)')
    return result | changes

def archive(tmp_path, records):
    manifest = store_archive(tmp_path / 'archive', json.dumps({'results': records}).encode(),
        source='cems', source_url='https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=SYNTHETIC-001',
        retrieved_at=datetime.now(timezone.utc))
    return manifest

def test_build_normalizes_documented_utc_and_lon_lat_and_collapses_duplicates(tmp_path):
    item = record()
    manifest = archive(tmp_path, [item, item])
    artifact = build_cems_inputs(load_archive(manifest), scenario(), PROFILE)
    entry, = artifact['inputs']
    assert entry['injection_time'] == '2026-10-04T11:02:00+00:00'
    assert entry['payload']['request']['target_lon'] == 24.9786
    assert entry['payload']['request']['target_lat'] == 35.225
    assert entry['payload']['request']['deadline'] == '2026-10-05T11:02:00+00:00'
    assert entry['payload']['centroid_policy_version'] == 'cems-centroid-v1'
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    write_cue_inputs(a, artifact)
    write_cue_inputs(b, build_cems_inputs(load_archive(manifest), scenario(), PROFILE))
    assert a.read_bytes() == b.read_bytes()


def scenario():
    return replace(usgs_vanuatu_example(), start_time=datetime(2026, 10, 4, tzinfo=timezone.utc))

@pytest.mark.parametrize('changes,diagnostic', [
    ({'sensitive': None}, 'visibility'), ({'sensitive': True}, 'visibility'),
    ({'centroid': 'POINT (35 91)'}, 'bounds'), ({'centroid': 'POINT Z (24 35 1)'}, 'WKT'),
    ({'centroid': 'POLYGON ((0 0,1 1,0 0))'}, 'WKT'), ({'centroid': None}, 'WKT'),
    ({'activationTime': 'bad'}, 'timestamp'), ({'eventTime': '2026-10-05T00:00:00'}, 'follows'),
    ({'name': ''}, 'name'), ({'category': None}, 'category'),
])
def test_invalid_source_records_fail(tmp_path, changes, diagnostic):
    manifest = archive(tmp_path, [record(**changes)])
    with pytest.raises(ValueError, match=diagnostic):
        build_cems_inputs(load_archive(manifest), scenario(), PROFILE)


def test_conflicting_identity_and_corruption_fail(tmp_path):
    manifest = archive(tmp_path, [record(), record(name='Conflicting revision')])
    with pytest.raises(ValueError, match='conflicting'):
        build_cems_inputs(load_archive(manifest), scenario(), PROFILE)
    (manifest.parent / 'response.json').write_bytes(b'corruption')
    with pytest.raises(ValueError, match='checksum mismatch'):
        load_archive(manifest)

@pytest.mark.parametrize('profile', [ImagingProfile(0,20,100), ImagingProfile(30,-1,100), ImagingProfile(30,20,100,'missing')])
def test_invalid_profiles_fail(tmp_path, profile):
    with pytest.raises(ValueError):
        build_cems_inputs(load_archive(archive(tmp_path,[record()])), scenario(), profile)

@pytest.mark.parametrize('time', ['2026-10-03T23:59:59', '2026-10-08T22:30:00'])
def test_outside_half_open_interval_fails(tmp_path, time):
    with pytest.raises(ValueError, match='outside Scenario'):
        build_cems_inputs(load_archive(archive(tmp_path,[record(activationTime=time)])), scenario(), PROFILE)


def test_incomplete_response_is_rejected_before_publication(tmp_path):
    manifest = archive(tmp_path, [record()])
    loaded = load_archive(manifest)
    loaded.response['count'] = 2
    with pytest.raises(ValueError, match='incomplete'):
        build_cems_inputs(loaded, scenario(), PROFILE)
