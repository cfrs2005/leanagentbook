"""Loopback-only real FLAN-T5 service; no production scheduling claims."""
import argparse
import json
import resource
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REVISION = '0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, TextStreamer
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model, local_files_only=True).float().cpu().eval()
    lock = threading.Lock()
    # Synthetic fixed token stream; the input length includes one EOS token.
    source = tokenizer('Summarize: The test device reports normal temperature and a clear path. ' * 80,
                       add_special_tokens=False, truncation=True, max_length=256).input_ids

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/generate':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024:
                    raise ValueError('invalid body length')
                body = json.loads(self.rfile.read(size))
                input_n, output_n = body['input_tokens'], body['output_tokens']
                if type(input_n) is not int or type(output_n) is not int:
                    raise ValueError('token counts must be integers')
                if not 2 <= input_n <= 256 or not 1 <= output_n <= 64:
                    raise ValueError('token counts outside lab bounds')
            except (KeyError, ValueError, TypeError):
                self.send_error(400, 'invalid token counts')
                return
            received = time.perf_counter()
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            def emit(event):
                self.wfile.write((json.dumps(event) + '\n').encode())
                self.wfile.flush()
            try:
                with lock:
                    started = time.perf_counter()
                    ids = torch.tensor([source[:input_n - 1] + [tokenizer.eos_token_id]])
                    generated = []
                    class TokenStreamer(TextStreamer):
                        def __init__(self):
                            self.prompt = True
                        def put(self, value):
                            if self.prompt:
                                self.prompt = False
                                return
                            token_ids = value.reshape(-1).tolist()
                            if len(token_ids) != 1:
                                raise RuntimeError('expected one generated token per event')
                            generated.extend(token_ids)
                            emit({'type': 'token', 'token_id': token_ids[0],
                                  'index': len(generated),
                                  'server_elapsed_s': time.perf_counter() - received})
                        def end(self):
                            pass
                    with torch.inference_mode():
                        model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                                       do_sample=False, min_new_tokens=output_n,
                                       max_new_tokens=output_n, use_cache=True,
                                       streamer=TokenStreamer())
                    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    emit({'type': 'done', 'input_tokens': ids.shape[1],
                          'output_tokens': len(generated), 'text': tokenizer.decode(generated),
                          'queue_s': started - received,
                          'server_elapsed_s': time.perf_counter() - received,
                          'process_peak_rss_bytes': rss if sys.platform == 'darwin' else rss * 1024})
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as exc:
                emit({'type': 'error', 'error': type(exc).__name__})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(json.dumps({'port': server.server_port, 'torch': torch.__version__,
                      'transformers': transformers.__version__, 'revision': REVISION,
                      'dtype': str(next(model.parameters()).dtype), 'device': 'cpu',
                      'torch_threads': 1, 'generation_slots': 1,
                      'queue_policy': 'thread lock; no FIFO guarantee; client bounded at 2',
                      'parameter_count': sum(p.numel() for p in model.parameters())}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
