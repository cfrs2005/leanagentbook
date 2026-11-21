"""Approval-bound fixed tool executed under a macOS deny-default OS policy."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from gateway import Gateway, Denied

MODES = ('normal', 'read_escape', 'write_escape', 'network', 'timeout', 'output_limit')


class IsolationUnavailable(RuntimeError):
    pass


class ToolFailure(RuntimeError):
    pass


def available():
    return sys.platform == 'darwin' and shutil.which('sandbox-exec') is not None


def bounded_process(command, timeout=2.0, limit=4096):
    """Drain both streams with a shared cap; terminate the process group on failure."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={'LANG': 'C', 'PATH': '/usr/bin:/bin'}, start_new_session=True)
    chunks = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    total = 0
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for stream in chunks:
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map() or proc.poll() is None:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise ToolFailure('timeout')
                for key, _ in selector.select(min(remaining, .05)):
                    data = os.read(key.fileobj.fileno(), min(1024, limit+1-total))
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    chunks[key.fileobj].extend(data)
                    total += len(data)
                    if total > limit:
                        raise ToolFailure('output_limit')
            if proc.returncode != 0:
                raise ToolFailure('worker_failed')
            return bytes(chunks[proc.stdout])
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()


def run_isolated(args):
    if not available():
        raise IsolationUnavailable('macOS sandbox-exec required; no unsandboxed fallback')
    with tempfile.TemporaryDirectory(prefix='book-fixed-tool-') as directory:
        root = Path(directory).resolve()
        job = root/'job'
        job.mkdir()
        outside = root/'outside.txt'
        outside.write_text('synthetic-private-canary')
        source = Path(__file__).with_name('isolated_worker.py').resolve()
        config = job/'input.json'
        result_file = job/'result.json'
        config.write_text(json.dumps(dict(args, outside=str(outside), result=str(result_file))))
        executable = Path(sys.executable).resolve()
        framework_binary = Path(sys.base_prefix)/'Resources/Python.app/Contents/MacOS/Python'
        if framework_binary.is_file():
            executable = framework_binary.resolve()
        # Read-only interpreter/library trees; no user home or temporary directory grant.
        read_roots = {str(Path(sys.base_prefix).resolve()), '/System/Library', '/usr/lib', '/usr/share'}
        lines = ['(version 1)', '(deny default)', '(allow sysctl-read)',
                 '(allow file-read-metadata)', '(allow file-read* (literal "/"))',
                 '(allow process-exec (literal '+json.dumps(str(executable))+'))',
                 '(allow file-read* (literal '+json.dumps(str(executable))+')'
                 ' (literal '+json.dumps(str(source))+')'
                 ' (literal '+json.dumps(str(config))+'))',
                 '(allow file-write* (literal '+json.dumps(str(result_file))+'))']
        for path in sorted(read_roots):
            lines.append('(allow file-read* (subpath '+json.dumps(path)+'))')
        profile = root/'policy.sb'
        profile.write_text('\n'.join(lines)+'\n')
        raw = bounded_process([shutil.which('sandbox-exec'), '-f', str(profile),
                               str(executable), '-I', '-S', str(source), str(config)])
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ToolFailure('invalid_output') from None
        if args['mode'] == 'normal':
            expected = {'status': 'ok', 'sum': sum(args['values']), 'count': len(args['values'])}
            if value != expected or json.loads(result_file.read_text()) != {k: expected[k] for k in ('sum', 'count')}:
                raise ToolFailure('invalid_output')
        elif value != {'status': 'denied', 'operation': args['mode']}:
            raise ToolFailure('isolation_failed')
        if outside.read_text() != 'synthetic-private-canary':
            raise ToolFailure('isolation_failed')
        return value


class IsolatedGateway(Gateway):
    """Preserves the invoice demo and adds one separately approved synthetic tool."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.launch_attempts = 0

    def _tool_request(self, actor, request):
        if (type(request) is not dict or set(request) != {'tool', 'args'}
                or request['tool'] != 'synthetic.summarize'):
            raise Denied('schema')
        args = request['args']
        if (type(args) is not dict or set(args) != {'resource', 'mode', 'values'}
                or args['resource'] != 'job-a' or args['mode'] not in MODES
                or type(args['values']) is not list or not 1 <= len(args['values']) <= 16
                or any(type(x) is not int or abs(x) > 1000 for x in args['values'])):
            raise Denied('schema')
        if (actor.tenant != 'alpha' or actor.subject != 'alice'
                or actor.service != 'agent-runtime' or 'tool_runner' not in actor.roles):
            raise Denied('resource')
        return {'resource': args['resource'], 'mode': args['mode'], 'values': list(args['values'])}

    def _tool_digest(self, actor, request):
        return hashlib.sha256(json.dumps({'subject': actor.subject, 'tenant': actor.tenant,
            'service': actor.service, 'request': request}, sort_keys=True).encode()).hexdigest()

    def approve_tool(self, approver_token, requester_token, request, ttl=60):
        with self._lock:
            actor = None
            try:
                actor = self._identity(approver_token)
                requester = self._identity(requester_token)
                args = self._tool_request(requester, request)
                request = {'tool': 'synthetic.summarize', 'args': args}
                if (actor.tenant != requester.tenant or actor.subject == requester.subject
                        or actor.service != 'agent-runtime' or 'approver' not in actor.roles
                        or type(ttl) not in (int, float) or not 0 < ttl <= 300):
                    raise Denied('approval_policy')
                import secrets
                handle = secrets.token_urlsafe(32)
                self._approvals[handle] = (self._tool_digest(requester, request), self.clock()+ttl)
                self._event(actor, 'isolated_approval', 'allow', 'issued')
                return handle
            except Denied as error:
                self._event(actor, 'isolated_approval', 'deny', str(error))
                raise

    def execute_tool(self, token, request, approval=None):
        with self._lock:
            actor = None
            try:
                actor = self._identity(token)
                args = self._tool_request(actor, request)
                request = {'tool': 'synthetic.summarize', 'args': args}
                grant = self._approvals.get(approval) if type(approval) is str else None
                if grant is None or grant[0] != self._tool_digest(actor, request) or self.clock() >= grant[1]:
                    raise Denied('approval')
                del self._approvals[approval]
                self.launch_attempts += 1
                result = run_isolated(args)
                self._event(actor, 'synthetic.summarize', 'allow', 'isolated_completed')
                return result
            except Denied as error:
                self._event(actor, 'synthetic.summarize', 'deny', str(error))
                raise
            except IsolationUnavailable:
                self._event(actor, 'synthetic.summarize', 'deny', 'isolation_unavailable')
                raise
            except ToolFailure as error:
                self._event(actor, 'synthetic.summarize', 'deny', str(error))
                raise
            except (OSError, ValueError):
                self._event(actor, 'synthetic.summarize', 'deny', 'worker_failed')
                raise ToolFailure('worker_failed') from None
