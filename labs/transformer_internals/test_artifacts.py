"""Offline standard-library checks of published numerical evidence."""
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).parent / 'results'


class ArtifactTests(unittest.TestCase):
    def test_report(self):
        report = json.loads((ROOT / 'report.json').read_text())
        self.assertEqual(len(report['checks']), 6)
        self.assertTrue(all(report['checks'].values()))
        for name, value in report['metrics'].items():
            self.assertTrue(math.isfinite(value))
            if name != 'unmasked_prefix_change':
                self.assertLessEqual(value, 1e-12)

    def test_actual_attention(self):
        weights = json.loads((ROOT / 'tensors.json').read_text())['weights'][0]
        self.assertEqual(len(weights), 2)
        for head in weights:
            self.assertEqual(len(head), 6)
            for i, row in enumerate(head):
                self.assertEqual(len(row), 6)
                self.assertAlmostEqual(sum(row), 1)
                self.assertTrue(all(x == 0 for x in row[i + 1:]))

    def test_incremental_output(self):
        full = json.loads((ROOT / 'tensors.json').read_text())['output'][0]
        incremental = json.loads((ROOT / 'incremental_output.json').read_text())[0]
        self.assertEqual(len(full), len(incremental))
        for row, other in zip(full, incremental):
            self.assertEqual(len(row), len(other))
            for a, b in zip(row, other):
                self.assertLessEqual(abs(a - b), 1e-12)


if __name__ == '__main__':
    unittest.main()
