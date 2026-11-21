"""Offline contract tests; numeric fixtures test logic, never impersonate CLIP."""
import copy
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from retrieval import evaluate, fit, lexical, rank, sha256, validate_queries, verify_evidence

ROOT = Path(__file__).resolve().parent


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((ROOT / 'results/raw_scores.json').read_text())
        cls.saved = json.loads((ROOT / 'results/evaluation.json').read_text())

    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_offline_replay_matches_recorded_real_scores(self):
        self.assertEqual(evaluate(self.raw), self.saved)
        provenance = self.raw['provenance']
        self.assertEqual(json.loads((ROOT / 'model-lock.json').read_text())['sha256'],
                         provenance['model_sha256'])
        for file, key in [('data/queries.json', 'query_file_sha256'),
                          ('data/manifest.json', 'manifest_file_sha256'),
                          ('run_clip.py', 'runner_sha256'), ('retrieval.py', 'retrieval_sha256')]:
            self.assertEqual(sha256(ROOT / file), provenance[key])

    def test_test_scores_cannot_change_fitted_parameters(self):
        changed = copy.deepcopy(self.raw)
        for q in changed['queries']:
            if q['split'] == 'test':
                changed['scores'][q['id']]['visual'] = [0.0] * len(changed['items'])
                changed['scores'][q['id']]['text'] = [0.0] * len(changed['items'])
        for mode, res in evaluate(changed).items():
            self.assertEqual(res['fit'], self.saved[mode]['fit'])

    def test_fit_rejects_test_split(self):
        with self.assertRaisesRegex(ValueError, 'development'):
            fit(self.raw['scores'], self.raw['queries'], self.raw['items'], 'visual')

    def test_cross_split_duplicate_rejected(self):
        queries = copy.deepcopy(self.raw['queries'])
        queries[1]['text'] = queries[0]['text']
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate_queries(queries, self.raw['items'])

    def test_blank_query_rejected(self):
        queries = copy.deepcopy(self.raw['queries'])
        queries[0]['text'] = ' '
        with self.assertRaises(ValueError):
            validate_queries(queries, self.raw['items'])

    def test_unknown_must_not_have_relevant_label(self):
        queries = copy.deepcopy(self.raw['queries'])
        queries[-1]['relevant'] = [self.raw['items'][0]['id']]
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            validate_queries(queries, self.raw['items'])

    def test_metadata_filter_cannot_return_other_tenant(self):
        row = next(iter(self.raw['scores'].values()))
        for mode in ('visual', 'text', 'fusion'):
            params = self.saved[mode]['fit']
            self.assertEqual(rank(row, self.raw['items'], mode, params, tenant='other'), [])
            self.assertEqual(rank(row, self.raw['items'], mode, params, collection='missing'), [])

    def test_nonfinite_and_wrong_dimension_rejected(self):
        row = copy.deepcopy(next(iter(self.raw['scores'].values())))
        row['visual'][0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            rank(row, self.raw['items'], 'visual', {})
        row['visual'] = []
        with self.assertRaisesRegex(ValueError, 'length'):
            rank(row, self.raw['items'], 'visual', {})

    def test_all_original_evidence_matches(self):
        for item in self.raw['items']:
            evidence = verify_evidence(item, ROOT / 'data')
            self.assertEqual(evidence['page'], 1)

    def test_corrupted_image_missing_file_and_path_escape_fail_closed(self):
        item = copy.deepcopy(self.raw['items'][0])
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'images').mkdir()
            for field in ('source', 'image'):
                shutil.copyfile(ROOT / 'data' / item[field], data / item[field])
            (data / item['image']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify_evidence(item, data)
            (data / item['image']).unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                verify_evidence(item, data)
        item['source'] = '../retrieval.py'
        with self.assertRaisesRegex(ValueError, 'escaped'):
            verify_evidence(item, ROOT / 'data')

    def test_invalid_region_and_page_rejected(self):
        for field, value in [('bbox_xyxy', [0, 0, 321, 320]), ('page', 2)]:
            item = {**self.raw['items'][0], field: value}
            with self.assertRaisesRegex(ValueError, 'region'):
                verify_evidence(item, ROOT / 'data')

    def test_lexical_paraphrase_score_shift_is_visible(self):
        self.assertGreater(lexical('a red square on a white background', 'red square'),
                           lexical('an illustration of a red four sided square', 'red square'))
        self.assertEqual(self.saved['text']['test_metrics']['known_accepted'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
