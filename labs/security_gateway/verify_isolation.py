"""Record real gateway-to-sandbox outcomes without storing temporary paths or secrets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from gateway import Principal, Denied
from isolated_gateway import IsolatedGateway, ToolFailure, available


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'measured_at_utc': datetime.now(timezone.utc).isoformat(),
              'platform': platform.platform(), 'python': platform.python_version(),
              'backend': 'macOS sandbox-exec deny-default fixed tool',
              'source_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ('isolated_gateway.py', 'isolated_worker.py', 'test_isolated_gateway.py')},
              'synthetic': True, 'cases': []}
    if not available():
        report['status'] = 'unsupported; isolation NOT verified'
        (args.output/'report.json').write_text(json.dumps(report, indent=2))
        return 2
    gateway = IsolatedGateway()
    user = gateway.provision_session(Principal('alice', 'alpha', frozenset({'tool_runner'})))
    reviewer = gateway.provision_session(Principal('reviewer', 'alpha', frozenset({'approver'})))
    request = {'tool': 'synthetic.summarize', 'args': {'resource': 'job-a', 'mode': 'normal', 'values': [2,3,5]}}
    try:
        gateway.execute_tool(user, request)
    except Denied:
        assert gateway.launch_attempts == 0
        report['cases'].append({'case': 'missing_approval', 'status': 'denied', 'launch_attempts': 0})
    else:
        raise AssertionError('Unauthorized launch')
    for mode in ('normal', 'read_escape', 'write_escape', 'network', 'timeout', 'output_limit'):
        request['args']['mode'] = mode
        handle = gateway.approve_tool(reviewer, user, request)
        try:
            outcome = gateway.execute_tool(user, request, handle)
            assert mode not in ('timeout', 'output_limit')
        except ToolFailure as error:
            assert str(error) == mode and mode in ('timeout', 'output_limit')
            outcome = {'status': 'stopped', 'reason': str(error)}
        report['cases'].append({'case': mode, 'outcome': outcome})
    report.update(status='passed', audit=gateway.audit, launch_attempts=gateway.launch_attempts,
                  limits=['fixed trusted worker, not arbitrary code',
                          'read-only interpreter/system trees and global file metadata allowed',
                          'network denied; actual probe is loopback bind, no external connection',
                          'Linux backend absent; portable gate tests only; OS tests explicitly skipped',
                          'no production authentication or payment/device side effect'])
    text = json.dumps(report, indent=2)
    assert all(secret not in text for secret in (user, reviewer, gateway._vault_secret, 'synthetic-private-canary'))
    (args.output/'report.json').write_text(text)
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(Path(__file__).parent), '-v'],
                           capture_output=True, text=True)
    (args.output/'tests.txt').write_text(tests.stdout+tests.stderr)
    if tests.returncode:
        return tests.returncode
    print('PASS: real gateway-to-sandbox normal/denial/timeout/output cases; tests recorded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
