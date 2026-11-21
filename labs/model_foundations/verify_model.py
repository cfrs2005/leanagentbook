"""Opt-in real tokenizer and inference replay; not discovered by default tests."""
import argparse
import hashlib
import json
from pathlib import Path
from http_model import Backend, check_generated


def verify(model_path, evidence):
    report = json.loads((evidence / 'report.json').read_text())
    assert hashlib.sha256((evidence / 'responses.jsonl').read_bytes()).hexdigest() == report['responses_sha256']
    for name, expected in report['source_sha256'].items():
        assert hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() == expected, name
    for name, expected in report['model_file_sha256'].items():
        assert hashlib.sha256((model_path / name).read_bytes()).hexdigest() == expected, name
    rows = [json.loads(line) for line in (evidence / 'responses.jsonl').read_text().splitlines()]
    assert len(rows) == 36
    backend = Backend(model_path)
    for row in rows:
        response = row['response']
        assert backend.tokenizer(row['request']['prompt'])['input_ids'] == response['input_ids']
        assert backend.tokenizer.decode([response['decoder_start_id'], *response['generated_ids']], skip_special_tokens=True) == response['text']
        assert len(response['input_ids']) == response['input_tokens']
        assert len(response['generated_ids']) == response['output_tokens']
        assert check_generated(response['text'], row['schema_name']) == row['schema_validation']
    for row in (rows[0], rows[18]):
        generated = backend.generate(row['request'])
        assert generated['generated_ids'] == row['response']['generated_ids']
    print('PASS: source/model/data hashes; all 36 tokenizer, decoder and schema checks; 2 fresh generation replays')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    verify(args.model_path, args.evidence)
