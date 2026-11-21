"""Opt-in verification of constrained outputs and real model branch decisions."""
import argparse
import json
from pathlib import Path
from collect_model import sha
from http_model import Backend, check_generated
from constrained_model import ConstrainedBackend, decode_native, validate_enum


def verify(model_path, evidence):
    report = json.loads((evidence / 'report.json').read_text())
    assert sha(evidence / 'responses.jsonl') == report['responses_sha256']
    for name, expected in report['source_sha256'].items():
        assert sha(Path(__file__).parent / name) == expected, name
    base = json.loads((evidence / report['environment_and_model_hash_reference']).read_text())
    for name, expected in base['model_file_sha256'].items():
        assert sha(model_path / name) == expected, name
    rows = [json.loads(line) for line in (evidence / 'responses.jsonl').read_text().splitlines()]
    assert len(rows) == 18
    original = Backend(model_path)
    for punctuation in ['{', '}']:
        assert original.tokenizer.unk_token_id in original.tokenizer.encode(punctuation, add_special_tokens=False)
    free_rows = [json.loads(line) for line in (evidence.parent / 'local-model-20261120' / 'responses.jsonl').read_text().splitlines()]
    for row in rows[:9]:
        matched = [free for free in free_rows if free['case'] == 'record' and free['repeat'] == 0
                   and free['request'] == row['request']]
        assert len(matched) == 1
    backend = ConstrainedBackend(original)
    assert backend.paths == report['candidate_token_paths']
    for row in rows:
        response = row['response']
        assert original.tokenizer(row['request']['prompt'])['input_ids'] == response['input_ids']
        native = original.tokenizer.decode(response['generated_ids'][:-1], skip_special_tokens=False)
        assert native == response['raw_native_text']
        assert decode_native(native) == response['text']
        assert validate_enum(response['text']) == row['enum_validation']
        assert check_generated(response['text'], 'record') == row['record_validation']
        assert row['enum_validation']['valid']
        assert row['response']['branches']
        for branch in row['response']['branches']:
            assert len(branch['allowed_ids']) >= 2
            assert branch['chosen_id'] in branch['allowed_ids']
            assert abs(sum(branch['probabilities_after_mask_and_temperature']) - 1) < 1e-5
    for row in (rows[0], rows[9]):
        fresh = backend.generate(row['request'])
        assert fresh['generated_ids'] == row['response']['generated_ids']
    print('PASS: hashes; 18 schema/codec/token/branch checks; 2 fresh constrained model generations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    verify(args.model_path, args.evidence)
