"""Offline CEMS public activation normalization and centroid-v1 policy."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from amis.api_schemas import ObservationRequestSchema
from amis.cues.archive import CueArchive
from amis.cues.normalize import _finite_number
from amis.cues.rules import ImagingProfile, request_identifier
from amis.domain import ObservationRequest, Scenario

POLICY_VERSION = 'cems-centroid-v1'
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
_POINT = re.compile(rf'POINT\s*\(\s*({_NUMBER})\s+({_NUMBER})\s*\)', re.IGNORECASE)


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError(f'{field} must be an ISO-8601 timestamp')
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f'{field} must be an ISO-8601 timestamp') from error
    # The owning API documentation explicitly defines offset-free values as UTC.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def normalize_cems(response: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if not isinstance(response.get('results'), list) or not response['results']:
        raise ValueError('CEMS response requires nonempty results')
    if response.get('next'):
        raise ValueError('CEMS selection is incomplete; archive a complete activation detail response')
    if 'count' in response and (type(response['count']) is not int or response['count'] != len(response['results'])):
        raise ValueError('CEMS selection is incomplete: count must match the archived results')
    records: dict[str, dict[str, Any]] = {}
    for record in response['results']:
        if not isinstance(record, dict):
            raise ValueError('CEMS activation must be an object')
        code = record.get('code')
        if record.get('sensitive') is not False:
            raise ValueError(f'CEMS {code}: sensitive must be explicitly false; visibility unknown or restricted')
        normalized: dict[str, Any] = {}
        for field in ('code', 'name', 'category'):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'CEMS {code}: missing nonempty {field}')
            normalized[field] = value.strip()
        activation = _utc(record.get('activationTime'), 'activationTime')
        event = None if record.get('eventTime') is None else _utc(record['eventTime'], 'eventTime')
        if event is not None and event > activation:
            raise ValueError(f'CEMS {code}: eventTime follows activationTime')
        centroid = record.get('centroid')
        match = _POINT.fullmatch(centroid.strip()) if isinstance(centroid, str) else None
        if match is None:
            raise ValueError(f'CEMS {code}: centroid must be a two-dimensional WKT POINT (longitude latitude); no fallback')
        lon, lat = (_finite_number(float(value), 'centroid coordinate') for value in match.groups())
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError(f'CEMS {code}: centroid outside geographic longitude/latitude bounds')
        normalized.update(activation_time=activation.isoformat(), source_event_time=event.isoformat() if event else None,
                          target_lon=lon, target_lat=lat)
        code = normalized['code']
        if code in records and records[code] != normalized:
            raise ValueError(f'conflicting normalized records for cems:{code}')
        records[code] = normalized
    return tuple(sorted(records.values(), key=lambda item: (item['activation_time'], item['code'])))


def build_cems_inputs(archive: CueArchive, scenario: Scenario, profile: ImagingProfile) -> dict[str, Any]:
    if archive.source != 'cems':
        raise ValueError('CEMS builder requires a cems archive')
    if any(t.tzinfo is None or t.utcoffset() is None for t in (scenario.start_time, scenario.end_time)):
        raise ValueError('Scenario boundaries must include a timezone')
    if scenario.end_time <= scenario.start_time:
        raise ValueError('Scenario end must be after start')
    profile = ImagingProfile.from_dict(profile.to_dict())
    if profile.satellite_id is not None and profile.satellite_id not in {s.id for s in scenario.satellites}:
        raise ValueError('imaging profile names an unknown satellite')
    inputs = []
    for cue in normalize_cems(archive.response):
        activation = datetime.fromisoformat(cue['activation_time'])
        if not scenario.start_time <= activation < scenario.end_time:
            raise ValueError(f"CEMS {cue['code']}: activation is outside Scenario half-open interval; source times cannot be shifted")
        identifier = request_identifier('cems', cue['code'])
        if identifier in {r.id for r in scenario.requests}:
            raise ValueError(f'cue request identifier already exists in Scenario: {identifier}')
        try:
            deadline = activation + timedelta(hours=24)
        except OverflowError as error:
            raise ValueError('CEMS policy deadline outside supported datetime range') from error
        validated = ObservationRequestSchema.model_validate({
            **profile.to_dict(), 'id': identifier, 'target_name': profile.target_name or cue['name'],
            'target_lon': cue['target_lon'], 'target_lat': cue['target_lat'], 'priority': 5, 'deadline': deadline,
        })
        request = ObservationRequest.from_dict(validated.model_dump(mode='json'))
        payload = dict(request=request.to_dict(), source='cems', source_event_id=cue['code'], alert_level='unknown',
                       category=cue['category'], activation_time=cue['activation_time'], source_url=archive.source_url,
                       centroid_policy_version=POLICY_VERSION)
        if cue['source_event_time'] is not None:
            payload['source_event_time'] = cue['source_event_time']
        inputs.append(dict(injection_time=cue['activation_time'], event_type='EMERGENCY_TASK', payload=payload))
    return dict(metadata=dict(artifact_type='developer-cue-inputs', scenario_id=scenario.id,
        policy_version=POLICY_VERSION, imaging_profile=profile.to_dict(), archive=dict(source=archive.source,
        source_url=archive.source_url, file=archive.file, sha256=archive.sha256)), inputs=inputs)
