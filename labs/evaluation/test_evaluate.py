"""Behavioral tests for executor, metrics, dataset coverage and release gate."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluate import ROOT, classification, execute, faithfulness, gate, load_dataset, ranking, summarize, wilson


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_dataset(ROOT/'dataset.json')
        cls.corpus = json.loads((ROOT/'corpus.json').read_text())

    def report(self, profile='baseline'):
        traces = {c['case_id']: execute(c['input'], self.corpus, profile) for c in self.data['cases']}
        r = summarize(self.data['cases'], traces, self.corpus)
        r.update(dataset_sha256='same', corpus_sha256='same')
        return r

    def test_dataset_coverage(self):
        cases = self.data['cases']
        self.assertEqual(len(cases), 60)
        self.assertEqual(len({c['category'] for c in cases}), 10)
        self.assertEqual(len({json.dumps(c['input'], sort_keys=True) for c in cases}), 60)

    def test_all_gold_results_and_calls(self):
        for c in self.data['cases']:
            with self.subTest(case=c['case_id']):
                t = execute(c['input'], self.corpus)
                self.assertEqual(t['result'], c['expected_result'])
                self.assertEqual([{k: x[k] for k in ('tool', 'args')} for x in t['calls']], c['expected_tools'])

    def test_recovery_observations(self):
        t = execute(dict(intent='recover', key='bolt', failures=1), self.corpus)
        self.assertEqual([x['observation'] for x in t['calls']], ['temporary_error', 12])

    def test_retry_budget(self):
        t = execute(dict(intent='recover', key='bolt', failures=100), self.corpus)
        self.assertEqual(len(t['calls']), 2)
        self.assertEqual(t['result'], 'retry_exhausted')

    def test_refusal_no_tool(self):
        t = execute(dict(intent='refuse', action='delete_all', authorized=False), self.corpus)
        self.assertEqual(t['calls'], [])
        self.assertEqual(t['result'], 'refused')

    def test_multistep_dependency(self):
        t = execute(dict(intent='workflow', key='wheel', quantity=4), self.corpus)
        self.assertEqual(t['calls'][1]['args'], {'a': 4, 'b': 4})
        self.assertEqual(t['result'], 'available')

    def test_classification_hand_calculation(self):
        m = classification(['a', 'a', 'b', 'b'], ['a', 'b', 'b', 'b'])
        self.assertEqual(m['accuracy'], .75)
        self.assertAlmostEqual(m['per_class']['a']['precision'], 1)
        self.assertAlmostEqual(m['per_class']['a']['recall'], .5)
        self.assertAlmostEqual(m['macro_f1'], (2/3+.8)/2)

    def test_zero_division_convention(self):
        m = classification(['a'], ['b'])
        self.assertEqual(m['macro_f1'], 0)
        with self.assertRaises(ValueError): classification([], [])

    def test_ranking_known_values(self):
        m = ranking(['irrelevant', 'a'], {'a': 2, 'b': 1})
        self.assertEqual(m['recall_at_k'], .5)
        self.assertEqual(m['mrr_at_k'], .5)
        self.assertAlmostEqual(m['ndcg_at_k'], (3/1.584962500721156)/(3+1/1.584962500721156))

    def test_no_relevant_and_duplicate_docs(self):
        self.assertIsNone(ranking([], {}))
        with self.assertRaises(ValueError): ranking(['a', 'a'], {'a': 1})
        self.assertEqual(ranking([], {'a': 1})['ndcg_at_k'], 0)

    def test_faithfulness_requires_retrieved_evidence(self):
        claims = [dict(fact='charge_before_use', citation='d1'), dict(fact='made_up', citation='d1')]
        self.assertEqual(faithfulness(claims, ['d1'], self.corpus), .5)
        self.assertEqual(faithfulness(claims, [], self.corpus), 0)
        self.assertIsNone(faithfulness([], [], self.corpus))

    def test_wilson_boundaries(self):
        lo, hi = wilson(60, 60)
        self.assertAlmostEqual(lo, .93983, places=4)
        self.assertAlmostEqual(hi, 1)
        self.assertAlmostEqual(wilson(0, 60)[0], 0)
        with self.assertRaises(ValueError): wilson(1, 0)

    def test_trace_coverage(self):
        with self.assertRaises(ValueError): summarize(self.data['cases'], {}, self.corpus)

    def test_empty_and_duplicate_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'data.json'
            for cases in ([], [self.data['cases'][0]]*2):
                p.write_text(json.dumps({'version': 'test', 'cases': cases}))
                with self.assertRaises(ValueError): load_dataset(p)

    def test_baseline_and_regression_gate(self):
        baseline, regression = self.report(), self.report('regressed')
        self.assertTrue(gate(baseline)['passed'])
        self.assertFalse(gate(regression, baseline)['passed'])
        self.assertEqual(regression['agent']['safety_violations'], 6)
        self.assertEqual(sum(d['success'] for d in regression['cases']), 32)
        self.assertIn('recovery', regression['failures'])

    def test_incomparable_baseline(self):
        r = self.report()
        old = copy.deepcopy(r)
        old['corpus_sha256'] = 'changed'
        self.assertIn('incomparable dataset or corpus', gate(r, old)['reasons'])

    def test_argument_error_even_correct_result(self):
        traces = {c['case_id']: execute(c['input'], self.corpus) for c in self.data['cases']}
        traces['arithmetic-01']['calls'][0]['args']['a'] = 999
        r = summarize(self.data['cases'], traces, self.corpus)
        self.assertTrue(r['cases'][0]['result_ok'])
        self.assertFalse(r['cases'][0]['success'])

    def test_cli_exit_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd = [sys.executable, str(ROOT/'evaluate.py'), '--output', str(out)]
            good = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertTrue((out/'traces.json').exists())
            bad = subprocess.run(cmd+['--profile', 'regressed', '--baseline', str(out/'report.json')], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertFalse(json.loads((out/'report.json').read_text())['gate']['passed'])
            invalid = subprocess.run(cmd+['--dataset', str(out/'absent.json')], capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)


if __name__ == '__main__':
    unittest.main()
