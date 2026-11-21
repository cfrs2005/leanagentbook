"""Run new prompts through Router and pinned local models; no record lookup."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

from live_provider import LocalModelProvider
from router import Router, normalized

ROOT = Path(__file__).resolve().parent
SCOPE = ('course', 'reader', 'acl-v1')
CASES = [
    {'id': 'new_simple', 'prompt': 'Answer with one number: 23 + 19?', 'schema': 'number', 'expected': '42'},
    {'id': 'new_complex', 'prompt': 'A warehouse had twenty boxes in storage at the beginning of the day. Workers delivered seven more boxes and then shipped nine boxes to a customer. How many boxes remain in the warehouse? Answer with one number only.', 'schema': 'number', 'expected': '18'},
    {'id': 'new_fallback', 'prompt': 'Answer yes or no: Is a penguin a bird?', 'schema': 'yes_no', 'expected': 'yes'},
]


def run(hub, output):
    if output.exists():
        raise FileExistsError('Use a new output directory')
    recorded = {r['prompt'] for r in json.loads((ROOT / 'observations.json').read_text())['observations']}
    assert all(case['prompt'] not in recorded for case in CASES)
    provider = LocalModelProvider(hub)
    permissions = {SCOPE: {'small', 'base'}}
    router = Router(provider, threshold=16, allowed_models=lambda scope: permissions.get(scope, set()))
    traces = []

    def request(label, case, scope=SCOPE, **kwargs):
        before = len(provider.calls)
        started = time.perf_counter()
        result = router.run(case['prompt'], case['schema'], scope, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        traces.append({'id': label, 'prompt': case['prompt'], 'expected': case['expected'],
                       'word_count': len(case['prompt'].split()), 'end_to_end_ms': elapsed,
                       'new_provider_calls': len(provider.calls)-before,
                       'correct': result['status'] == 'accepted' and normalized(result['answer']) == case['expected'],
                       **result})
        print(label, result['status'], repr(result['answer']), flush=True)
        return result

    for case in CASES[:2]:
        request(case['id']+'_cold', case)
        request(case['id']+'_repeat', case)
    # A completed simple answer must populate cache; revoke permission before reading it.
    permissions[SCOPE] = set()
    request('revoked_scope_cached_prompt', CASES[0])
    permissions[SCOPE] = {'small', 'base'}
    request('unknown_scope', CASES[0], scope=('course', 'outsider', 'acl-v1'))
    request('budget_denied', CASES[0], budget=1, cache=False)
    permissions[SCOPE] = {'small'}
    request('selected_model_denied', CASES[1], cache=False)
    permissions[SCOPE] = {'small', 'base'}
    provider.fail_once = 'small'
    request('injected_small_failure_then_real_base', CASES[2], cache=False)

    by_id = {row['id']: row for row in traces}
    assert by_id['new_simple_cold']['attempts'][0]['model'] == 'small'
    assert by_id['new_complex_cold']['attempts'][0]['model'] == 'base'
    assert by_id['new_simple_repeat']['cache_hit']
    assert by_id['new_simple_repeat']['new_provider_calls'] == 0
    for name in ('revoked_scope_cached_prompt', 'unknown_scope', 'selected_model_denied'):
        assert by_id[name]['status'] == 'forbidden' and by_id[name]['new_provider_calls'] == 0
    assert by_id['budget_denied']['status'] == 'budget_exhausted'
    assert by_id['budget_denied']['new_provider_calls'] == 0
    fallback = by_id['injected_small_failure_then_real_base']['attempts']
    assert len(fallback) == 2 and fallback[0]['fault_injected']
    assert fallback[1]['model'] == 'base' and fallback[1]['status'] == 'ok' and not fallback[1]['fault_injected']
    report = {'mode': 'live_local_routing', 'models': provider.models,
              'environment': {'python': platform.python_version(), 'machine': platform.machine(),
                              'device': 'cpu', 'dtype': 'float32', 'threads': 2,
                              'packages': {p: importlib.metadata.version(p) for p in ('torch', 'transformers')}},
              'load_ms': provider.load_ms, 'max_new_tokens': provider.max_output,
              'policy': '16 whitespace-delimited words; length is a teaching proxy, not measured difficulty',
              'pricing': 'Synthetic credits: small/base 1/4 per 1000 input tokens; output multiplier 2; not money',
              'timing': 'end_to_end_ms measures Router.run including cache/authorization/token estimate; model loads excluded. recorded_backend_ms retains legacy name and sums actual live calls here. cold means answer-cache cold, not process cold.',
              'failure': 'One controlled pre-generation small failure; zero model tokens consumed; actual base generation follows. Not a real network outage.',
              'limits': 'New synthetic prompts, not a blinded quality benchmark. Larger base is not guaranteed better. Static internal permission fixture is not authentication.',
              'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                for name in ('router.py', 'live_provider.py', 'run_live.py', 'models.json')},
              'traces': traces, 'provider_calls': provider.calls, 'checks_passed': True}
    output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Saved report.json; all integration checks passed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hub', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.hub, args.output)
