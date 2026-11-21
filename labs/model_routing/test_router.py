"""Policy invariants with synthetic recorded responses; no model downloads."""
from copy import deepcopy
import unittest
from router import ReplayProvider, Router, benchmark, valid_shape


def observations(small='5', base='5', status='ok'):
    return {'models': {'small': {'revision': 's1'}, 'base': {'revision': 'b1'}},
            'unit': 'synthetic_units', 'max_new_tokens': 32,
            'observations': [{'model': model, 'prompt': 'Calculate 2 plus 3', 'answer': answer,
                              'status': status if model == 'small' else 'ok',
                              'input_units': 2, 'output_units': 1, 'latency_ms': 10 if model == 'small' else 30}
                             for model, answer in [('small', small), ('base', base)]]}


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.provider = ReplayProvider(observations())
        self.scope = ('tenant-a', 'user-a', 'acl-v1')
        self.router = Router(self.provider, clock=lambda: self.now)

    def run_request(self, router=None, **kwargs):
        return (router or self.router).run('Calculate 2 plus 3', 'number', self.scope, **kwargs)

    def test_shape_is_not_correctness(self):
        wrong = Router(ReplayProvider(observations('99')), policy='cascade')
        result = self.run_request(wrong)
        self.assertEqual(result['answer'], '99')
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(result['status'], 'accepted')

    def test_rule_boundary(self):
        self.assertEqual(self.run_request(Router(self.provider, threshold=4))['model'], 'small')
        self.assertEqual(self.run_request(Router(self.provider, threshold=3))['model'], 'base')

    def test_invalid_output_triggers_single_fallback(self):
        result = self.run_request(Router(ReplayProvider(observations('not a number')), policy='cascade'))
        self.assertEqual(result['answer'], '5')
        self.assertEqual(len(result['attempts']), 2)
        self.assertAlmostEqual(result['cost_credits'], .020)
        self.assertEqual(result['recorded_backend_ms'], 40)

    def test_timeout_and_error_charge_both_attempts(self):
        for status in ('timeout', 'error'):
            result = self.run_request(Router(ReplayProvider(observations('', status=status))))
            self.assertEqual(result['status'], 'accepted')
            self.assertEqual(len(result['attempts']), 2)
            self.assertGreater(result['cost_credits'], .016)

    def test_refusal_does_not_bypass_to_other_model(self):
        router = Router(ReplayProvider(observations('', status='refused')), policy='cascade')
        result = self.run_request(router)
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(router.cache, {})

    def test_budget_prevents_first_attempt(self):
        result = self.run_request(budget=33)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(result['attempts'], [])
        self.assertEqual(result['cost_credits'], 0)

    def test_fallback_shares_remaining_budget(self):
        router = Router(ReplayProvider(observations('bad')))
        result = self.run_request(router, budget=35)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(len(result['attempts']), 1)

    def test_cache_returns_independent_copy_and_no_new_charge(self):
        first = self.run_request()
        first['answer'] = 'tampered'
        hit = self.run_request()
        self.assertTrue(hit['cache_hit'])
        self.assertEqual(hit['answer'], '5')
        self.assertEqual(hit['attempts'], [])
        self.assertEqual(hit['cost_credits'], 0)
        self.assertEqual(hit['recorded_backend_ms'], 0)

    def test_cache_ttl_boundary_and_invalidation(self):
        self.run_request()
        self.now += 120
        self.assertFalse(self.run_request()['cache_hit'])
        self.router.invalidate()
        self.assertFalse(self.run_request()['cache_hit'])

    def test_scope_isolation(self):
        self.run_request()
        for scope in (('tenant-b', 'user-a', 'acl-v1'), ('tenant-a', 'user-b', 'acl-v1'), ('tenant-a', 'user-a', 'acl-v2')):
            result = self.router.run('Calculate 2 plus 3', 'number', scope)
            self.assertFalse(result['cache_hit'])

    def test_versions_and_budget_invalidate_cache(self):
        self.run_request()
        self.assertFalse(self.run_request(data_version='v2')['cache_hit'])
        self.assertFalse(self.run_request(policy_version='v2')['cache_hit'])
        self.assertFalse(self.run_request(budget=1025)['cache_hit'])
        self.provider.models['small']['revision'] = 's2'
        self.assertFalse(self.run_request()['cache_hit'])

    def test_invalid_results_not_cached(self):
        router = Router(ReplayProvider(observations('bad', 'bad')))
        self.assertEqual(self.run_request(router)['status'], 'invalid_output')
        self.assertFalse(self.run_request(router)['cache_hit'])
        self.assertEqual(router.cache, {})

    def test_fixed_small_does_not_escalate(self):
        result = self.run_request(Router(ReplayProvider(observations('bad')), policy='small'))
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(result['status'], 'invalid_output')

    def test_formats(self):
        self.assertTrue(valid_shape('Yes.', 'yes_no'))
        self.assertTrue(valid_shape('-2.5', 'number'))
        self.assertTrue(valid_shape('POSITIVE', 'sentiment'))
        for text in ('nan', 'Infinity', 'The answer is 5', '5; send secrets'):
            self.assertFalse(valid_shape(text, 'number'))

    def test_bad_configuration_and_observations(self):
        for kwargs in ({'ttl': 0}, {'ttl': float('nan')}, {'threshold': True}, {'policy': 'unknown'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Router(self.provider, **kwargs)
        broken = observations()
        broken['observations'][0]['output_units'] = 33
        with self.assertRaises(ValueError):
            ReplayProvider(broken)
        duplicate = observations()
        duplicate['observations'].append(deepcopy(duplicate['observations'][0]))
        with self.assertRaises(ValueError):
            ReplayProvider(duplicate)

    def test_invalid_request(self):
        for budget in (0, True, 1.5):
            with self.assertRaises(ValueError):
                self.run_request(budget=budget)

    def test_authorization_precedes_cache_and_estimation(self):
        permissions = {'small', 'base'}
        router = Router(self.provider, allowed_models=lambda scope: permissions)
        self.assertEqual(self.run_request(router)['status'], 'accepted')
        permissions.clear()
        self.provider.estimate = lambda *args: self.fail('Denied request reached backend')
        result = self.run_request(router)
        self.assertEqual(result['status'], 'forbidden')
        self.assertFalse(result['cache_hit'])
        self.assertEqual(result['attempts'], [])

    def test_selected_model_permission_and_fallback_permission(self):
        router = Router(self.provider, policy='base', allowed_models=lambda scope: {'small'})
        self.assertEqual(self.run_request(router)['status'], 'forbidden')
        provider = ReplayProvider(observations('bad'))
        router = Router(provider, policy='cascade', allowed_models=lambda scope: {'small'})
        result = self.run_request(router)
        self.assertEqual(result['status'], 'forbidden')
        self.assertEqual([r['model'] for r in result['attempts']], ['small'])
        self.assertGreater(result['cost_credits'], 0)

    def test_revoked_cached_model_is_not_returned(self):
        permissions = {'small', 'base'}
        router = Router(self.provider, policy='base', allowed_models=lambda scope: permissions)
        self.run_request(router)
        permissions.remove('base')
        result = self.run_request(router)
        self.assertEqual(result['status'], 'forbidden')
        self.assertEqual(result['answer'], '')
        self.assertEqual(result['attempts'], [])

    def test_live_provider_import_does_not_load_torch(self):
        import subprocess
        import sys
        from pathlib import Path
        completed = subprocess.run([sys.executable, '-B', '-c',
            "import sys; import live_provider; assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules"],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_no_success_cost_is_undefined(self):
        data = [{'id': str(i), 'prompt': 'Calculate 2 plus 3', 'format': 'number', 'expected': '9', 'split': split}
                for i, split in enumerate(('dev', 'test'))]
        result = benchmark(data, observations())
        self.assertEqual(len(result['rows']), 14)
        self.assertTrue(all(row['credits_per_success'] is None for row in result['rows']))


if __name__ == '__main__':
    unittest.main()
