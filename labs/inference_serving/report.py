"""Standard-library replay of request-level token events."""
import argparse
import json
import math
from pathlib import Path
import statistics


def quantile(values, q):
    if not values:
        return None
    if not 0 < q <= 1:
        raise ValueError('q must be in (0, 1]')
    return sorted(values)[max(0, math.ceil(q * len(values)) - 1)]


def metrics(row):
    tokens = [event for event in row['events'] if event['type'] == 'token']
    done = [event for event in row['events'] if event['type'] == 'done']
    if row['error'] or len(done) != 1 or not tokens:
        return None
    end = done[0]
    if end['output_tokens'] != len(tokens) or len(tokens) != row['requested_output_tokens']:
        raise ValueError('output token count mismatch')
    if end['input_tokens'] != row['requested_input_tokens']:
        raise ValueError('input token count mismatch')
    if [event['index'] for event in tokens] != list(range(1, len(tokens) + 1)):
        raise ValueError('token sequence mismatch')
    times = [event['client_elapsed_s'] for event in tokens]
    server_times = [event['server_elapsed_s'] for event in tokens]
    if times != sorted(times) or server_times != sorted(server_times):
        raise ValueError('nonmonotonic token timing')
    gaps = [b - a for a, b in zip(times, times[1:])]
    return {'ttft_s': times[0], 'tpot_s': statistics.mean(gaps) if gaps else None,
            'itls_s': gaps, 'e2e_s': row['duration_s'], 'queue_s': end['queue_s'],
            'output_tokens': len(tokens), 'input_tokens': end['input_tokens'],
            'peak_rss_bytes': end['process_peak_rss_bytes']}


def summarize(root):
    rows = [json.loads(line) for line in (root / 'requests.jsonl').read_text().splitlines()]
    cells = [json.loads(line) for line in (root / 'cells.jsonl').read_text().splitlines()]
    result = []
    for cell in cells:
        selected = [r for r in rows if r['cell_id'] == cell['cell_id']]
        if len(selected) != cell['requests']:
            raise ValueError('missing request rows')
        good = [m for r in selected if (m := metrics(r)) is not None]
        record = dict(cell, successes=len(good), errors=len(selected) - len(good))
        record['output_tokens_per_s'] = sum(m['output_tokens'] for m in good) / cell['wall_s']
        record['input_tokens_per_s'] = sum(m['input_tokens'] for m in good) / cell['wall_s']
        record['requests_per_s'] = len(good) / cell['wall_s']
        record['peak_rss_mib'] = max((m['peak_rss_bytes'] for m in good), default=0) / 2**20
        for field in ('ttft_s', 'tpot_s', 'e2e_s', 'queue_s'):
            values = [m[field] * 1000 for m in good if m[field] is not None]
            for label, q in [('p50', .5), ('p95', .95), ('p99', .99)]:
                record[field.replace('_s', '_ms') + '_' + label] = quantile(values, q)
            record[field + '_n'] = len(values)
        gaps = [v * 1000 for m in good for v in m['itls_s']]
        record['itl_n'] = len(gaps)
        record['itl_ms_p95'] = quantile(gaps, .95)
        result.append(record)
    return sorted(result, key=lambda c: (c['concurrency'], c['input_tokens'], c['output_tokens']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=str(Path(__file__).with_name('results')))
    parser.add_argument('--output', default='labs/inference_serving/output-report')
    args = parser.parse_args()
    result = summarize(Path(args.input))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    table = ['| 并发 | 输入/输出 token | 成功/错误 | 输出 token/s | TTFT P50/P95/P99 ms | TPOT P50 ms | 排队 P50 ms |',
             '|---|---|---|---|---|---|---|']
    for r in result:
        table.append(f"| {r['concurrency']} | {r['input_tokens']}/{r['output_tokens']} | {r['successes']}/{r['errors']} | "
                     f"{r['output_tokens_per_s']:.1f} | {r['ttft_ms_p50']:.1f}/{r['ttft_ms_p95']:.1f}/{r['ttft_ms_p99']:.1f} | "
                     f"{r['tpot_ms_p50']:.1f} | {r['queue_ms_p50']:.1f} |")
    (out / 'summary.md').write_text('\n'.join(table) + '\n')
    print('\n'.join(table))


if __name__ == '__main__':
    main()
