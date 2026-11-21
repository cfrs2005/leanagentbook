"""Optional pinned local language model; proposals never become control decisions."""
from pathlib import Path
import time

REVISION = '0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab'


class LocalDraftModel:
    def __init__(self, model_path):
        if Path(model_path).name != REVISION:
            raise ValueError('Use the pinned FLAN-T5-small snapshot directory')
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        torch.set_num_threads(1)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True, use_safetensors=True).eval()

    def __call__(self, status, references):
        # The generator sees only synthetic status and fixed evidence identifiers.
        prompt = ('Write one short maintenance review suggestion. Do not claim a confirmed cause. '
                  f'Synthetic observed status: {status}. Evidence identifiers: '
                  + ', '.join(row['id'] for row in references) + '. A human must review the evidence.')
        start = time.perf_counter()
        tokens = self.tokenizer(prompt, return_tensors='pt', truncation=False)
        if tokens['input_ids'].shape[1] > 256:
            raise ValueError('Draft input budget exhausted')
        with self.torch.inference_mode():
            output = self.model.generate(**tokens, max_new_tokens=32, do_sample=False)
        return {'mode': 'real_local_flan_t5_draft', 'model': 'google/flan-t5-small', 'revision': REVISION,
                'text': self.tokenizer.decode(output[0], skip_special_tokens=True), 'verified': False,
                'input_tokens': tokens['input_ids'].shape[1], 'output_tokens': len(output[0]) - 1,
                'generation_seconds': time.perf_counter() - start,
                'policy': 'Unverified draft only; cannot change evidence, status, approval or control'}
