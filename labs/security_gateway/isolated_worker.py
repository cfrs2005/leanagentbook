"""Fixed synthetic worker. No caller-provided code, paths, commands or URLs."""
import json
import resource
import socket
import sys
import time
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
config = json.loads(Path(sys.argv[1]).read_text())
mode = config['mode']
if mode == 'normal':
    result = {'sum': sum(config['values']), 'count': len(config['values'])}
    Path(config['result']).write_text(json.dumps(result))
    print(json.dumps({'status': 'ok', **result}))
elif mode in ('read_escape', 'write_escape', 'network'):
    try:
        if mode == 'read_escape':
            Path(config['outside']).read_text()
        elif mode == 'write_escape':
            Path(config['outside']).write_text('changed')
        else:
            with socket.socket() as connection:
                connection.bind(('127.0.0.1', 0))
    except PermissionError:
        print(json.dumps({'status': 'denied', 'operation': mode}))
    else:
        print(json.dumps({'status': 'unexpectedly_allowed', 'operation': mode}))
elif mode == 'timeout':
    time.sleep(10)
elif mode == 'output_limit':
    while True:
        sys.stdout.write('x' * 1024)
        sys.stdout.flush()
