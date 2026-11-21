"""Check scope, timing uncertainty and provenance for synthetic device logs."""
import json
import unittest

from device_logs import correlate
from platform_app import ROOT, envelope, make_report


class DeviceLogTests(unittest.TestCase):
    def setUp(self):
        self.payload = envelope('abnormal', 'abnormal')
        self.diagnosis = make_report(self.payload)['diagnosis']
        self.raw = (ROOT / 'fixtures' / 'device-events.jsonl').read_text()

    def test_time_window_uncertainty_is_not_hidden(self):
        result = correlate(self.raw, self.payload, self.diagnosis)
        rows = result['records']
        self.assertEqual([r['association'] for r in rows],
                         ['matched', 'boundary_ambiguous', 'matched', 'boundary_ambiguous', 'outside_observed_windows'])
        self.assertEqual(rows[1]['candidate_window_indices'], [0, 1])
        self.assertEqual(rows[2]['normalized_time_ms'], 6200)
        self.assertEqual(rows[2]['candidate_window_indices'], [1])
        self.assertFalse(result['root_cause_confirmed'])

    def test_exact_boundary_uses_half_open_interval(self):
        rows = correlate(self.raw, self.payload, self.diagnosis, uncertainty_ms=0)['records']
        self.assertEqual(rows[1]['candidate_window_indices'], [1])
        self.assertEqual(rows[3]['association'], 'outside_observed_windows')

    def test_other_device_version_or_event_is_rejected(self):
        row = json.loads(self.raw.splitlines()[0])
        for field in ('tenant', 'device', 'event_id', 'software_version', 'config_version'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                correlate(json.dumps(dict(row, **{field: 'other'})), self.payload, self.diagnosis)

    def test_invalid_fields_and_repeated_sequence_are_rejected(self):
        row = json.loads(self.raw.splitlines()[0])
        for updates in ({'message': 'unbounded private text'}, {'synthetic': False}, {'device_time_ms': True},
                        {'device_time_ms': -1}, {'level': 'FATAL'}, {'code': 'bad command'}, {'sequence': True}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                correlate(json.dumps(dict(row, **updates)), self.payload, self.diagnosis)
        with self.assertRaises(ValueError):
            correlate(json.dumps(row)+'\n'+json.dumps(row), self.payload, self.diagnosis)
        with self.assertRaises(ValueError):
            correlate('x'*16385, self.payload, self.diagnosis)

    def test_cannot_associate_unrelated_sensor_report(self):
        diagnosis = make_report(envelope('normal'))['diagnosis']
        with self.assertRaises(ValueError):
            correlate(self.raw, self.payload, diagnosis)


if __name__ == '__main__':
    unittest.main()
