"""Evaluate fixed, human-authored synthetic relevance labels at document level."""
import argparse
import json
import math
from pathlib import Path
import platform
import sqlite3
import statistics
import tempfile
import time

from pipeline import Store

ROOT = Path(__file__).parent


def evaluate():
    labels = json.loads((ROOT / 'queries.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as temp:
        store = Store(Path(temp) / 'eval.sqlite')
        for doc_id, filename in [('battery', 'battery.md'), ('network', 'network.html'),
                                 ('maintenance', 'maintenance.md'), ('private', 'private.md')]:
            store.ingest(ROOT / 'fixtures' / filename, doc_id,
                         role='technician' if doc_id == 'private' else 'public')
        records, latencies, recalls, reciprocal, ndcgs, refusals = [], [], [], [], [], []
        for label in labels:
            start = time.perf_counter()
            hits = store.search(label['query'], label.get('principal', 'public'), k=3)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            ranked = list(dict.fromkeys(hit['doc_id'] for hit in hits))
            relevant = set(label['relevant'])
            if relevant:
                recalls.append(len(set(ranked) & relevant) / len(relevant))
                reciprocal.append(next((1 / rank for rank, doc in enumerate(ranked, 1)
                                        if doc in relevant), 0))
                dcg = sum(1 / math.log2(rank + 1) for rank, doc in enumerate(ranked, 1)
                          if doc in relevant)
                ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(3, len(relevant)) + 1))
                ndcgs.append(dcg / ideal)
            else:
                refusals.append(not ranked)
            records.append({**label, 'retrieved_documents': ranked, 'latency_ms': round(elapsed, 4)})
        store.close()
    return {'dataset': '12 hand-labeled synthetic queries; no held-out production set',
            'ranking_unit': 'top 3 distinct parents, then document deduplication',
            'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
            'answer_mode': 'extractive/scripted', 'positive_queries': len(recalls),
            'negative_queries': len(refusals), 'recall_at_3': statistics.mean(recalls),
            'mrr_at_3': statistics.mean(reciprocal), 'ndcg_at_3': statistics.mean(ndcgs),
            'empty_result_accuracy': statistics.mean(refusals),
            'latency_ms_median': round(statistics.median(latencies), 4),
            'latency_ms_p95_nearest_rank': round(sorted(latencies)[math.ceil(.95 * len(latencies)) - 1], 4),
            'queries': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rendered = json.dumps(evaluate(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
