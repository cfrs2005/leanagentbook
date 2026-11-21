"""Parse bounded synthetic device logs and correlate clock intervals to event windows."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from platform_app import ROOT, canonical, envelope, make_report

FIELDS = {'schema', 'synthetic', 'tenant', 'device', 'event_id', 'sequence',
          'device_time_ms', 'level', 'code', 'software_version', 'config_version'}


def correlate(raw, payload, diagnosis, *, clock_offset_ms=100, uncertainty_ms=20):
    if not isinstance(raw, str) or not 0 < len(raw.encode()) <= 16384:
        raise ValueError('Log input must be nonempty and at most 16 KiB')
    if type(clock_offset_ms) is not int or abs(clock_offset_ms) > 60000:
        raise ValueError('Invalid clock offset')
    if type(uncertainty_ms) is not int or not 0 <= uncertainty_ms <= 1000:
        raise ValueError('Invalid clock uncertainty')
    if hashlib.sha256(payload['csv'].encode()).hexdigest() != diagnosis['source']['sha256']:
        raise ValueError('Report does not belong to this sensor payload')
    rows = raw.splitlines()
    if len(rows) > 128:
        raise ValueError('Too many log records')
    output, previous = [], -1
    for line_number, line in enumerate(rows, 1):
        record = json.loads(line)
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise ValueError('Unsupported log schema fields')
        if record['schema'] != 'synthetic-device-log-v1' or record['synthetic'] is not True:
            raise ValueError('Only synthetic logs are supported')
        for field in ('tenant', 'device', 'event_id', 'software_version', 'config_version'):
            if record[field] != payload[field]:
                raise ValueError('Device, event or version mismatch')
        sequence = record['sequence']
        if type(sequence) is not int or not previous < sequence <= 1000000:
            raise ValueError('Sequence must increase without duplicates')
        previous = sequence
        if type(record['device_time_ms']) is not int or not 0 <= record['device_time_ms'] <= 3660000:
            raise ValueError('Invalid relative device time')
        if record['level'] not in ('INFO', 'WARN', 'ERROR'):
            raise ValueError('Invalid log level')
        if not isinstance(record['code'], str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,63}', record['code']):
            raise ValueError('Invalid event code')
        normalized = record['device_time_ms'] - clock_offset_ms
        low, high = normalized - uncertainty_ms, normalized + uncertainty_ms
        candidates, certain = [], False
        for index, event in enumerate(diagnosis['events']):
            start = event['window']['start_s'] * 1000
            end = event['window']['end_exclusive_s'] * 1000
            if low < end and high >= start:
                candidates.append(index)
                if low >= start and high < end:
                    certain = True
        association = ('matched' if len(candidates) == 1 and certain else
                       'boundary_ambiguous' if candidates else 'outside_observed_windows')
        output.append({'source_line': line_number, 'sequence': sequence, 'code': record['code'],
                       'level': record['level'], 'device_time_ms': record['device_time_ms'],
                       'normalized_time_ms': normalized, 'time_interval_ms': [low, high],
                       'candidate_window_indices': candidates, 'association': association})
    return {'schema': 'log-window-association-v1', 'synthetic': True,
            'log_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'sensor_sha256': diagnosis['source']['sha256'],
            'clock': {'basis': 'Synthetic known offset, not estimated from production data',
                      'offset_ms': clock_offset_ms, 'uncertainty_ms': uncertainty_ms,
                      'origin': 'Same synthetic recording start as sensor CSV; not wall-clock UTC'},
            'identity': {k: payload[k] for k in ('tenant', 'device', 'event_id', 'software_version', 'config_version')},
            'records': output, 'root_cause_confirmed': False,
            'scope': 'Time correlation only; device log codes are observations, not verified fault causes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to((ROOT / 'results').resolve()):
        parser.error('Published evidence is read-only')
    payload = envelope('abnormal', 'abnormal')
    report = make_report(payload)
    raw = (ROOT / 'fixtures' / 'device-events.jsonl').read_text()
    report['device_log_evidence'] = correlate(raw, payload, report['diagnosis'])
    with args.output.open('x') as stream:
        stream.write(canonical(report) + '\n')
    print(json.dumps({'records': len(report['device_log_evidence']['records']),
                      'associations': [r['association'] for r in report['device_log_evidence']['records']],
                      'automatic_control': report['automatic_control']}))


if __name__ == '__main__':
    main()
