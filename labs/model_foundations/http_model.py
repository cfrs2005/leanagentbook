"""Loopback-only HTTP API for real local FLAN-T5 generation."""
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from foundations import validate_output

SCHEMAS = {
    'integer': {'type': 'integer'},
    'record': {'type': 'object', 'properties': {'answer': {'type': 'string', 'minLength': 1},
               'source_ids': {'type': 'array', 'items': {'type': 'string'}}},
               'required': ['answer', 'source_ids'], 'additionalProperties': False},
}


def validate_request(value):
    if type(value) is not dict or set(value) != {'prompt', 'temperature', 'seed', 'max_new_tokens'}:
        raise ValueError('Expected prompt, temperature, seed and max_new_tokens')
    if type(value['prompt']) is not str or not 1 <= len(value['prompt']) <= 4096:
        raise ValueError('Prompt length outside 1..4096 characters')
    if type(value['temperature']) not in (int, float) or not math.isfinite(value['temperature']) or not 0 < value['temperature'] <= 2:
        raise ValueError('Temperature must be finite and in (0, 2]')
    if type(value['seed']) is not int or not 0 <= value['seed'] <= 2**32 - 1:
        raise ValueError('Seed must be an unsigned 32-bit integer')
    if type(value['max_new_tokens']) is not int or not 1 <= value['max_new_tokens'] <= 64:
        raise ValueError('Output budget must be in 1..64')
    return value


def check_generated(raw, schema_name):
    """Validate exact raw text against these two schema contracts; never repair it."""
    try:
        if schema_name == 'record':
            value = validate_output(raw)
        elif schema_name == 'integer':
            value = json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonstandard constant')))
            if type(value) not in (int, float) or not math.isfinite(value) or value != int(value):
                raise ValueError('Schema requires an integer JSON number, excluding bool')
        else:
            raise ValueError('Unsupported schema contract')
        return {'valid': True, 'value': value, 'error': None}
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        return {'valid': False, 'value': None, 'error': str(exc)}


class Backend:
    def __init__(self, model_path):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        torch.set_num_threads(2)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True).eval()

    def generate(self, request):
        import time
        import torch
        from transformers import set_seed
        encoded = self.tokenizer(request['prompt'], return_tensors='pt', truncation=False)
        input_ids = encoded['input_ids'][0].tolist()
        if len(input_ids) > 512:
            raise ValueError('Encoder input exceeds the lab limit of 512 tokens')
        set_seed(request['seed'])
        started = time.perf_counter()
        with torch.inference_mode():
            sequence = self.model.generate(**encoded, do_sample=True,
                temperature=request['temperature'], top_p=1.0, top_k=0,
                max_new_tokens=request['max_new_tokens'])[0].tolist()
        output_ids = sequence[1:]
        return {'text': self.tokenizer.decode(sequence, skip_special_tokens=True),
                'input_ids': input_ids, 'generated_ids': output_ids,
                'input_tokens': len(input_ids), 'output_tokens': len(output_ids),
                'decoder_start_id': sequence[0],
                'finish_reason': 'eos' if output_ids and output_ids[-1] == self.tokenizer.eos_token_id else 'length',
                'generation_seconds': time.perf_counter() - started}


def make_server(backend):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            if self.path != '/generate':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Invalid body size')
                request = validate_request(json.loads(self.rfile.read(size)))
                response, code = backend.generate(request), 200
            except (ValueError, TypeError, OverflowError) as exc:
                response, code = {'error': str(exc)}, 400
            except Exception:
                response, code = {'error': 'Model generation failed'}, 500
            data = json.dumps(response, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return HTTPServer(('127.0.0.1', 0), Handler)
