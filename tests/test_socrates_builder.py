"""Public developer archive/builder seam; rows here are synthetic unit fixtures."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from amis.demo import build_canonical_replan_scenario
from amis.orbital.elements import catalogue
from amis.conjunctions.archive import load_archive, store_archive
from amis.conjunctions.builder import build_inputs

NOW = datetime(2026, 9, 21, 10, tzinfo=timezone.utc)
HEADER = 'NORAD_CAT_ID_1,OBJECT_NAME_1,DSE_1,NORAD_CAT_ID_2,OBJECT_NAME_2,DSE_2,TCA,TCA_RANGE,TCA_RELATIVE_SPEED,MAX_PROB,DILUTION\n'
ROW = '39084,LANDSAT 8,1,99999,OTHER,1,2026-09-21 10:25:00.000,0.25,10,1.000E-04,0.1\n'


def scenario():
    base = build_canonical_replan_scenario()
    return replace(base, satellites=(replace(base.satellite, orbit=catalogue()[0]),))


def archive(tmp_path, rows=ROW):
    return store_archive(tmp_path / 'report', (HEADER + rows).encode(),
                         source_url='https://celestrak.org/SOCRATES/sort-minRange.csv',
                         retrieved_at=NOW - timedelta(hours=1), response_filename='sort-minRange.csv')


def build(path, **kwargs):
    return build_inputs(load_archive(path), scenario(), injection_time=NOW,
                        pre_padding_s=300, post_padding_s=300, **kwargs)


def test_bytes_integrity_before_parse_and_no_overwrite(tmp_path):
    path = archive(tmp_path)
    assert (path.parent / 'report.csv').read_bytes() == (HEADER + ROW).encode()
    with pytest.raises(ValueError, match='already exists'):
        archive(tmp_path)
    (path.parent / 'report.csv').write_bytes(b'not CSV')
    with pytest.raises(ValueError, match='checksum'):
        load_archive(path)


def test_threshold_and_orientation_duplicates_are_deterministic(tmp_path):
    reverse = '99999,OTHER,1,39084,LANDSAT 8,1,2026-09-21 10:25:00.000,0.25,10,0.0001,0.1\n'
    result = build(archive(tmp_path, ROW + reverse))
    assert len(result['inputs']) == 1
    entry = result['inputs'][0]
    assert entry['injection_time'] == NOW.isoformat()
    assert entry['payload']['outage_start'] == '2026-09-21T10:20:00+00:00'
    assert entry['payload']['conjunction']['maximum_probability'] == 0.0001
    assert entry['payload']['conjunction']['counterpart_norad_id'] == 99999
    assert result == build(tmp_path / 'report/manifest.json')


@pytest.mark.parametrize('probability', ['', 'N/A', 'NaN', '-1', '1.1', '1%', 'inf'])
def test_unsupported_probability_is_diagnostic_not_zero(tmp_path, probability):
    result = build(archive(tmp_path, ROW.replace('1.000E-04', probability)))
    assert result['inputs'] == []
    assert 'MAX_PROB' in result['summary']['diagnostics'][0]


def test_below_threshold_and_unmatched_summary(tmp_path):
    rows = ROW.replace('1.000E-04', '9.999E-05') + ROW.replace('39084', '12345')
    result = build(archive(tmp_path, rows))
    assert result['inputs'] == []
    assert result['summary']['nonqualifying_encounters'] == 1
    assert result['summary']['unmatched_encounters'] == 1


@pytest.mark.parametrize('threshold', [0, 0.001, 1])
def test_v1_cannot_label_a_different_threshold(tmp_path, threshold):
    with pytest.raises(ValueError, match='v1 requires threshold 0.0001'):
        build(archive(tmp_path), threshold=threshold)


@pytest.mark.parametrize('distance', ['-1', 'nan', 'inf'])
def test_invalid_distance_fails(tmp_path, distance):
    with pytest.raises(ValueError, match='distance'):
        build(archive(tmp_path, ROW.replace('0.25', distance)))


def test_conflicting_selected_encounter_fails(tmp_path):
    with pytest.raises(ValueError, match='conflicting'):
        build(archive(tmp_path, ROW + ROW.replace('0.25', '0.3')))


def test_explicit_unmatched_selection_fails(tmp_path):
    with pytest.raises(ValueError, match='unmatched'):
        build(archive(tmp_path, ROW.replace('39084', '12345')), satellite_ids=('SAT-001',))


def test_both_objects_and_ambiguous_identity_mapping(tmp_path):
    path = archive(tmp_path, ROW.replace('99999', '40697'))
    base = scenario()
    other = replace(base.satellite, id='SAT-002', orbit=catalogue()[1])
    sc = replace(base, satellites=(base.satellite, other))
    kwargs = dict(injection_time=NOW, pre_padding_s=300, post_padding_s=300)
    result = build_inputs(load_archive(path), sc, **kwargs)
    assert [(i['payload']['satellite_id'], i['payload']['conjunction']['counterpart_norad_id'])
            for i in result['inputs']] == [('SAT-001', 40697), ('SAT-002', 39084)]
    reused = replace(sc, satellites=(base.satellite, replace(base.satellite, id='SAT-COPY')))
    with pytest.raises(ValueError, match='ambiguous'):
        build_inputs(load_archive(path), reused, **kwargs)
    mapped = build_inputs(load_archive(path), reused, identity_mapping={39084: 'SAT-COPY'}, **kwargs)
    assert [i['payload']['satellite_id'] for i in mapped['inputs']] == ['SAT-COPY']


@pytest.mark.parametrize('change, message', [
    ({'injection_time': NOW - timedelta(hours=2)}, 'horizon'),
    ({'injection_time': NOW + timedelta(minutes=21)}, 'later'),
    ({'pre_padding_s': 0}, 'positive'),
    ({'post_padding_s': -1}, 'positive'),
    ({'post_padding_s': 100000}, 'horizon'),
    ({'pre_padding_s': float('nan')}, 'finite'),
    ({'injection_time': NOW.replace(tzinfo=None)}, 'timezone'),
])
def test_temporal_and_policy_failures(tmp_path, change, message):
    kwargs = dict(injection_time=NOW, pre_padding_s=300, post_padding_s=300)
    kwargs.update(change)
    with pytest.raises(ValueError, match=message):
        build_inputs(load_archive(archive(tmp_path)), scenario(), **kwargs)


def test_empty_truncated_report_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='no encounter'):
        build(archive(tmp_path, ''))


def test_evidence_unavailable_at_injection(tmp_path):
    path = store_archive(tmp_path / 'future', (HEADER + ROW).encode(),
                         source_url='https://celestrak.org/SOCRATES/sort-minRange.csv',
                         retrieved_at=NOW + timedelta(seconds=1), response_filename='report.csv')
    with pytest.raises(ValueError, match='unavailable'):
        build(path)


def test_injection_at_outage_start_and_full_horizon_boundaries(tmp_path):
    path = archive(tmp_path)
    sc = replace(scenario(), start_time=NOW + timedelta(minutes=20), end_time=NOW + timedelta(minutes=30))
    result = build_inputs(load_archive(path), sc, injection_time=sc.start_time,
                          pre_padding_s=300, post_padding_s=300)
    assert result['inputs'][0]['payload']['outage_start'] == sc.start_time.isoformat()
    assert result['inputs'][0]['payload']['outage_end'] == sc.end_time.isoformat()


def test_explicit_missing_encounter_and_mapping_mismatch_fail(tmp_path):
    path = archive(tmp_path)
    with pytest.raises(ValueError, match='encounter not found'):
        build(path, encounter_ids=('missing',))
    with pytest.raises(ValueError, match='mapping'):
        build(path, identity_mapping={39084: 'not-a-satellite'})


def test_extra_csv_fields_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='row'):
        build(archive(tmp_path, ROW.rstrip() + ',extra\n'))


def test_publish_failure_leaves_no_partial_output(tmp_path):
    from scripts.build_socrates_inputs import publish
    output = tmp_path / 'inputs.json'
    with pytest.raises(ValueError):
        publish(output, {'value': float('nan')})
    assert not output.exists()
    publish(output, {'inputs': []})
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        publish(output, {'inputs': [1]})
    assert output.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ['inputs.json']
