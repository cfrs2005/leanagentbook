"""Offline temporal-integrity and metric tests; no training dependencies."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from series import CHANNELS, SPLITS, STRIDE, WINDOW, generate, validate, stats, windows, confusion, fit_threshold, event_metrics


class SeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate()
        cls.records, cls.skipped = windows(cls.rows)

    def test_seed_and_contract(self):
        self.assertEqual(self.rows, generate())
        validate(self.rows)
        self.assertEqual(len(self.rows), 12000)
        self.assertEqual(sum(r['label'] for r in self.rows), 1200)

    def test_reject_irregular_nonfinite_and_boolean(self):
        for key, value in [('t', 10), ('current_a', math.nan), ('temperature_c', True), ('label', 2)]:
            rows = deepcopy(self.rows[:3]); rows[1][key] = value
            with self.assertRaises(ValueError):
                validate(rows)

    def test_raw_intervals_never_cross_splits(self):
        covered = {}
        for split, (start, end) in SPLITS.items():
            group = [r for r in self.records if r['split'] == split]
            self.assertTrue(group)
            self.assertTrue(all(start <= r['start'] <= r['end'] < end for r in group))
            covered[split] = {t for r in group for t in range(r['start'], r['end'] + 1)}
        self.assertFalse(covered['train'] & covered['dev'])
        self.assertFalse(covered['train'] & covered['test'])
        self.assertFalse(covered['dev'] & covered['test'])

    def test_future_changes_do_not_change_earlier_features(self):
        changed = deepcopy(self.rows)
        for row in changed[8400:]:
            for key in CHANNELS:
                row[key] = 99999
            row['label'] = 1 - row['label']
        records, _ = windows(changed)
        self.assertEqual([r for r in self.records if r['split'] != 'test'],
                         [r for r in records if r['split'] != 'test'])

    def test_feature_dimensions_and_time_label(self):
        self.assertTrue(all(len(r['features']) == 21 for r in self.records))
        self.assertTrue(all(r['label'] == self.rows[r['end']]['label'] for r in self.records))
        self.assertTrue(all(r['end'] - r['start'] == WINDOW - 1 for r in self.records))

    def test_long_missing_gap_is_rejected_not_interpolated(self):
        self.assertTrue(any(r['start'] <= 8505 <= r['end'] for r in self.skipped))
        self.assertFalse(any(r['start'] <= 8505 <= r['end'] for r in self.records))

    def test_missing_initial_value_cannot_use_future(self):
        rows = [dict(t=t, label=0, **{c: 1 for c in CHANNELS}) for t in range(60)]
        rows[0]['current_a'] = None
        good, skipped = windows(rows)
        self.assertEqual(good, [])
        self.assertEqual(len(skipped), 1)

    def test_known_statistics(self):
        mean, variance, rms, peak, kurtosis, slope = stats([1, 2, 3])
        self.assertEqual(mean, 2)
        self.assertAlmostEqual(variance, 2 / 3)
        self.assertAlmostEqual(rms, math.sqrt(14 / 3))
        self.assertEqual(peak, 3)
        self.assertAlmostEqual(kurtosis, 1.5)
        self.assertEqual(slope, 1)

    def test_confusion_and_zero_prediction(self):
        result = confusion([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertEqual([result[k] for k in ('tp', 'fp', 'fn', 'tn')], [1, 1, 1, 1])
        self.assertEqual(result['f1'], .5)
        result = confusion([1, 0], [0, 0])
        self.assertIsNone(result['precision'])
        self.assertEqual(result['recall'], 0)

    def test_metric_input_failure(self):
        for labels, predicted in [([], []), ([1], []), ([2], [1])]:
            with self.assertRaises(ValueError):
                confusion(labels, predicted)

    def test_threshold_uses_dev_only(self):
        dev = [dict(split='dev', label=y) for y in [0, 0, 1, 1]]
        result = fit_threshold(dev, [.1, .2, .7, .8])
        self.assertEqual(result['threshold'], .7)
        for bad in [dict(split='test', label=1), dict(split='train', label=1)]:
            with self.assertRaises(ValueError):
                fit_threshold(dev + [bad], [.1, .2, .7, .8, .9])
        with self.assertRaises(ValueError):
            fit_threshold(dev, [.1, .2, math.inf, .8])

    def test_signed_lead_and_missed_events(self):
        records = [dict(start=t - 59, end=t) for t in range(59, 360, 15)]
        events = [dict(id='one', kind='x', onset=150, end=200), dict(id='two', kind='y', onset=270, end=300)]
        result = event_metrics(records, [int(r['end'] == 134) for r in records], events)
        self.assertEqual(result['events'][0]['lead_seconds'], 16)
        self.assertIsNone(result['events'][1]['lead_seconds'])
        late = event_metrics(records, [int(r['end'] == 164) for r in records], events)
        self.assertEqual(late['events'][0]['lead_seconds'], -14)

    def test_false_alarm_episode_grouping(self):
        records = [dict(start=t - 59, end=t) for t in range(59, 360, 15)]
        result = event_metrics(records, [int(r['end'] in (59, 74, 119)) for r in records], [])
        self.assertEqual(result['false_alarm_episodes'], 2)

    def test_committed_report_replays_metrics_without_ml(self):
        path = Path(__file__).parent / 'results' / 'report.json'
        if not path.exists():
            self.skipTest('Real-model report has not been collected yet')
        report = json.loads(path.read_text())
        self.assertEqual(len(report['windows']), len(self.records))
        for saved, current in zip(report['windows'], self.records):
            self.assertEqual({k: v for k, v in saved.items() if k != 'features'},
                             {k: v for k, v in current.items() if k != 'features'})
            self.assertTrue(all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
                                for a, b in zip(saved['features'], current['features'])))
        dev = [r for r in self.records if r['split'] == 'dev']
        test = [r for r in self.records if r['split'] == 'test']
        for name, result in report['results'].items():
            fitted = fit_threshold(dev, report['scores'][name]['dev'])
            self.assertEqual(fitted['threshold'], result['threshold'])
            predicted = [int(s >= result['threshold']) for s in report['scores'][name]['test']]
            self.assertEqual(confusion([r['label'] for r in test], predicted), result['test_metrics'])
            self.assertEqual(event_metrics(test, predicted), result['event_metrics'])


if __name__ == '__main__':
    unittest.main()
