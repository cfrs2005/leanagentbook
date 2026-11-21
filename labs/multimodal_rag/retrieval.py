"""Offline ranking, development-only threshold fitting, and evidence checks."""
import hashlib
import json
import math
import re
from pathlib import Path

MODES = ('visual', 'text', 'fusion')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lexical(query, title):
    a, b = set(re.findall(r'[a-z]+', query.lower())), set(re.findall(r'[a-z]+', title.lower()))
    return len(a & b) / len(a | b) if a | b else 0.0


def validate_queries(queries, items):
    ids = {item['id'] for item in items}
    if len(ids) != len(items):
        raise ValueError('Duplicate document IDs')
    seen_ids, seen_text = set(), set()
    for q in queries:
        if not q['text'].strip() or q['id'] in seen_ids or q['text'].lower().strip() in seen_text:
            raise ValueError('Empty or duplicate query; possible split leakage')
        if q['split'] not in ('dev', 'test') or not set(q['relevant']) <= ids:
            raise ValueError('Invalid split or relevance label')
        if q['kind'] not in ('known', 'unknown') or bool(q['relevant']) != (q['kind'] == 'known'):
            raise ValueError('Unknown queries must have no relevant document')
        seen_ids.add(q['id'])
        seen_text.add(q['text'].lower().strip())
    for split in ('dev', 'test'):
        if {q['kind'] for q in queries if q['split'] == split} != {'known', 'unknown'}:
            raise ValueError('Each split needs known and unknown queries')


def verify_evidence(item, data_dir):
    root = Path(data_dir).resolve()
    for name in ('source', 'image'):
        path = (root / item[name]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Missing or escaped evidence path')
        if sha256(path) != item[f'{name}_sha256']:
            raise ValueError('Evidence checksum mismatch')
    x0, y0, x1, y1 = item['bbox_xyxy']
    if item['page'] != 1 or not (0 <= x0 < x1 <= item['width'] and 0 <= y0 < y1 <= item['height']):
        raise ValueError('Invalid synthetic page or evidence region')
    return {'source': item['source'], 'image': item['image'], 'page': item['page'],
            'bbox_xyxy': item['bbox_xyxy'], 'image_sha256': item['image_sha256']}


def rank(row, items, mode, params, tenant='course', collection='synthetic_shapes_v1'):
    if mode not in MODES:
        raise ValueError('Unknown retrieval mode')
    if len(row['visual']) != len(items) or len(row['text']) != len(items):
        raise ValueError('Score length mismatch')
    if not all(math.isfinite(x) for channel in ('visual', 'text') for x in row[channel]):
        raise ValueError('Nonfinite score')
    candidates = []
    for i, item in enumerate(items):
        if item['tenant'] != tenant or item['collection'] != collection:
            continue
        visual, text = row['visual'][i], row['text'][i]
        if mode == 'visual':
            score = visual
        elif mode == 'text':
            score = text
        else:
            low, high = params['visual_range']
            scaled = min(1.0, max(0.0, (visual - low) / (high - low)))
            score = params['alpha'] * scaled + (1 - params['alpha']) * text
        candidates.append({'id': item['id'], 'score': score})
    return sorted(candidates, key=lambda hit: (-hit['score'], hit['id']))


def measure(rows, queries, items, mode, params, threshold):
    counts = {'known': 0, 'unknown': 0, 'known_top1_correct': 0, 'known_hit3': 0,
              'known_accepted': 0, 'known_accepted_correct': 0, 'known_accepted_wrong': 0,
              'unknown_rejected': 0, 'unknown_accepted': 0}
    decisions = []
    for query in queries:
        ranking = rank(rows[query['id']], items, mode, params)
        accepted = bool(ranking) and ranking[0]['score'] >= threshold
        top_id = ranking[0]['id'] if ranking else None
        known = bool(query['relevant'])
        correct = top_id in query['relevant']
        counts['known' if known else 'unknown'] += 1
        if known:
            counts['known_top1_correct'] += correct
            counts['known_hit3'] += bool(set(query['relevant']) & {h['id'] for h in ranking[:3]})
            counts['known_accepted'] += accepted
            counts['known_accepted_correct'] += accepted and correct
            counts['known_accepted_wrong'] += accepted and not correct
        else:
            counts['unknown_rejected'] += not accepted
            counts['unknown_accepted'] += accepted
        decisions.append({'query_id': query['id'], 'accepted': accepted,
                          'top_id': top_id, 'top_score': ranking[0]['score'] if ranking else None,
                          'correct': correct, 'top3': ranking[:3]})
    k, u = counts['known'], counts['unknown']
    accepted = counts['known_accepted'] + counts['unknown_accepted']
    counts.update({'recall_at_1': counts['known_top1_correct'] / k if k else None,
                   'recall_at_3': counts['known_hit3'] / k if k else None,
                   'known_correct_accept_rate': counts['known_accepted_correct'] / k if k else None,
                   'unknown_reject_rate': counts['unknown_rejected'] / u if u else None,
                   'accepted_precision': counts['known_accepted_correct'] / accepted if accepted else None})
    return counts, decisions


def fit(rows, queries, items, mode):
    if not queries or any(q['split'] != 'dev' for q in queries):
        raise ValueError('Threshold fitting accepts development queries only')
    values = [v for q in queries for v in rows[q['id']]['visual']]
    low, high = min(values), max(values)
    if not math.isfinite(low + high) or high <= low:
        raise ValueError('Invalid development score range')
    best = None
    for alpha in ([0.25, 0.5, 0.75] if mode == 'fusion' else [None]):
        params = {'alpha': alpha, 'visual_range': [low, high]}
        tops = sorted({rank(rows[q['id']], items, mode, params)[0]['score'] for q in queries})
        for threshold in tops + [math.nextafter(max(tops), math.inf)]:
            metrics, _ = measure(rows, queries, items, mode, params, threshold)
            objective = (metrics['known_correct_accept_rate'] + metrics['unknown_reject_rate']) / 2
            key = (objective, -metrics['unknown_accepted'], -metrics['known_accepted_wrong'], threshold)
            if best is None or key > best[0]:
                best = key, {**params, 'threshold': threshold, 'dev_objective': objective,
                             'dev_metrics': metrics}
    return best[1]


def evaluate(raw):
    items, queries, rows = raw['items'], raw['queries'], raw['scores']
    validate_queries(queries, items)
    dev = [q for q in queries if q['split'] == 'dev']
    test = [q for q in queries if q['split'] == 'test']
    result = {}
    for mode in MODES:
        params = fit(rows, dev, items, mode)
        metrics, decisions = measure(rows, test, items, mode, params, params['threshold'])
        result[mode] = {'fit': params, 'test_metrics': metrics, 'test_decisions': decisions}
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.raw.read_text()))
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
