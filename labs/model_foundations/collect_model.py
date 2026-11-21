"""Real-model HTTP experiment. Optional dependencies are loaded only on execution."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import threading
import time
import urllib.request
from http_model import Backend, SCHEMAS, check_generated, make_server

REVISION = '0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab'
CASES = [
    {'id': 'integer', 'schema': 'integer', 'expected': 5,
     'prompt': 'What is 2 plus 3? Return only a JSON integer, without explanation.'},
    {'id': 'record', 'schema': 'record',
     'prompt': 'Source record-1: The device temperature is 42 degrees Celsius. Return only JSON with exactly these fields: "answer" (string) and "source_ids" (array of strings). Include the temperature and source ID.'},
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(model_path, output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    backend = Backend(model_path)
    load_seconds = time.perf_counter() - started
    server = make_server(backend)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = 'http://127.0.0.1:' + str(server.server_port) + '/generate'
    rows = []
    try:
        with (output / 'responses.jsonl').open('x') as stream:
            for case in CASES:
                for temperature in [0.2, 0.8, 1.3]:
                    for seed in [7, 17, 27]:
                        for repeat in [0, 1]:
                            request = {'prompt': case['prompt'], 'temperature': temperature,
                                       'seed': seed, 'max_new_tokens': 64}
                            start = time.perf_counter()
                            http_request = urllib.request.Request(endpoint, json.dumps(request).encode(),
                                                                  {'Content-Type': 'application/json'})
                            with urllib.request.urlopen(http_request, timeout=120) as response:
                                payload = json.load(response)
                                status = response.status
                            validation = check_generated(payload['text'], case['schema'])
                            row = {'case': case['id'], 'schema_name': case['schema'], 'request': request,
                                   'repeat': repeat, 'http_status': status, 'response': payload,
                                   'schema_validation': validation,
                                   'fact_correct': validation['value'] == case['expected'] if case['id'] == 'integer' and validation['valid'] else None,
                                   'http_roundtrip_seconds': time.perf_counter() - start}
                            rows.append(row)
                            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                            stream.flush()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    groups = []
    for case in CASES:
        for temperature in [0.2, 0.8, 1.3]:
            group = [r for r in rows if r['case'] == case['id'] and r['request']['temperature'] == temperature]
            groups.append({'case': case['id'], 'temperature': temperature, 'requests': len(group),
                           'schema_valid': sum(r['schema_validation']['valid'] for r in group),
                           'unique_outputs': len({r['response']['text'] for r in group}),
                           'fact_correct': sum(r['fact_correct'] is True for r in group) if case['id'] == 'integer' else None,
                           'same_seed_repeats_identical': all(group[i]['response']['generated_ids'] == group[i+1]['response']['generated_ids'] for i in range(0, len(group), 2))})
    report = {'model': 'google/flan-t5-small', 'revision': REVISION,
              'source_access_date': '2026-11-20', 'transport': 'real loopback HTTP POST /generate; not a cloud API',
              'input_data': 'Original synthetic English prompts; two fixed cases, all outputs retained',
              'generation': {'do_sample': True, 'top_p': 1.0, 'top_k': 0, 'max_new_tokens': 64, 'temperatures': [0.2, 0.8, 1.3], 'seeds': [7,17,27], 'repeats': 2},
              'token_counting': 'Encoder input includes special tokens; output excludes decoder start and includes generated EOS; not a cloud billing count',
              'model_load_seconds': load_seconds, 'environment': {'python': platform.python_version(),
                 'system': platform.system(), 'machine': platform.machine(), 'device': 'cpu', 'torch_threads': 2,
                 'packages': {name: importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','sentencepiece','safetensors','numpy']}},
              'schemas': SCHEMAS, 'cases': CASES, 'groups': groups,
              'source_sha256': {name: sha(Path(__file__).parent / name) for name in ['collect_model.py','http_model.py','foundations.py']},
              'model_file_sha256': {p.name: sha(p) for p in sorted(model_path.iterdir()) if p.is_file()},
              'responses_sha256': sha(output / 'responses.jsonl')}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(groups, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    collect(args.model_path, args.out)
