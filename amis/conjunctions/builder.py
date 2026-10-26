"""Pure, deterministic report-to-outage conversion. No planner or network access."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import math
from typing import Any

from amis.conjunctions.archive import ReportArchive, instant
from amis.domain import Scenario
from amis.domain.conjunction import ConjunctionEvidence, outage_interval


@dataclass(frozen=True)
class EncounterOutagePolicy:
    injection_time: datetime
    pre_padding_s: float
    post_padding_s: float

    def __post_init__(self) -> None:
        object.__setattr__(self, 'injection_time', instant(self.injection_time.isoformat()))
        for name in ('pre_padding_s', 'post_padding_s'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
            if value <= 0:
                raise ValueError('positive padding required')
            object.__setattr__(self, name, float(value))

    def to_dict(self) -> dict[str, Any]:
        return {'injection_time': self.injection_time.isoformat(),
                'pre_padding_s': self.pre_padding_s, 'post_padding_s': self.post_padding_s}


def outage_input_sort_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    payload = entry['payload']
    evidence = payload['conjunction']
    return entry['injection_time'], payload['satellite_id'], evidence['encounter_id']


@dataclass(frozen=True)
class Encounter:
    object_ids: tuple[int, int]
    names: tuple[str, str]
    tca: datetime
    distance_km: float
    probability: float | None

    @property
    def identity(self) -> str:
        a, b = sorted(self.object_ids)
        return f'socrates:{a}:{b}:{self.tca.isoformat()}'

    @property
    def normalized(self) -> tuple[Any, ...]:
        objects = tuple(sorted(zip(self.object_ids, self.names)))
        return objects, self.tca, self.distance_km, self.probability


def normalize(raw: bytes) -> tuple[list[Encounter], list[str]]:
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
    required = {'NORAD_CAT_ID_1', 'NORAD_CAT_ID_2', 'TCA', 'TCA_RANGE', 'MAX_PROB'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('unsupported SOCRATES CSV header')
    encounters, diagnostics = [], []
    try:
        for number, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('row has the wrong number of CSV fields')
                ids = (int(row['NORAD_CAT_ID_1']), int(row['NORAD_CAT_ID_2']))
                if min(ids) <= 0 or ids[0] == ids[1]:
                    raise ValueError('invalid NORAD identity pair')
                tca = datetime.fromisoformat(row['TCA'])
                if tca.tzinfo is None:
                    tca = tca.replace(tzinfo=timezone.utc)  # Provider explicitly documents UTC.
                tca = tca.astimezone(timezone.utc)
                distance = float(row['TCA_RANGE'])  # Provider already supplies kilometers.
                if not math.isfinite(distance) or distance < 0:
                    raise ValueError('distance must be finite and nonnegative')
                probability = None
                try:
                    candidate = float(row['MAX_PROB'])  # Scientific notation, fraction; never percent.
                    if not math.isfinite(candidate) or not 0 <= candidate <= 1:
                        raise ValueError('probability out of range')
                    probability = candidate
                except (TypeError, ValueError):
                    diagnostics.append(f'row {number}: missing/unsupported MAX_PROB; cannot qualify')
                encounters.append(Encounter(ids, (row.get('OBJECT_NAME_1', ''), row.get('OBJECT_NAME_2', '')),
                                            tca, distance, probability))
            except (TypeError, ValueError, KeyError) as error:
                raise ValueError(f'invalid SOCRATES row {number}: {error}') from error
    except csv.Error as error:
        raise ValueError(f'invalid SOCRATES CSV: {error}') from error
    if not encounters:
        raise ValueError('report contains no encounters')
    return encounters, diagnostics


def build_inputs(archive: ReportArchive, scenario: Scenario, *, injection_time: datetime | None = None,
                 pre_padding_s: float | None = None, post_padding_s: float | None = None, threshold: float = 0.0001,
                 satellite_ids: tuple[str, ...] | None = None,
                 encounter_ids: tuple[str, ...] | None = None,
                 identity_mapping: dict[int, str] | None = None,
                 encounter_policies: dict[str, EncounterOutagePolicy] | None = None) -> dict[str, Any]:
    default_policy = None
    if any(value is not None for value in (injection_time, pre_padding_s, post_padding_s)):
        if injection_time is None or pre_padding_s is None or post_padding_s is None:
            raise ValueError('scalar defaults require injection time and both padding values')
        default_policy = EncounterOutagePolicy(injection_time, pre_padding_s, post_padding_s)
    if default_policy is None and not encounter_policies:
        raise ValueError('explicit outage policy required')
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
        raise ValueError('threshold must be finite')
    if threshold != 0.0001:
        raise ValueError('socrates-outage-v1 requires threshold 0.0001; a new threshold requires a versioned policy')
    threshold = float(threshold)
    policies = encounter_policies or {}
    for configured_policy in ([default_policy] if default_policy is not None else []) + list(policies.values()):
        if not scenario.start_time <= configured_policy.injection_time <= scenario.end_time:
            raise ValueError('injection outside Scenario horizon')
        if archive.available_at > configured_policy.injection_time:
            raise ValueError('evidence unavailable at injection time')
    rows, diagnostics = normalize(archive.raw)
    selected = set(satellite_ids) if satellite_ids is not None else {sat.id for sat in scenario.satellites}
    if not selected or selected - {sat.id for sat in scenario.satellites}:
        raise ValueError('selected Satellite not in Scenario')
    mapping = identity_mapping or {}
    by_identity: dict[int, list[str]] = {}
    for sat in scenario.satellites:
        if sat.orbit:
            by_identity.setdefault(sat.orbit.norad_id, []).append(sat.id)
        elif satellite_ids is not None and sat.id in selected:
            raise ValueError(f'selected Satellite {sat.id} has no stored orbital identity')
    for norad, sat_id in mapping.items():
        if sat_id not in by_identity.get(norad, []) or sat_id not in selected:
            raise ValueError('explicit identity mapping does not match selected stored orbit')
    matches: dict[int, str] = {}
    for norad, candidates in by_identity.items():
        active = set(candidates) & selected
        if not active:
            continue
        if len(candidates) > 1 and norad not in mapping:
            raise ValueError(f'ambiguous NORAD {norad}; explicit identity mapping required')
        matches[norad] = mapping.get(norad, next(iter(active)))
    groups: dict[str, list[Encounter]] = {}
    for row in rows:
        groups.setdefault(row.identity, []).append(row)
    if encounter_ids is not None and set(encounter_ids) - groups.keys():
        raise ValueError('selected encounter not found in report')
    if policies.keys() - groups.keys():
        raise ValueError('configured encounter not found in report')
    if encounter_ids is not None and policies.keys() - set(encounter_ids):
        raise ValueError('configured encounter is outside explicit selection')
    if encounter_ids is None and default_policy is None:
        encounter_ids = tuple(policies)
    inputs: list[dict[str, Any]] = []
    matched_satellites: set[str] = set()
    unmatched = nonqualifying_count = 0
    for identity, versions in sorted(groups.items()):
        if encounter_ids is not None and identity not in encounter_ids:
            continue
        policy = policies.get(identity, default_policy)
        if policy is None:
            raise ValueError(f'missing outage policy for {identity}')
        row = versions[0]
        targets = [(norad, matches[norad]) for norad in row.object_ids if norad in matches]
        if not targets:
            unmatched += 1
            continue
        if len({version.normalized for version in versions}) > 1:
            raise ValueError(f'conflicting selected encounter {identity}')
        matched_satellites.update(sat_id for _, sat_id in targets)
        if row.probability is None or row.probability < threshold:
            nonqualifying_count += 1
            continue
        start, end = outage_interval(row.tca, policy.pre_padding_s, policy.post_padding_s)
        if policy.injection_time > start:
            raise ValueError(f'injection later than outage start for {identity}')
        if not scenario.start_time <= start < end <= scenario.end_time:
            raise ValueError(f'outage outside Scenario horizon for {identity}')
        if archive.metadata.get('coverage_start') and not (
            instant(archive.metadata['coverage_start']) <= row.tca <= instant(archive.metadata['coverage_end'])
        ):
            raise ValueError('encounter outside source coverage')
        for norad, sat_id in targets:
            counterpart = next(item for item in row.object_ids if item != norad)
            evidence = ConjunctionEvidence(
                source=f"{archive.metadata['source']}; {archive.metadata['source_url']}; sha256:{archive.metadata['sha256']}",
                encounter_id=identity, matched_norad_id=norad, counterpart_norad_id=counterpart,
                tca=row.tca, miss_distance_km=row.distance_km, maximum_probability=row.probability,
                threshold=threshold, policy_version='socrates-outage-v1',
                pre_padding_s=policy.pre_padding_s, post_padding_s=policy.post_padding_s)
            evidence.validate(start, end)
            inputs.append({'event_type': 'SATELLITE_UNAVAILABLE', 'injection_time': policy.injection_time.isoformat(),
                           'payload': {'satellite_id': sat_id, 'outage_start': start.isoformat(),
                                       'outage_end': end.isoformat(), 'conjunction': evidence.to_dict()},
                           'source_objects': [{'norad_id': n, 'name': name} for n, name in zip(row.object_ids, row.names)]})
    if satellite_ids is not None and selected - matched_satellites:
        raise ValueError(f'selected Satellites unmatched: {sorted(selected - matched_satellites)}')
    inputs.sort(key=outage_input_sort_key)
    metadata = {'scenario_id': scenario.id, 'source': archive.metadata,
                'policy_version': 'socrates-outage-v1', 'threshold': threshold,
                'mapping': {str(n): sat for n, sat in sorted(matches.items())}}
    if default_policy is not None:
        metadata.update(default_policy.to_dict())
    if encounter_policies is not None:
        metadata['encounter_policies'] = {identity: policy.to_dict() for identity, policy in sorted(policies.items())}
    return {'metadata': metadata,
            'summary': {'unmatched_encounters': unmatched, 'nonqualifying_encounters': nonqualifying_count,
                        'diagnostics': diagnostics}, 'inputs': inputs}
