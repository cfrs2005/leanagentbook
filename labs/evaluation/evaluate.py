"""Offline evaluation of a scripted task executor; no LLM or external writes."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent
STOCK = {'bolt': 12, 'nut': 0, 'wheel': 4, 'sensor': 2, 'brush': 8}


def execute(task, corpus, profile='baseline'):
    """Consume inputs only. Gold labels are deliberately unavailable here."""
    start = time.perf_counter()
    kind = task['intent']
    calls, retrieved, claims = [], [], []
    attempts = 0

    def call(tool, args):
        nonlocal attempts
        attempts += 1
        args = dict(args)
        if profile == 'regressed' and kind == 'convert':
            args['value'] += 1
        if profile == 'regressed' and kind == 'arithmetic':
            tool = 'compare'
        if tool == 'calculate':
            a, b = args['a'], args['b']
            result = {'add': lambda: a+b, 'subtract': lambda: a-b,
                      'multiply': lambda: a*b, 'divide': lambda: a/b if b else 'division_by_zero'}[args['op']]()
        elif tool == 'convert':
            v = args['value']
            result = {'cm_to_m': lambda: v/100, 'c_to_f': lambda: v*9/5+32,
                      'kg_to_g': lambda: v*1000, 'min_to_s': lambda: v*60}[args['unit']]()
        elif tool == 'aggregate':
            values = args['values']
            result = (sum(values) if args['op'] == 'sum' else
                      'empty_values' if not values else
                      {'mean': statistics.mean, 'max': max, 'min': min}[args['op']](values))
        elif tool == 'lookup':
            result = ('temporary_error' if kind == 'recover' and attempts <= task['failures']
                      else STOCK.get(args['key'], 'not_found'))
        elif tool == 'compare':
            result = 'greater' if args['a'] > args['b'] else 'less' if args['a'] < args['b'] else 'equal'
        elif tool == 'search':
            scores = [(len(set(args['terms']) & set(d['tags'])), d['id']) for d in corpus]
            ranked = [doc for score, doc in sorted(scores, key=lambda x: (-x[0], x[1])) if score]
            result = ranked[:args['k']]
            if profile == 'regressed':
                result = ['d6']
        else:
            raise ValueError(f'Unknown tool: {tool}')
        calls.append(dict(tool=tool, args=args, observation=result))
        return result

    if kind == 'refuse':
        result = 'refused'
        if profile == 'regressed':
            call('lookup', {'key': 'bolt'})
            result = 'unauthorized_action_simulated'
    elif kind == 'clarify':
        result = 'clarify:' + task['missing']
    elif kind in ('lookup', 'recover', 'workflow'):
        result = call('lookup', {'key': task['key']})
        if kind == 'recover' and result == 'temporary_error' and profile != 'regressed':
            result = call('lookup', {'key': task['key']})
        if result == 'temporary_error':
            result = 'retry_exhausted'
        if kind == 'workflow' and isinstance(result, (int, float)):
            comparison = call('compare', {'a': result, 'b': task['quantity']})
            result = 'insufficient' if comparison == 'less' else 'available'
    elif kind == 'retrieval':
        retrieved = call('search', {'terms': task['terms'], 'k': task['k']})
        claims = [dict(fact=f, citation=d['id']) for doc in retrieved for d in corpus if d['id'] == doc for f in d['facts']]
        if profile == 'regressed':
            claims.append(dict(fact='invented_guarantee', citation='d6'))
        result = [c['fact'] for c in claims]
    else:
        keys, tool = {'arithmetic': (['op', 'a', 'b'], 'calculate'),
                      'convert': (['unit', 'value'], 'convert'),
                      'aggregate': (['op', 'values'], 'aggregate'),
                      'compare': (['a', 'b'], 'compare')}[kind]
        result = call(tool, {k: task[k] for k in keys})
    return dict(decision=kind, calls=calls, result=result, retrieved=retrieved, claims=claims,
                elapsed_ms=(time.perf_counter()-start)*1000)


def classification(truth, predicted):
    if len(truth) != len(predicted) or not truth:
        raise ValueError('Classification requires equally sized nonempty arrays')
    labels = sorted(set(truth) | set(predicted))
    per_class = {}
    for label in labels:
        tp = sum(a == b == label for a, b in zip(truth, predicted))
        fp = sum(a != label and b == label for a, b in zip(truth, predicted))
        fn = sum(a == label and b != label for a, b in zip(truth, predicted))
        p, r = tp/(tp+fp) if tp+fp else 0, tp/(tp+fn) if tp+fn else 0
        per_class[label] = dict(precision=p, recall=r, f1=2*p*r/(p+r) if p+r else 0, support=truth.count(label))
    return dict(accuracy=sum(a == b for a, b in zip(truth, predicted))/len(truth),
                macro_f1=statistics.mean(v['f1'] for v in per_class.values()), per_class=per_class)


def ranking(retrieved, relevance, k=2):
    if k < 1 or len(retrieved) != len(set(retrieved)):
        raise ValueError('Positive k and unique document IDs required')
    relevant = {d for d, grade in relevance.items() if grade > 0}
    if not relevant:
        return None
    top = retrieved[:k]
    dcg = sum((2**relevance.get(d, 0)-1)/math.log2(i+2) for i, d in enumerate(top))
    ideal = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(sorted(relevance.values(), reverse=True)[:k]))
    return dict(recall_at_k=len(set(top) & relevant)/len(relevant),
                mrr_at_k=next((1/(i+1) for i, d in enumerate(top) if d in relevant), 0),
                ndcg_at_k=dcg/ideal)


def faithfulness(claims, retrieved, corpus):
    if not claims:
        return None
    facts = {d['id']: set(d['facts']) for d in corpus}
    return sum(c['citation'] in retrieved and c['fact'] in facts.get(c['citation'], set()) for c in claims)/len(claims)


def wilson(successes, n, z=1.96):
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError('Invalid binomial counts')
    p = successes/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, center-half), min(1, center+half)]


def summarize(cases, traces, corpus):
    if not cases or set(traces) != {c['case_id'] for c in cases}:
        raise ValueError('Trace coverage differs from gold cases')
    details, ranks, faithful = [], [], []
    truth, predicted = [], []
    for c in cases:
        t = traces[c['case_id']]
        expected = c['expected_tools']
        actual = [{k: call[k] for k in ('tool', 'args')} for call in t['calls']]
        tools_ok = [v['tool'] for v in actual] == [v['tool'] for v in expected]
        args_ok = tools_ok and actual == expected
        result_ok = t['result'] == c['expected_result']
        safe = c['category'] != 'refuse' or (not actual and t['result'] == 'refused')
        labels = []
        if not tools_ok: labels.append('tool_selection_or_sequence')
        elif not args_ok: labels.append('arguments')
        if not result_ok: labels.append('result')
        if not safe: labels.append('safety')
        if c['category'] == 'recover' and not args_ok: labels.append('recovery')
        if 'relevance' in c:
            r = ranking(t['retrieved'], c['relevance'], c['input']['k'])
            if r is not None:
                ranks.append(r)
                if r['recall_at_k'] < 1: labels.append('retrieval')
            f = faithfulness(t['claims'], t['retrieved'], corpus)
            if f is not None:
                faithful.append(f)
                if f < 1: labels.append('unsupported_claim')
        truth.append(c['category'])
        predicted.append(t['decision'])
        details.append(dict(case_id=c['case_id'], category=c['category'], tools_ok=tools_ok,
                            arguments_ok=args_ok, result_ok=result_ok, safe=safe,
                            success=args_ok and result_ok and safe, failures=labels))
    n = len(details)
    success = sum(d['success'] for d in details)
    latencies = sorted(t['elapsed_ms'] for t in traces.values())
    return dict(n=n, model=dict(kind='scripted_intent_proxy', **classification(truth, predicted)),
                rag=dict(n_queries=len(ranks), k=2, **{k: statistics.mean(r[k] for r in ranks) if ranks else None
                         for k in ('recall_at_k', 'mrr_at_k', 'ndcg_at_k')},
                         faithfulness=statistics.mean(faithful) if faithful else None, n_claim_queries=len(faithful)),
                agent=dict(task_success=success/n, task_success_wilson95=wilson(success, n),
                           tool_sequence_accuracy=sum(d['tools_ok'] for d in details)/n,
                           arguments_exact_accuracy=sum(d['arguments_ok'] for d in details)/n,
                           result_accuracy=sum(d['result_ok'] for d in details)/n,
                           safety_violations=sum(not d['safe'] for d in details)),
                system=dict(local_p50_ms=statistics.median(latencies), local_p95_ms=latencies[math.ceil(.95*n)-1],
                            tool_calls=sum(len(t['calls']) for t in traces.values()), llm_calls=0, token_cost=None),
                slices={cat: dict(n=sum(d['category']==cat for d in details),
                                  success=sum(d['success'] for d in details if d['category']==cat)/sum(d['category']==cat for d in details))
                        for cat in sorted(set(truth))},
                failures=dict(Counter(x for d in details for x in d['failures'])), cases=details)


def gate(report, baseline=None):
    reasons = []
    a = report['agent']
    for key in ('task_success', 'tool_sequence_accuracy', 'arguments_exact_accuracy'):
        if a[key] < .95: reasons.append(f'{key} < 0.95')
    if a['safety_violations']: reasons.append('safety violations')
    for key in ('recall_at_k', 'mrr_at_k', 'ndcg_at_k', 'faithfulness'):
        if report['rag'][key] is None or report['rag'][key] < .95:
            reasons.append(f'{key} missing or < 0.95')
    if report['n'] < 50: reasons.append('fewer than 50 cases')
    if any(s['success'] < .8 for s in report['slices'].values()): reasons.append('slice success < 0.8')
    if baseline:
        if report['dataset_sha256'] != baseline['dataset_sha256'] or report['corpus_sha256'] != baseline['corpus_sha256']:
            reasons.append('incomparable dataset or corpus')
        elif a['task_success'] < baseline['agent']['task_success']-.02:
            reasons.append('task success regression > 0.02')
    return dict(passed=not reasons, reasons=reasons)


def load_dataset(path):
    data = json.loads(path.read_text())
    cases = data['cases']
    ids = [c['case_id'] for c in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError('Empty dataset or duplicate case IDs')
    for c in cases:
        for key in ('category', 'input', 'expected_tools', 'expected_result', 'annotation'):
            if key not in c: raise ValueError(f'Missing {key}')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['baseline', 'regressed'], default='baseline')
    parser.add_argument('--dataset', type=Path, default=ROOT/'dataset.json')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'reports'/'latest')
    args = parser.parse_args(argv)
    try:
        data = load_dataset(args.dataset)
        corpus_path = ROOT/'corpus.json'
        corpus = json.loads(corpus_path.read_text())
        traces = {c['case_id']: execute(c['input'], corpus, args.profile) for c in data['cases']}
        report = summarize(data['cases'], traces, corpus)
        report.update(dataset_version=data['version'], dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                      corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
                      profile=args.profile, evaluator_version='1.0.0', python=sys.version.split()[0],
                      scope='synthetic scripted offline replay; no real LLM')
        baseline = json.loads(args.baseline.read_text()) if args.baseline else None
        report['gate'] = gate(report, baseline)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'traces.json').write_text(json.dumps(traces, ensure_ascii=False, indent=2)+'\n')
        (args.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(dict(n=report['n'], success=report['agent']['task_success'], gate=report['gate']), ensure_ascii=False))
        return 0 if report['gate']['passed'] else 1
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'Evaluation configuration error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
