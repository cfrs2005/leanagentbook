"""Offline CI tests for independently computed boundaries and invariants."""
import json
import math
import unittest
from pathlib import Path
from retrieval import BM25, cosine, dot, l2, metrics, normalize, ranked, rrf, teaching_vector, weighted_fusion


class SimilarityTests(unittest.TestCase):
    def test_known_geometry(self):
        self.assertEqual(dot([3, 4], [0, 1]), 4)
        self.assertEqual(l2([0, 0], [3, 4]), 5)
        self.assertAlmostEqual(cosine([3, 4], [0, 1]), .8)
        self.assertAlmostEqual(cosine([3, 4], [0, 8]), .8)
        self.assertAlmostEqual(cosine([1, 0], [-1, 0]), -1)
        a, b = normalize([3, 4]), normalize([4, 3])
        self.assertAlmostEqual(l2(a, b) ** 2, 2 - 2 * dot(a, b))

    def test_magnitude_changes_dot_order(self):
        q, a, b = [1, 0], [1, 0], [2, 2]
        self.assertGreater(dot(q, b), dot(q, a))
        self.assertGreater(cosine(q, a), cosine(q, b))

    def test_invalid(self):
        for a, b in [([], []), ([1], [1, 2]), ([math.nan], [1]), ([math.inf], [1])]:
            for fn in (dot, cosine, l2):
                with self.assertRaises(ValueError): fn(a, b)
        with self.assertRaises(ValueError): cosine([0, 0], [1, 0])


class FusionTests(unittest.TestCase):
    def test_rrf_manual(self):
        # b: 1/2 + 1/1; a: 1/1; c: 1/2.
        self.assertEqual(rrf([['a','b'],['b','c']],constant=0),['b','a','c'])
        self.assertEqual(rrf([[],['z']]),['z'])
        self.assertEqual(rrf([]),[])
        self.assertEqual(rrf([['b'],['a']]),['a','b'])

    def test_rrf_rejects_duplicate_and_bad_constant(self):
        for constant in (-1, math.nan, math.inf):
            with self.assertRaises(ValueError): rrf([['a']],constant)
        with self.assertRaises(ValueError): rrf([['a','a']])

    def test_weighted_endpoints_and_constant_scores(self):
        a, b = {'x':2,'y':4}, {'x':10,'y':1}
        self.assertEqual(weighted_fusion(a,b,1),['y','x'])
        self.assertEqual(weighted_fusion(a,b,0),['x','y'])
        self.assertEqual(weighted_fusion({'a':5,'b':5},{}),['a','b'])
        self.assertEqual(weighted_fusion({},{}),[])
        with self.assertRaises(ValueError): weighted_fusion(a,b,2)
        with self.assertRaises(ValueError): weighted_fusion({'a':math.nan},b)


class EvaluationTests(unittest.TestCase):
    def test_metric_manual(self):
        result = metrics(['x','b','a'], {'a':2,'b':1},2)
        self.assertEqual(result['recall'], .5)
        self.assertEqual(result['mrr'], .5)
        self.assertAlmostEqual(result['ndcg'], (1/math.log2(3))/(3+1/math.log2(3)))
        self.assertEqual(metrics(['a'],{'a':2},5)['ndcg'],1)
        with self.assertRaises(ValueError): metrics(['a','a'],{'a':1})
        with self.assertRaises(ValueError): metrics(['a'],{})

    def test_bm25_formula_and_unknown(self):
        index = BM25({'a':'red red', 'b':'blue blue'})
        expected = math.log(2) * 2 * 2.2 / 3.2
        self.assertAlmostEqual(index.scores('red')['a'],expected)
        self.assertEqual(index.scores('unknown'),{'a':0,'b':0})
        self.assertEqual(index.scores('red red'),index.scores('red'))
        with self.assertRaises(ValueError): BM25({})
        with self.assertRaises(ValueError): BM25({'a':''})

    def test_dataset_integrity(self):
        root = Path(__file__).resolve().parent
        docs = json.loads((root/'corpus.json').read_text())
        queries = json.loads((root/'judgments.json').read_text())
        ids = {d['id'] for d in docs}
        self.assertEqual(len(ids),len(docs))
        self.assertEqual(len({q['id'] for q in queries}),len(queries))
        self.assertGreaterEqual(len(queries),20)
        self.assertTrue(all(set(q['relevance']) <= ids for q in queries))
        self.assertTrue(all(set(q['relevance'].values()) <= {1,2} for q in queries))
        self.assertEqual({q['split'] for q in queries},{'dev','test'})

    def test_end_to_end_offline(self):
        from evaluate import run
        report = run("offline", 1, 10, 5)
        self.assertEqual(len(report["rows"]), 28 * 5)
        by_query = {}
        for row in report["rows"]:
            by_query.setdefault(row["query"], {})[row["method"]] = row
        for rows in by_query.values():
            self.assertEqual(set(rows["rrf"]["order"]), set(rows["rerank"]["order"]))
            self.assertEqual(rows["rrf"]["candidate_recall"], rows["rerank"]["candidate_recall"])
        for args in [(0,10,5),(1,3,5),(1,33,5)]:
            with self.assertRaises(ValueError): run("offline", *args)

    def test_unknown_teaching_vector_is_defined(self):
        self.assertAlmostEqual(dot(teaching_vector('xyz'),teaching_vector('xyz')),1)
        self.assertEqual(ranked({'b':0,'a':0}),['a','b'])


if __name__ == '__main__':
    unittest.main()
