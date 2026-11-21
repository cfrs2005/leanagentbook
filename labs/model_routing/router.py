"""Provider-independent routing with optional authorization; default CLI replays records."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parent
RATES = {'small': 1, 'base': 4}  # Hypothetical credits per 1000 input units.


def normalized(text):
    return text.strip().lower().rstrip('.!?').strip()


def valid_shape(text, schema):
    value = normalized(text)
    if schema == 'number':
        return re.fullmatch(r'-?\d+(?:\.\d+)?', value) is not None
    if schema == 'yes_no':
        return value in {'yes', 'no'}
    if schema == 'sentiment':
        return value in {'positive', 'negative'}
    raise ValueError('Unsupported response format')


class ReplayProvider:
    def __init__(self, observations):
        self.models = deepcopy(observations['models'])
        self.unit = observations['unit']
        self.max_output = observations['max_new_tokens']
        self.rows = {}
        for row in observations['observations']:
            key = (row['model'], row['prompt'])
            if key in self.rows:
                raise ValueError('Duplicate observation')
            if (row['model'] not in RATES or row['status'] not in {'ok', 'error', 'timeout', 'refused'}
                    or not isinstance(row['answer'], str)
                    or any(type(row[k]) is not int or row[k] < 0 for k in ('input_units', 'output_units'))
                    or row['output_units'] > self.max_output
                    or type(row['latency_ms']) not in (int, float)
                    or not math.isfinite(row['latency_ms']) or row['latency_ms'] < 0):
                raise ValueError('Invalid observation')
            self.rows[key] = deepcopy(row)

    def estimate(self, model, prompt):
        return self.rows[(model, prompt)]['input_units'] + self.max_output

    def call(self, model, prompt):
        return deepcopy(self.rows[(model, prompt)])


class Router:
    def __init__(self, provider, policy='rules', threshold=16, ttl=120, clock=time.monotonic, allowed_models=None):
        if policy not in {'small', 'base', 'rules', 'cascade'}:
            raise ValueError('Unknown routing policy')
        if (type(threshold) is not int or threshold < 0 or type(ttl) not in (int, float)
                or not math.isfinite(ttl) or ttl <= 0):
            raise ValueError('Invalid policy configuration')
        self.provider, self.policy, self.threshold = provider, policy, threshold
        self.ttl, self.clock, self.cache = ttl, clock, {}
        self.allowed_models = allowed_models

    def run(self, prompt, schema, scope, data_version='v1', policy_version='v1',
            budget=1024, cache=True):
        # Scope is internal context from an authenticated caller, not a login mechanism.
        if (not isinstance(prompt, str) or not prompt or schema not in {'number', 'yes_no', 'sentiment'}
                or type(scope) is not tuple or len(scope) != 3
                or any(not isinstance(value, str) or not value for value in (*scope, data_version, policy_version))
                or type(budget) is not int or budget < 1):
            raise ValueError('Invalid request envelope')
        permitted = set(self.provider.models) if self.allowed_models is None else set(self.allowed_models(scope))
        denied = {'answer': '', 'status': 'forbidden', 'model': None, 'cache_hit': False,
                  'attempts': [], 'cost_credits': 0, 'recorded_backend_ms': 0}
        if not permitted:
            return denied
        key = json.dumps([prompt, schema, scope, data_version, policy_version, self.policy,
                          self.threshold, self.provider.models, self.provider.max_output, budget], sort_keys=True)
        now = self.clock()
        if cache and key in self.cache:
            expires, previous = self.cache[key]
            if now < expires:
                if previous['model'] not in permitted:
                    return denied
                return dict(deepcopy(previous), cache_hit=True, attempts=[], cost_credits=0, recorded_backend_ms=0)
            del self.cache[key]
        if self.policy in {'small', 'base'}:
            first = self.policy
        else:
            first = 'base' if self.policy == 'rules' and len(prompt.split()) > self.threshold else 'small'
        choices = [first]
        if first == 'small' and self.policy in {'rules', 'cascade'}:
            choices.append('base')
        output = {'answer': '', 'status': 'failed', 'model': None, 'cache_hit': False,
                  'attempts': [], 'cost_credits': 0, 'recorded_backend_ms': 0}
        used = 0
        for model in choices:
            if model not in permitted:
                output['status'] = 'forbidden'
                break
            if used + self.provider.estimate(model, prompt) > budget:
                output['status'] = 'budget_exhausted'
                break
            observed = self.provider.call(model, prompt)
            used += observed['input_units'] + observed['output_units']
            output['cost_credits'] += RATES[model] * (observed['input_units'] + 2 * observed['output_units']) / 1000
            output['recorded_backend_ms'] += observed['latency_ms']
            output['attempts'].append(observed)
            output['model'] = model
            if observed['status'] == 'refused':
                output['status'] = 'refused'
                break  # A refusal is not a technical error to bypass with another model.
            if observed['status'] == 'ok' and valid_shape(observed['answer'], schema):
                output.update(answer=observed['answer'], status='accepted')
                break
            output['status'] = 'invalid_output' if observed['status'] == 'ok' else observed['status']
        if cache and output['status'] == 'accepted':
            self.cache[key] = (self.clock() + self.ttl, deepcopy(output))
        return output

    def invalidate(self):
        self.cache.clear()


def benchmark(dataset, observations, warm=False):
    provider = ReplayProvider(observations)
    rows = []
    configurations = [('small', 16), ('base', 16), ('cascade', 16)]
    configurations += [('rules', threshold) for threshold in (8, 16, 24, 32)]
    for policy, threshold in configurations:
        router = Router(provider, policy, threshold)
        outcomes = []
        for record in dataset:
            arguments = (record['prompt'], record['format'], ('tenant-demo', 'user-demo', 'acl-v1'))
            if warm:
                router.run(*arguments)
            answer = router.run(*arguments)
            passed = answer['status'] == 'accepted' and normalized(answer['answer']) == normalized(record['expected'])
            outcomes.append(dict(id=record['id'], split=record['split'], correct=passed, **answer))
        for split in ('dev', 'test'):
            selected = [row for row in outcomes if row['split'] == split]
            successes = sum(row['correct'] for row in selected)
            costs = sum(row['cost_credits'] for row in selected)
            latencies = sorted(row['recorded_backend_ms'] for row in selected)
            rows.append({'policy': policy, 'threshold_words': threshold, 'split': split,
                'requests': len(selected), 'successes': successes, 'accuracy': successes / len(selected),
                'cost_credits': costs, 'credits_per_success': costs / successes if successes else None,
                'recorded_backend_p50_ms': latencies[math.ceil(.5 * len(latencies)) - 1],
                'recorded_backend_p95_ms': latencies[math.ceil(.95 * len(latencies)) - 1],
                'cache_hits': sum(row['cache_hit'] for row in selected), 'results': selected})
    return {'mode': 'warm_exact_cache' if warm else 'cold_policy_replay',
            'unit': provider.unit, 'pricing': 'Hypothetical credits: small=1, base=4 per 1000 input units; output multiplier=2; not money',
            'measurement': 'Sum of recorded backend calls, not measured end-to-end latency; warm mode excludes population cost',
            'rows': rows}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, default=ROOT / 'observations.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--warm', action='store_true')
    args = parser.parse_args()
    observations = json.loads(args.observations.read_text())
    if observations['dataset_sha256'] != hashlib.sha256((ROOT / 'dataset.json').read_bytes()).hexdigest():
        raise ValueError('Observations and dataset differ')
    result = benchmark(json.loads((ROOT / 'dataset.json').read_text()), observations, args.warm)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps([{k: v for k, v in row.items() if k != 'results'} for row in result['rows']], indent=2))
