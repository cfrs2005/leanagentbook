"""Analytic identities, evidence failures and capability boundary tests."""
import unittest
from diagnosis import (NODES, ReadOnlyTools, confounding_example, counterfactual_temperature,
                       diagnose, generate, infer, probability, scm, score)


class DiagnosisTests(unittest.TestCase):
    def test_confounding_reversal(self):
        r = confounding_example()
        self.assertAlmostEqual(r['observational']['1'], .64)
        self.assertAlmostEqual(r['observational']['0'], .26)
        self.assertAlmostEqual(r['interventional']['1'], .4)
        self.assertAlmostEqual(r['interventional']['0'], .5)

    def test_bayes_known_answer(self):
        likelihood = .05 + .7 + .1*.4
        marginal = .12*likelihood + .88*(.05 + .1*.4)
        self.assertAlmostEqual(infer('bearing', {'vibration': 1}), .12*likelihood/marginal)

    def test_priors_and_truncation(self):
        self.assertAlmostEqual(infer('bearing'), .12)
        self.assertAlmostEqual(infer('temperature', intervention={'load': 0}), .05+.25*.12+.3*.15)
        self.assertAlmostEqual(infer('load', intervention={'load': 1}), 1.)

    def test_same_individual_counterfactual(self):
        u = dict(zip(NODES, (.2, .05, .8, .4, .4, .2)))
        factual = scm(u)
        changed = scm(u, {'load': 0})
        self.assertEqual((factual['temperature'], changed['temperature']), (1, 0))
        self.assertEqual(factual['bearing'], changed['bearing'])
        self.assertAlmostEqual(counterfactual_temperature(factual, 0), .3/.65)
        self.assertEqual(counterfactual_temperature(factual, 1), 1.)

    def test_all_counterfactual_states(self):
        for row in generate(7, 100):
            row.pop('id')
            for load in (0, 1):
                self.assertTrue(0 <= counterfactual_temperature(row, load) <= 1)
            self.assertAlmostEqual(counterfactual_temperature(row, row['load']), row['temperature'])

    def test_missing_and_uncertainty(self):
        result = diagnose(ReadOnlyTools([]))
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertFalse(result['root_cause_confirmed'])
        self.assertTrue(all(h['missing'] and h['uncertainty_bits'] > 0 for h in result['hypotheses']))

    def test_conflict_stops_inference(self):
        rows = [{'field': 'current', 'value': x, 'source': str(x)} for x in (0, 1)]
        result = diagnose(ReadOnlyTools(rows))
        self.assertEqual(result['status'], 'conflicting_evidence')
        self.assertEqual(result['hypotheses'], [])

    def test_support_and_against(self):
        rows = [{'field': n, 'value': x, 'source': 'synthetic'} for n, x in [('current', 1), ('vibration', 0)]]
        bearing = diagnose(ReadOnlyTools(rows))['hypotheses'][1]
        self.assertTrue(bearing['support'])
        self.assertTrue(bearing['against'])

    def test_unknown_and_invalid(self):
        for evidence in ({'speed': 1}, {'load': True}, {'load': None}, {'load': 2}):
            with self.assertRaises(ValueError):
                infer('bearing', evidence)
        with self.assertRaises(ValueError):
            diagnose(ReadOnlyTools([{'field': 'current', 'value': 1, 'source': 'x', 'command': 'start'}]))
        with self.assertRaises(ValueError):
            infer('temperature', {'load': 0}, {'load': 1})

    def test_denied_tools(self):
        tool = ReadOnlyTools([])
        for name, args in [('set_speed', {}), ('read_synthetic_evidence', {'device': 'real'})]:
            with self.assertRaises(PermissionError):
                tool.call(name, args)
        self.assertEqual(tool.audit, [])

    def test_split_reproducibility(self):
        cal, test = generate(2201, 100), generate(2202, 100)
        self.assertEqual(cal, generate(2201, 100))
        self.assertFalse({r['id'] for r in cal} & {r['id'] for r in test})
        self.assertTrue(0 <= score(test, 0)['brier'] <= 1)
        self.assertEqual(sum(b['count'] for b in score(test, 0)['reliability_bins']), 100)


if __name__ == '__main__':
    unittest.main()
