"""Finite object-enum decoding using existing T5 sentinels as a JSON brace codec."""
import json

OBJECTS = [{'answer': value, 'source_ids': ['record-1']} for value in ['42', '99']]
ENUM_SCHEMA = {'enum': OBJECTS}
CODEC = {'<extra_id_0>': '{', '<extra_id_1>': '}'}


def encode_object(value):
    if value not in OBJECTS:
        raise ValueError('Object outside the finite schema')
    return json.dumps(value, separators=(',', ':')).replace('{', '<extra_id_0>').replace('}', '<extra_id_1>')


def decode_native(text):
    for sentinel, punctuation in CODEC.items():
        text = text.replace(sentinel, punctuation)
    return text


def allowed_next(prefix, paths):
    return sorted({path[len(prefix)] for path in paths if len(prefix) < len(path) and path[:len(prefix)] == prefix})


def validate_enum(text):
    try:
        value = json.loads(text)
        if value not in OBJECTS:
            raise ValueError('Object outside the finite enum schema')
        return {'valid': True, 'value': value, 'error': None}
    except (ValueError, TypeError) as exc:
        return {'valid': False, 'value': None, 'error': str(exc)}


class ConstrainedBackend:
    def __init__(self, backend):
        self.backend = backend
        tokenizer = backend.tokenizer
        start = backend.model.config.decoder_start_token_id
        self.paths = [[start, *tokenizer.encode(encode_object(obj), add_special_tokens=False), tokenizer.eos_token_id]
                      for obj in OBJECTS]
        for path, obj in zip(self.paths, OBJECTS):
            assert tokenizer.unk_token_id not in path
            native = tokenizer.decode(path[1:-1], skip_special_tokens=False)
            assert json.loads(decode_native(native)) == obj

    def generate(self, request):
        import torch
        from transformers import set_seed
        backend = self.backend
        tokenizer = backend.tokenizer
        encoded = tokenizer(request['prompt'], return_tensors='pt', truncation=False)
        if encoded['input_ids'].shape[1] > 512:
            raise ValueError('Encoder input exceeds 512 tokens')
        if request['max_new_tokens'] < max(len(path) - 1 for path in self.paths):
            raise ValueError('Output budget cannot cover all finite-schema candidates')
        set_seed(request['seed'])
        def prefix_allowed(batch_id, input_ids):
            choices = allowed_next(input_ids.tolist(), self.paths)
            if not choices:
                raise ValueError('Prefix outside the finite language')
            return choices
        with torch.inference_mode():
            generated = backend.model.generate(**encoded, do_sample=True, temperature=request['temperature'],
                top_k=0, top_p=1.0, max_new_tokens=request['max_new_tokens'],
                prefix_allowed_tokens_fn=prefix_allowed, return_dict_in_generate=True, output_scores=True)
        sequence = generated.sequences[0].tolist()
        assert sequence in self.paths
        native = tokenizer.decode(sequence[1:-1], skip_special_tokens=False)
        branches = []
        for step, score in enumerate(generated.scores):
            choices = allowed_next(sequence[:step+1], self.paths)
            if len(choices) > 1:
                probabilities = torch.softmax(score[0], dim=-1)
                branches.append({'step': step, 'allowed_ids': choices,
                                 'probabilities_after_mask_and_temperature': [float(probabilities[i]) for i in choices],
                                 'chosen_id': sequence[step+1]})
        return {'text': decode_native(native), 'raw_native_text': native,
                'input_ids': encoded['input_ids'][0].tolist(), 'generated_ids': sequence[1:],
                'branches': branches, 'finish_reason': 'eos',
                'codec': CODEC, 'schema': ENUM_SCHEMA}
