"""Collect real CPU model observations; labels are never passed to generation."""
import argparse
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

ROOT = Path(__file__).resolve().parent


def main():
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    dataset = json.loads((ROOT / 'dataset.json').read_text())
    models = json.loads((ROOT / 'models.json').read_text())
    result = {'schema': 'routing-observations-v1', 'models': models,
              'dataset_sha256': hashlib.sha256((ROOT / 'dataset.json').read_bytes()).hexdigest(),
              'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                              'torch': importlib.metadata.version('torch'),
                              'transformers': importlib.metadata.version('transformers')},
              'measurement': 'One real generation per prompt/model after warmup; CPU two threads; no network in timed region',
              'unit': 'model_tokens', 'max_new_tokens': 32, 'observations': [], 'load_ms': {}}
    for name, config in models.items():
        print('Loading', name, flush=True)
        start = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(config['model'], revision=config['revision'])
        model = AutoModelForSeq2SeqLM.from_pretrained(config['model'], revision=config['revision'], use_safetensors=True).eval()
        result['load_ms'][name] = (time.perf_counter() - start) * 1000
        warm = tokenizer('Answer with one number: 1 + 1?', return_tensors='pt')
        with torch.inference_mode():
            model.generate(**warm, max_new_tokens=32, do_sample=False)
        for row in dataset:
            # Only prompt text reaches the tokenizer and model; gold is evaluated elsewhere.
            start = time.perf_counter()
            inputs = tokenizer(row['prompt'], return_tensors='pt', truncation=False)
            if inputs['input_ids'].shape[1] > 512:
                raise ValueError('Prompt exceeds experiment input limit')
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=32, do_sample=False)
            answer = tokenizer.decode(output[0], skip_special_tokens=True)
            elapsed = (time.perf_counter() - start) * 1000
            # Exclude decoder start; include emitted EOS, matching generated sequence accounting.
            result['observations'].append({'prompt': row['prompt'], 'model': name, 'answer': answer,
                'input_units': inputs['input_ids'].shape[1], 'output_units': len(output[0]) - 1,
                'latency_ms': elapsed, 'status': 'ok'})
            print(name, row['id'], answer, flush=True)
        del model, tokenizer
        gc.collect()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Saved', args.output, flush=True)


if __name__ == '__main__':
    main()
