"""Bounded closed-loop load test. Own and terminate the child server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import selectors
import subprocess
import sys
import threading
import time
import urllib.request


def request(port, input_n, output_n):
    start = time.perf_counter()
    events = []
    try:
        req = urllib.request.Request(f'http://127.0.0.1:{port}/generate',
            data=json.dumps({'input_tokens': input_n, 'output_tokens': output_n}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
                event = json.loads(line)
                event['client_elapsed_s'] = time.perf_counter() - start
                events.append(event)
        done = [e for e in events if e['type'] == 'done']
        tokens = [e for e in events if e['type'] == 'token']
        error = None if len(done) == 1 and len(tokens) == output_n else 'incomplete stream'
    except Exception as exc:
        error = type(exc).__name__
    return {'events': events, 'error': error, 'duration_s': time.perf_counter() - start,
            'requested_input_tokens': input_n, 'requested_output_tokens': output_n}


def system_value(name):
    try:
        return subprocess.check_output(['sysctl', '-n', name], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', default='labs/inference_serving/output')
    parser.add_argument('--requests', type=int, default=12)
    args = parser.parse_args()
    if args.requests < 2:
        parser.error('--requests must be at least 2')
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=False)
    model_path = Path(args.model).resolve()
    expected = '0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab'
    if Path(args.model).name != expected:
        parser.error('model must be the pinned snapshot directory')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in model_path.iterdir() if p.is_file() and p.suffix in ('.json', '.model', '.safetensors', '.bin')}
    child = None
    with (target / 'server.stderr.txt').open('w') as err:
        try:
            env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
            child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('server.py')),
                                      '--model', args.model], stdout=subprocess.PIPE, stderr=err,
                                     text=True, env=env)
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=120):
                    raise TimeoutError('server startup timeout')
                ready = json.loads(child.stdout.readline())
            metadata = {'started_utc': datetime.now(timezone.utc).isoformat(),
                        'python': platform.python_version(), 'os': platform.platform(),
                        'machine': platform.machine(), 'cpu': system_value('machdep.cpu.brand_string'),
                        'logical_cpus': os.cpu_count(), 'host_ram_bytes': system_value('hw.memsize'),
                        'model': 'google/flan-t5-small', 'model_file_sha256': hashes,
                        'server': ready, 'gpu_memory': None, 'gpu_memory_reason': 'CPU only; not applicable',
                        'quantization': 'none; FP32', 'shared_host_load': True,
                        'seed': 7, 'requests_per_cell': args.requests, 'warmups': 1,
                        'input_policy': 'fixed repeated synthetic English sentence, token-prefix slice plus EOS',
                        'output_policy': 'greedy; min_new_tokens=max_new_tokens; EOS suppressed to fixed length',
                        'clock': 'perf_counter; client origin before HTTP connection; server origin after body validation',
                        'memory_policy': 'server process lifetime peak RSS; includes loading and warmup; not cell allocation'}
            warmup = request(ready['port'], 32, 8)
            (target / 'warmup.json').write_text(json.dumps(warmup, indent=2) + '\n')
            if warmup['error']:
                raise RuntimeError('warmup failed')
            cells = list(itertools.product((1, 2), (32, 128), (8, 24)))
            random.Random(7).shuffle(cells)
            metadata['cell_order'] = cells
            (target / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
            with (target / 'requests.jsonl').open('w') as raw, (target / 'cells.jsonl').open('w') as cellfile:
                for cell_id, (concurrency, input_n, output_n) in enumerate(cells):
                    barrier = threading.Barrier(concurrency)
                    guard = threading.Lock()
                    state = {'active': 0, 'peak': 0}
                    start = time.perf_counter()
                    def worker(worker_id):
                        barrier.wait(timeout=30)
                        rows = []
                        for index in range(worker_id, args.requests, concurrency):
                            with guard:
                                state['active'] += 1
                                state['peak'] = max(state['peak'], state['active'])
                            dispatched = time.perf_counter() - start
                            row = request(ready['port'], input_n, output_n)
                            with guard:
                                state['active'] -= 1
                            row.update(cell_id=cell_id, request_id=index, start_offset_s=dispatched,
                                       concurrency=concurrency, worker_id=worker_id)
                            rows.append(row)
                        return rows
                    with ThreadPoolExecutor(max_workers=concurrency) as executor:
                        rows = list(itertools.chain.from_iterable(executor.map(worker, range(concurrency))))
                    elapsed = time.perf_counter() - start
                    for row in sorted(rows, key=lambda r: r['request_id']):
                        raw.write(json.dumps(row) + '\n')
                    raw.flush()
                    cell = {'cell_id': cell_id, 'concurrency': concurrency,
                            'actual_peak_http_concurrency': state['peak'], 'generation_concurrency': 1,
                            'input_tokens': input_n, 'output_tokens': output_n,
                            'requests': args.requests, 'wall_s': elapsed}
                    cellfile.write(json.dumps(cell) + '\n')
                    cellfile.flush()
                    print(json.dumps(cell), flush=True)
        finally:
            if child is not None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
                (target / 'shutdown.json').write_text(json.dumps({'child_exited': child.poll() is not None,
                                                               'returncode': child.returncode}) + '\n')
    # Error streams should not publish host-specific paths.
    log = target / 'server.stderr.txt'
    log.write_text(log.read_text().replace(str(Path.home()), '$HOME').replace(str(model_path), '$MODEL'))


if __name__ == '__main__':
    main()
