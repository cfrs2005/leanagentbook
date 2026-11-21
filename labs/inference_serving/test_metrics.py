"""Offline metric checks; no model dependencies or fabricated performance runs."""
from pathlib import Path
import unittest
from report import metrics, quantile, summarize


class MetricsTest(unittest.TestCase):
    def row(self):
        return {'error': None, 'duration_s': 1.0, 'requested_input_tokens': 32,
                'requested_output_tokens': 3,
                'events': [{'type': 'token', 'index': i + 1, 'client_elapsed_s': t,
                            'server_elapsed_s': t - .01} for i, t in enumerate([.2, .3, .7])] +
                          [{'type': 'done', 'input_tokens': 32, 'output_tokens': 3,
                            'queue_s': .1, 'process_peak_rss_bytes': 1024}]}

    def test_first_token_is_not_completion(self):
        value = metrics(self.row())
        self.assertEqual(value['ttft_s'], .2)
        self.assertAlmostEqual(value['tpot_s'], .25)
        self.assertEqual(value['e2e_s'], 1.0)

    def test_single_token_tpot_undefined(self):
        row = self.row()
        row['events'] = [row['events'][0], row['events'][-1]]
        row['events'][-1]['output_tokens'] = row['requested_output_tokens'] = 1
        self.assertIsNone(metrics(row)['tpot_s'])

    def test_tail_with_small_sample(self):
        self.assertEqual(quantile(list(range(12)), .95), 11)
        self.assertEqual(quantile(list(range(12)), .99), 11)
        self.assertIsNone(quantile([], .99))

    def test_failed_stream_excluded(self):
        row = self.row()
        row['error'] = 'timeout'
        self.assertIsNone(metrics(row))

    def test_corrupt_counts_and_order_rejected(self):
        for field, value in [('output_tokens', 2), ('input_tokens', 33)]:
            row = self.row()
            row['events'][-1][field] = value
            with self.assertRaises(ValueError):
                metrics(row)
        row = self.row()
        row['events'][1]['client_elapsed_s'] = .1
        with self.assertRaises(ValueError):
            metrics(row)

    def test_recorded_grid(self):
        cells = summarize(Path(__file__).with_name('results'))
        self.assertEqual(len(cells), 8)
        self.assertEqual(sum(c['successes'] for c in cells), 96)
        self.assertEqual(sum(c['errors'] for c in cells), 0)
        for cell in cells:
            self.assertEqual(cell['actual_peak_http_concurrency'], cell['concurrency'])
            self.assertEqual(cell['itl_n'], 12 * (cell['output_tokens'] - 1))
            self.assertGreater(cell['output_tokens_per_s'], 0)


if __name__ == '__main__':
    unittest.main()
