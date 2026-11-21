"""Real CPU LoRA SFT. Published results are never overwritten by this script."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import resource
import time
from pathlib import Path

from contracts import PROMPT, load_data, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', help='Read-only snapshot matching the configured revision')
    parser.add_argument('--output', default='output/training_post_training')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = Path(args.output).resolve()
    if out == root / 'results' or root / 'results' in out.parents:
        raise ValueError('Published results are read-only; use output/ or /tmp')
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Use an empty output directory to preserve prior runs')
    started = time.perf_counter()
    import torch
    import psutil
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from peft import LoraConfig, TaskType, get_peft_model, PeftModel

    cfg = json.loads((root / 'config.json').read_text())
    random.seed(cfg['seed'])
    torch.manual_seed(cfg['seed'])
    torch.set_num_threads(cfg['cpu_threads'])
    torch.use_deterministic_algorithms(True)
    data = load_data()
    source = args.model_path or cfg['model_id']
    if args.model_path and Path(source).name != cfg['revision']:
        raise ValueError('Local snapshot directory must match the pinned revision')
    kwargs = {'local_files_only': True} if args.model_path else {'revision': cfg['revision']}
    tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
    base = AutoModelForSeq2SeqLM.from_pretrained(source, **kwargs).to('cpu')
    base.config.use_cache = False

    def batch(rows):
        inputs = tokenizer([PROMPT + r['text'] for r in rows], padding=True, return_tensors='pt')
        labels = tokenizer(text_target=[r['label'] for r in rows], padding=True, return_tensors='pt')['input_ids']
        if inputs['input_ids'].shape[1] > cfg['max_input_tokens']:
            raise ValueError('Input exceeds token budget; no silent truncation')
        labels[labels == tokenizer.pad_token_id] = -100
        return {**inputs, 'labels': labels}

    def loss(model, rows):
        model.eval()
        total, count = 0., 0
        with torch.no_grad():
            for i in range(0, len(rows), cfg['batch_size']):
                b = batch(rows[i:i+cfg['batch_size']])
                n = int((b['labels'] != -100).sum())
                total += float(model(**b).loss) * n
                count += n
        return total / count

    def evaluate(model, rows):
        model.eval()
        records = []
        with torch.no_grad():
            for row in rows:
                b = batch([row])
                pred = model.generate(input_ids=b['input_ids'], attention_mask=b['attention_mask'],
                                      max_new_tokens=cfg['max_output_tokens'], do_sample=False, num_beams=1)
                records.append({**row, 'prediction': tokenizer.decode(pred[0], skip_special_tokens=True).strip().lower()})
        return {'metrics': metrics(records), 'predictions': records, 'token_loss': loss(model, rows)}

    baseline = {s: evaluate(base, data[s]) for s in ('train', 'dev')}
    model = get_peft_model(base, LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM,
        r=cfg['rank'], lora_alpha=cfg['alpha'], lora_dropout=cfg['dropout'], target_modules=cfg['target_modules']))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    initial = {n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad}
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=cfg['learning_rate'])
    curve = [{'epoch': 0, 'train_loss': baseline['train']['token_loss'], 'dev_loss': baseline['dev']['token_loss']}]
    best, best_epoch = float('inf'), None
    train_start = time.perf_counter()
    step_log = []
    for epoch in range(1, cfg['epochs'] + 1):
        indices = list(range(len(data['train'])))
        random.shuffle(indices)
        model.train()
        for i in range(0, len(indices), cfg['batch_size']):
            rows = [data['train'][j] for j in indices[i:i+cfg['batch_size']]]
            optimizer.zero_grad(set_to_none=True)
            value = model(**batch(rows)).loss
            if not torch.isfinite(value):
                raise ValueError('Non-finite training loss')
            value.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            step_log.append({'step': len(step_log)+1, 'epoch': epoch, 'loss': float(value.detach()), 'gradient_norm': float(norm)})
        point = {'epoch': epoch, 'train_loss': loss(model, data['train']), 'dev_loss': loss(model, data['dev'])}
        curve.append(point)
        if point['dev_loss'] < best:
            best, best_epoch = point['dev_loss'], epoch
            model.save_pretrained(out / 'adapter', safe_serialization=True)
        print(json.dumps(point), flush=True)
    train_seconds = time.perf_counter() - train_start
    delta = sum(float((p.detach() - initial[n]).square().sum()) for n,p in model.named_parameters() if n in initial) ** 0.5
    if delta == 0:
        raise AssertionError('No adapter update')
    # Choose by dev loss only, then open the held-out test once for reporting.
    model.load_adapter(out / 'adapter', adapter_name='selected')
    model.set_adapter('selected')
    after = {s: evaluate(model, data[s]) for s in data}
    with model.disable_adapter():
        baseline['test'] = evaluate(model, data['test'])
    probe = batch(data['dev'])
    model.eval()
    with torch.no_grad():
        logits = model(**probe).logits.detach().clone()
    del optimizer, initial, base, model
    import gc
    gc.collect()
    fresh = AutoModelForSeq2SeqLM.from_pretrained(source, **kwargs).to('cpu')
    reloaded = PeftModel.from_pretrained(fresh, out / 'adapter').eval()
    with torch.no_grad():
        reload_logits = reloaded(**probe).logits
    max_diff = float((reload_logits-logits).abs().max())
    reload_eval = evaluate(reloaded, data['test'])
    same = reload_eval['predictions'] == after['test']['predictions']
    if max_diff > 1e-6 or not same:
        raise AssertionError(f'Adapter reload mismatch: {max_diff}, {same}')
    end_rss_bytes = psutil.Process().memory_info().rss
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if platform.system() == 'Darwin' else peak * 1024
    report = {
      'config': cfg, 'data_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'data').glob('*.jsonl'))},
      'environment': {'python': platform.python_version(), 'os': platform.system(), 'machine': platform.machine(),
                      'device': 'cpu', 'dtype': 'float32', 'versions': {p: importlib.metadata.version(p) for p in ('torch','transformers','peft','numpy','sentencepiece','psutil')}},
      'parameters': {'trainable': trainable, 'total_with_adapter': total_params, 'final_update_l2': delta},
      'selection': {'best_epoch': best_epoch, 'best_dev_loss': best, 'test_used_for_selection': False},
      'curve': curve, 'steps': step_log, 'baseline': baseline, 'after': after,
      'reload': {'max_abs_dev_logits_difference': max_diff, 'test_predictions_equal': same},
      'resources': {'training_and_epoch_validation_seconds': train_seconds, 'total_seconds': time.perf_counter()-started,
                    'process_peak_rss_bytes': peak_bytes, 'process_end_rss_bytes': end_rss_bytes,
                    'rss_method': 'getrusage RUSAGE_SELF high-water mark; includes loading, training, evaluation and reload',
                    'gpu_peak_memory_bytes': None, 'gpu_note': 'Not applicable: CPU-only run; unified RAM is not GPU VRAM'},
      'failures': {stage: [r for r in result['test']['predictions'] if r['prediction'] != r['label']]
                   for stage, result in [('baseline', baseline), ('after', after)]}}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'config.json').write_text(json.dumps(cfg, indent=2)+'\n')
    # Remove local paths from the saved adapter metadata, while preserving reloadability.
    adapter_cfg_path = out/'adapter'/'adapter_config.json'
    adapter_cfg = json.loads(adapter_cfg_path.read_text())
    adapter_cfg['base_model_name_or_path'] = cfg['model_id']
    adapter_cfg['revision'] = cfg['revision']
    adapter_cfg_path.write_text(json.dumps(adapter_cfg, indent=2)+'\n')
    print(json.dumps({'baseline_test': baseline['test']['metrics'], 'after_test': after['test']['metrics'], 'reload': report['reload'], 'resources': report['resources']}), flush=True)


if __name__ == '__main__':
    main()
