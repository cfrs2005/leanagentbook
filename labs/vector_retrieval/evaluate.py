"""Evaluate fixed retrieval pipelines without giving judgments to rankers."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path
from retrieval import BM25, dot, metrics, ranked, rrf, teaching_rerank, teaching_vector, weighted_fusion

ROOT = Path(__file__).resolve().parent
EMBEDDER = ('sentence-transformers/all-MiniLM-L6-v2', '1110a243fdf4706b3f48f1d95db1a4f5529b4d41')
RERANKER = ('cross-encoder/ms-marco-TinyBERT-L2-v2', '81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc')


def run(mode, repeats, candidates, cutoff):
    docs = {row['id']: row['text'] for row in json.loads((ROOT / 'corpus.json').read_text())}
    queries = json.loads((ROOT / 'judgments.json').read_text())
    if not 1 <= cutoff <= candidates <= len(docs) or repeats < 1:
        raise ValueError('Require 1 <= cutoff <= candidates <= corpus size and repeats >= 1')
    ids = list(docs)
    start = time.perf_counter()
    versions = {}
    if mode == 'pretrained':
        from sentence_transformers import SentenceTransformer, CrossEncoder
        import torch
        torch.set_num_threads(2)
        encoder = SentenceTransformer(EMBEDDER[0], revision=EMBEDDER[1], device='cpu')
        reranker = CrossEncoder(RERANKER[0], revision=RERANKER[1], device='cpu', max_length=256)
        def encode(texts):
            return encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
        def rerank(query, selected):
            values = reranker.predict([(query, docs[key]) for key in selected], show_progress_bar=False)
            return ranked(dict(zip(selected, map(float, values))))
        versions = {name: importlib.metadata.version(name) for name in ('torch','transformers','sentence-transformers','numpy')}
    else:
        encode = lambda texts: [teaching_vector(text) for text in texts]
        rerank = lambda query, selected: teaching_rerank(query, selected, docs)
    load_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    bm25 = BM25(docs)
    vectors = dict(zip(ids, encode(list(docs.values()))))
    index_ms = (time.perf_counter() - start) * 1000
    def pipeline(query, method):
        if method == 'bm25':
            return ranked(bm25.scores(query))[:candidates]
        if method == 'dense':
            qv = encode([query])[0]
            return ranked({key: dot(qv, v) for key, v in vectors.items()})[:candidates]
        sparse = bm25.scores(query)
        qv = encode([query])[0]
        dense = {key: dot(qv, v) for key, v in vectors.items()}
        a, b = ranked(sparse)[:candidates], ranked(dense)[:candidates]
        if method == 'weighted':
            return weighted_fusion({key:sparse[key] for key in a}, {key:dense[key] for key in b})[:candidates]
        merged = rrf([a,b])[:candidates]
        return rerank(query, merged) if method == 'rerank' else merged
    methods = ['bm25','dense','rrf','weighted','rerank']
    # Warm each complete path once; warmup is excluded from timings.
    for method in methods:
        pipeline(queries[0]['text'], method)
    rows = []
    for query in queries:
        for method in methods:
            times = []
            for _ in range(repeats):
                start = time.perf_counter()
                order = pipeline(query['text'], method)
                times.append((time.perf_counter() - start) * 1000)
            rows.append({'query':query['id'],'split':query['split'],'category':query['category'],
                         'method':method,'order':order,'metrics':metrics(order,query['relevance'],cutoff),
                         'candidate_recall':metrics(order,query['relevance'],candidates)['recall'],
                         'latency_ms':times})
    summary = {}
    for split in ('dev','test'):
        summary[split] = {}
        for method in methods:
            selected = [row for row in rows if row['method']==method and row['split']==split]
            latencies = sorted(v for row in selected for v in row['latency_ms'])
            summary[split][method] = {key:statistics.mean(row['metrics'][key] for row in selected) for key in ('recall','mrr','ndcg')}
            summary[split][method].update(candidate_recall=statistics.mean(row['candidate_recall'] for row in selected),
                p50_ms=statistics.median(latencies),p95_ms=latencies[math.ceil(.95*len(latencies))-1],queries=len(selected))
    return {'mode':mode,'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),
            'cpu_count':os.cpu_count(),'versions':versions,'models':{'embedder':EMBEDDER,'reranker':RERANKER} if mode=='pretrained' else {},
            'corpus_sha256':hashlib.sha256((ROOT/'corpus.json').read_bytes()).hexdigest(),
            'judgments_sha256':hashlib.sha256((ROOT/'judgments.json').read_bytes()).hexdigest(),
            'config':{'repeats':repeats,'candidate_depth':candidates,'cutoff':cutoff,'rrf_constant':60,'weight':0.5,'device':'cpu','torch_threads':2 if mode=='pretrained' else None},
            'load_ms':load_ms,'index_ms':index_ms,'summary':summary,'rows':rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['offline','pretrained'],default='offline')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--candidates',type=int,default=10)
    parser.add_argument('--cutoff',type=int,default=5)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = run(args.mode,args.repeats,args.candidates,args.cutoff)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
