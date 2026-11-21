"""Loopback-only distributed scheduling lab; Python 3.11+, no dependencies."""
import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


# Keep loopback traffic independent of OS or environment proxy settings.
OPENER = build_opener(ProxyHandler({}))

def request(url, path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = Request(url + path, body, {'Content-Type': 'application/json'})
    try:
        with OPENER.open(req, timeout=2) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


class State:
    def __init__(self, lease=0.6, budget=1000, tenant_limit=2, global_limit=3):
        self.lock = threading.Lock()
        self.tasks = {}
        self.registry = {}
        self.events = []
        self.tenants = ['alpha', 'beta']
        self.cursor = 0
        self.lease = lease
        self.budget = budget
        self.tenant_limit = tenant_limit
        self.global_limit = global_limit
        self.reserved = Counter()
        self.started = time.monotonic()

    def event(self, kind, **fields):
        self.events.append(dict(t=round(time.monotonic() - self.started, 6),
                                kind=kind, **fields))

    def expire(self, now):
        for task in self.tasks.values():
            if task['status'] == 'running' and task['deadline'] <= now:
                task['status'] = 'queued'
                self.event('expired', id=task['id'], worker=task['worker'],
                           generation=task['generation'])

    def dispatch(self, path, body):
        with self.lock:
            now = time.monotonic()
            self.expire(now)
            if path == '/snapshot':
                return 200, json.loads(json.dumps(dict(
                    tasks=list(self.tasks.values()), events=self.events,
                    registry=self.registry, reserved=dict(self.reserved))))
            if path == '/submit':
                tenant, key = body['tenant'], body['key']
                n, delay, cost = body['n'], body['delay'], body['cost']
                if (tenant not in self.tenants or not isinstance(key, str) or
                    not 1 <= len(key) <= 80 or type(n) is not int or
                    not 1 <= n <= 100000 or type(delay) not in (int, float) or
                    not 0 <= delay <= 2 or type(cost) is not int or not 1 <= cost <= 100):
                    return 400, {'error': 'invalid task'}
                task_id = tenant + ':' + key
                spec = dict(n=n, delay=delay, cost=cost)
                if task_id in self.tasks:
                    old = self.tasks[task_id]
                    if old['spec'] != spec:
                        return 409, {'error': 'idempotency conflict'}
                    return 200, {'id': task_id, 'duplicate': True}
                if self.reserved[tenant] + cost > self.budget:
                    return 429, {'error': 'synthetic token budget exhausted'}
                self.reserved[tenant] += cost
                self.tasks[task_id] = dict(id=task_id, tenant=tenant, spec=spec,
                                           status='queued', generation=0)
                self.event('submitted', id=task_id, tenant=tenant)
                return 201, {'id': task_id}
            if path == '/register':
                worker = body['worker']
                if (not isinstance(worker, str) or not 1 <= len(worker) <= 80 or
                    body['capability'] != 'sum_squares' or type(body['pid']) is not int):
                    return 400, {'error': 'invalid worker'}
                if worker in self.registry:
                    return 409, {'error': 'worker identity already registered'}
                self.registry[worker] = dict(pid=body['pid'], seen=now,
                                             capability='sum_squares')
                self.event('registered', worker=worker, pid=body['pid'])
                return 201, {'ok': True}
            if path not in ('/claim', '/heartbeat', '/complete'):
                return 404, {'error': 'unknown route'}
            worker = body['worker']
            if worker not in self.registry:
                return 403, {'error': 'unregistered worker'}
            self.registry[worker]['seen'] = now
            if path == '/claim':
                running = [t for t in self.tasks.values() if t['status'] == 'running']
                if len(running) >= self.global_limit or any(t['worker'] == worker for t in running):
                    return 200, {'task': None}
                counts = Counter(t['tenant'] for t in running)
                for offset in range(len(self.tenants)):
                    index = (self.cursor + offset) % len(self.tenants)
                    tenant = self.tenants[index]
                    if counts[tenant] >= self.tenant_limit:
                        continue
                    for task in self.tasks.values():
                        if task['tenant'] == tenant and task['status'] == 'queued':
                            task.update(status='running', worker=worker,
                                        generation=task['generation'] + 1,
                                        deadline=now + self.lease)
                            self.cursor = (index + 1) % len(self.tenants)
                            self.event('assigned', id=task['id'], tenant=tenant,
                                       worker=worker, generation=task['generation'],
                                       global_running=len(running) + 1,
                                       tenant_running=counts[tenant] + 1)
                            return 200, {'task': task.copy()}
                return 200, {'task': None}
            task = self.tasks[body['id']]
            if task['generation'] != body['generation'] or task.get('worker') != worker:
                self.event('stale_rejected', id=task['id'], worker=worker)
                return 409, {'error': 'stale owner'}
            if path == '/complete' and task['status'] == 'done':
                if body['result'] == task['result']:
                    self.event('duplicate_result', id=task['id'])
                    return 200, {'duplicate': True}
                return 409, {'error': 'result conflict'}
            if task['status'] != 'running':
                return 409, {'error': 'lease not active'}
            if path == '/heartbeat':
                task['deadline'] = now + self.lease
                self.event('heartbeat', id=task['id'], worker=worker)
                return 200, {'ok': True}
            n = task['spec']['n']
            expected = n * (n - 1) * (2 * n - 1) // 6
            if type(body['result']) is not int or body['result'] != expected:
                return 422, {'error': 'invalid synthetic result'}
            task.update(status='done', result=body['result'])
            self.event('completed', id=task['id'], tenant=task['tenant'], worker=worker)
            return 200, {'duplicate': False}


@contextmanager
def coordinator(**options):
    state = State(**options)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 8192:
                    raise ValueError('body too large')
                self.connection.settimeout(2)
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise ValueError('object required')
                if self.command == 'GET' and self.path != '/snapshot':
                    status, result = 405, {'error': 'POST required'}
                else:
                    status, result = state.dispatch(self.path, body)
                    # Serialize inside a separate lock so snapshots cannot mutate mid-encode.
                    with state.lock:
                        result = json.dumps(result).encode()
            except (ValueError, KeyError, TypeError, TimeoutError):
                status, result = 400, {'error': 'invalid request'}
            if not isinstance(result, bytes):
                result = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(result)))
            self.end_headers()
            self.wfile.write(result)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def worker(url, name, stall=False):
    status, _ = request(url, '/register', dict(worker=name, pid=os.getpid(), capability='sum_squares'))
    if status != 201:
        return 1
    while True:
        status, response = request(url, '/claim', {'worker': name})
        if status != 200:
            return 2
        task = response['task']
        if task is None:
            time.sleep(0.02)
            continue
        payload = dict(worker=name, id=task['id'], generation=task['generation'])
        if stall:
            time.sleep(60)
            continue
        end = time.monotonic() + task['spec']['delay']
        alive = True
        while time.monotonic() < end:
            time.sleep(min(0.1, max(0, end - time.monotonic())))
            status, _ = request(url, '/heartbeat', payload)
            if status != 200:
                alive = False
                break
        if alive:
            payload['result'] = sum(i * i for i in range(task['spec']['n']))
            request(url, '/complete', payload)


@contextmanager
def workers(url, count, prefix='worker', stall=False):
    processes = []
    try:
        for index in range(count):
            args = [sys.executable, str(Path(__file__).resolve()), '--url', url,
                    '--name', f'{prefix}-{index}']
            if stall:
                args.append('--stall')
            processes.append(subprocess.Popen(args))
        yield processes
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--stall', action='store_true')
    args = parser.parse_args()
    sys.exit(worker(args.url, args.name, args.stall))
