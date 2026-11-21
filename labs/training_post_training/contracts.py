"""Dependency-free data and evaluation contracts."""
import json
from pathlib import Path

LABELS = ('billing', 'access', 'hardware')
PROMPT = 'Route this support request. Reply with exactly one label: billing, access, hardware. Request: '


def load_data(root=None):
    root = Path(root) if root else Path(__file__).parent / 'data'
    data = {s: [json.loads(line) for line in (root / f'{s}.jsonl').read_text().splitlines()]
            for s in ('train', 'dev', 'test')}
    seen = {k: set() for k in ('id', 'scenario', 'text')}
    for rows in data.values():
        if not rows:
            raise ValueError('Empty split')
        for row in rows:
            if row['label'] not in LABELS:
                raise ValueError('Unknown label')
            for key in seen:
                value = ' '.join(row[key].lower().split())
                if not value or value in seen[key]:
                    raise ValueError(f'Duplicate or empty {key}')
                seen[key].add(value)
    return data


def metrics(rows):
    if not rows:
        raise ValueError('Empty predictions')
    correct = sum(r['prediction'] == r['label'] for r in rows)
    confusion = {label: {p: 0 for p in (*LABELS, 'invalid')} for label in LABELS}
    for row in rows:
        p = row['prediction'] if row['prediction'] in LABELS else 'invalid'
        confusion[row['label']][p] += 1
    f1 = []
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label].values()) - tp
        f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return {'n': len(rows), 'correct': correct, 'accuracy': correct / len(rows),
            'macro_f1': sum(f1) / len(f1), 'confusion': confusion,
            'invalid': sum(c['invalid'] for c in confusion.values())}
