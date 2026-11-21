"""Optional offline Transformers provider. Importing this module needs no torch."""
from copy import deepcopy
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent


class LocalModelProvider:
    def __init__(self, hub, max_output=32, fail_once=None):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.models = json.loads((ROOT / 'models.json').read_text())
        if type(max_output) is not int or not 1 <= max_output <= 64:
            raise ValueError('Invalid maximum output')
        if fail_once is not None and fail_once not in self.models:
            raise ValueError('Unknown failure target')
        self.unit, self.max_output = 'model_tokens', max_output
        self.fail_once = fail_once
        self.calls, self.load_ms, self.backends = [], {}, {}
        self.torch = torch
        torch.set_num_threads(2)
        for name, config in self.models.items():
            snapshot = Path(hub) / ('models--' + config['model'].replace('/', '--')) / 'snapshots' / config['revision']
            if not snapshot.is_dir():
                raise FileNotFoundError(f'Missing pinned local snapshot: {name}')
            started = time.perf_counter()
            tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(snapshot, local_files_only=True,
                                                        use_safetensors=True).float().cpu().eval()
            self.backends[name] = (tokenizer, model)
            self.load_ms[name] = (time.perf_counter() - started) * 1000

    def _inputs(self, name, prompt):
        tokenizer, _ = self.backends[name]
        inputs = tokenizer(prompt, return_tensors='pt', truncation=False)
        if inputs['input_ids'].shape[1] > 512:
            raise ValueError('Prompt exceeds 512 tokens')
        return inputs

    def estimate(self, model, prompt):
        return self._inputs(model, prompt)['input_ids'].shape[1] + self.max_output

    def call(self, model, prompt):
        started = time.perf_counter()
        inputs = self._inputs(model, prompt)
        row = {'model': model, 'revision': self.models[model]['revision'], 'prompt': prompt,
               'answer': '', 'input_units': 0, 'output_units': 0, 'status': 'error',
               'fault_injected': False, 'usage_known': True}
        if self.fail_once == model:
            self.fail_once = None
            row.update(fault_injected=True, error='injected_before_generation')
        else:
            tokenizer, backend = self.backends[model]
            # Unhandled runtime failures stop the experiment rather than invent token usage.
            with self.torch.inference_mode():
                output = backend.generate(**inputs, max_new_tokens=self.max_output, do_sample=False)
            row.update(answer=tokenizer.decode(output[0], skip_special_tokens=True),
                       input_units=int(inputs['input_ids'].shape[1]),
                       output_units=int(len(output[0]) - 1), status='ok')
        row['latency_ms'] = (time.perf_counter() - started) * 1000
        self.calls.append(deepcopy(row))
        return row
