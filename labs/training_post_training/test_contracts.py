"""Offline checks do not claim to execute Transformers training."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from contracts import load_data, metrics


class ContractsTest(unittest.TestCase):
    def test_split_sizes_and_balance(self):
        data = load_data()
        self.assertEqual({s: len(rows) for s, rows in data.items()}, {'train':36,'dev':12,'test':12})
        for rows in data.values():
            self.assertEqual(len({sum(r['label']==label for r in rows) for label in ('billing','access','hardware')}), 1)

    def test_duplicate_rejected(self):
        data = copy.deepcopy(load_data())
        data['test'][0]['text'] = data['train'][0]['text']
        with tempfile.TemporaryDirectory() as d:
            for s, rows in data.items():
                Path(d, s+'.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaises(ValueError):
                load_data(d)

    def test_invalid_and_empty(self):
        result = metrics([{'label':'billing','prediction':'something else'}])
        self.assertEqual(result['invalid'],1)
        self.assertEqual(result['accuracy'],0)
        with self.assertRaises(ValueError):
            metrics([])

    def test_metrics_not_just_accuracy(self):
        result = metrics([{'label':'billing','prediction':'billing'},
                          {'label':'access','prediction':'billing'},
                          {'label':'hardware','prediction':'hardware'}])
        self.assertAlmostEqual(result['accuracy'],2/3)
        self.assertAlmostEqual(result['macro_f1'],5/9)

    def test_published_evidence(self):
        root = Path(__file__).parent
        report = json.loads((root/'results'/'report.json').read_text())
        for filename, checksum in report['data_sha256'].items():
            self.assertEqual(hashlib.sha256((root/'data'/filename).read_bytes()).hexdigest(), checksum)
        for stage in ('baseline','after'):
            for split, result in report[stage].items():
                self.assertEqual(result['metrics'], metrics(result['predictions']))
                self.assertEqual(len(result['predictions']), len(load_data()[split]))
        self.assertTrue(report['reload']['test_predictions_equal'])
        self.assertLessEqual(report['reload']['max_abs_dev_logits_difference'], 1e-6)
        self.assertFalse(report['selection']['test_used_for_selection'])
        self.assertGreater(report['parameters']['final_update_l2'],0)
        self.assertEqual(len(report['steps']),72)
        self.assertEqual(len(report['curve']),9)
        selected = min(report['curve'][1:],key=lambda row:row['dev_loss'])
        self.assertEqual(selected['epoch'],report['selection']['best_epoch'])


if __name__ == '__main__':
    unittest.main()
