"""HTTP comparison with genuine model-selected finite object-enum outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import threading
import urllib.request
from collect_model import REVISION, sha
from http_model import Backend, make_server, check_generated
from constrained_model import ConstrainedBackend, ENUM_SCHEMA, OBJECTS, validate_enum


def collect(model_path, output):
    output.mkdir(parents=True, exist_ok=False)
    backend = Backend(model_path)
    constrained = ConstrainedBackend(backend)
    server = make_server(constrained)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = []
    try:
        with (output / 'responses.jsonl').open('x') as stream:
            for truth in ['42', '99']:
                prompt = f'Source record-1: The device temperature is {truth} degrees Celsius. Return only JSON with exactly these fields: "answer" (string) and "source_ids" (array of strings). Include the temperature and source ID.'
                for temperature in [0.2, 0.8, 1.3]:
                    for seed in [7, 17, 27]:
                        request = {'prompt': prompt, 'temperature': temperature, 'seed': seed, 'max_new_tokens': 64}
                        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/generate', json.dumps(request).encode(), {'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=120) as response:
                            payload = json.load(response)
                            status = response.status
                        validation = validate_enum(payload['text'])
                        row = {'request': request, 'expected_answer': truth, 'http_status': status, 'response': payload,
                               'enum_validation': validation, 'record_validation': check_generated(payload['text'], 'record'),
                               'fact_correct': validation['valid'] and validation['value']['answer'] == truth}
                        rows.append(row)
                        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                        stream.flush()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    report = {'model': 'google/flan-t5-small', 'revision': REVISION, 'source_access_date': '2026-11-20',
              'method': 'Real model.generate with prefix_allowed_tokens_fn; finite object enum; existing sentinel brace codec; unchanged tokenizer vocabulary and weights',
              'native_json_limitation': 'Original T5 tokenizer encodes ASCII braces as unk; native generation uses extra_id_0/1, explicit reversible codec emits JSON braces',
              'schema': ENUM_SCHEMA, 'candidates': OBJECTS, 'candidate_token_paths': constrained.paths,
              'requests': len(rows), 'schema_valid': sum(r['enum_validation']['valid'] for r in rows),
              'fact_correct': sum(r['fact_correct'] for r in rows), 'all_have_model_scored_branch': all(r['response']['branches'] for r in rows),
              'source_sha256': {name: sha(Path(__file__).parent / name) for name in ['collect_constrained.py','constrained_model.py','http_model.py','collect_model.py','foundations.py']},
              'responses_sha256': sha(output / 'responses.jsonl'),
              'environment_and_model_hash_reference': '../local-model-20261120/report.json'}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['requests','schema_valid','fact_correct','all_have_model_scored_branch']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    collect(args.model_path, args.out)
