"""Portable authorization tests and explicit platform-gated real isolation checks."""
import copy
import json
import socket
import unittest
from unittest.mock import patch
from gateway import Principal, Denied
from isolated_gateway import IsolatedGateway, IsolationUnavailable, ToolFailure, available


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.g = IsolatedGateway(clock=lambda: 100)
        self.user = self.g.provision_session(Principal('alice', 'alpha', frozenset({'tool_runner'})))
        self.reviewer = self.g.provision_session(Principal('reviewer', 'alpha', frozenset({'approver'})))
        self.request = {'tool': 'synthetic.summarize', 'args': {'resource': 'job-a', 'mode': 'normal', 'values': [2,3,5]}}

    def test_denials_never_launch(self):
        no_role = self.g.provision_session(Principal('alice', 'alpha', frozenset()))
        other_tenant = self.g.provision_session(Principal('alice', 'beta', frozenset({'tool_runner'})))
        with patch('isolated_gateway.run_isolated') as launch:
            for token in ('forged', no_role, other_tenant, self.user):
                with self.assertRaises(Denied):
                    self.g.execute_tool(token, self.request)
            launch.assert_not_called()
        self.assertEqual(self.g.launch_attempts, 0)

    def test_approval_binds_all_parameters(self):
        handle = self.g.approve_tool(self.reviewer, self.user, self.request)
        with patch('isolated_gateway.run_isolated') as launch:
            for key, value in [('values', [999]), ('mode', 'read_escape'), ('resource', 'job-b')]:
                changed = copy.deepcopy(self.request)
                changed['args'][key] = value
                with self.assertRaises(Denied):
                    self.g.execute_tool(self.user, changed, handle)
            launch.assert_not_called()

    def test_independent_approver_and_expiry(self):
        self_approver = self.g.provision_session(Principal('alice', 'alpha', frozenset({'approver'})))
        with self.assertRaises(Denied):
            self.g.approve_tool(self_approver, self.user, self.request)
        handle = self.g.approve_tool(self.reviewer, self.user, self.request, ttl=1)
        self.g.clock = lambda: 101
        with self.assertRaises(Denied):
            self.g.execute_tool(self.user, self.request, handle)
        self.assertEqual(self.g.launch_attempts, 0)

    def test_missing_backend_fails_closed(self):
        handle = self.g.approve_tool(self.reviewer, self.user, self.request)
        with patch('isolated_gateway.available', return_value=False), patch('isolated_gateway.subprocess.Popen') as spawn:
            with self.assertRaises(IsolationUnavailable):
                self.g.execute_tool(self.user, self.request, handle)
            spawn.assert_not_called()
        self.assertEqual(self.g.audit[-1]['reason'], 'isolation_unavailable')
        with self.assertRaises(Denied):
            self.g.execute_tool(self.user, self.request, handle)

    def test_secret_and_invalid_input_not_audited(self):
        secret = self.g._vault_secret
        changed = copy.deepcopy(self.request)
        changed['args']['values'] = [secret]
        with self.assertRaises(Denied):
            self.g.execute_tool(self.user, changed)
        exported = json.dumps(self.g.audit)
        for private in (secret, self.user, self.reviewer):
            self.assertNotIn(private, exported)


@unittest.skipUnless(available(), 'Real macOS sandbox-exec backend unavailable; isolation NOT verified')
class RealIsolationTests(unittest.TestCase):
    setUp = AuthorizationTests.setUp
    def run_mode(self, mode):
        self.request['args']['mode'] = mode
        handle = self.g.approve_tool(self.reviewer, self.user, self.request)
        return self.g.execute_tool(self.user, self.request, handle)

    def test_normal_read_write_and_single_use(self):
        handle = self.g.approve_tool(self.reviewer, self.user, self.request)
        self.assertEqual(self.g.execute_tool(self.user, self.request, handle), {'status': 'ok', 'sum': 10, 'count': 3})
        with self.assertRaises(Denied):
            self.g.execute_tool(self.user, self.request, handle)
        self.assertEqual(self.g.launch_attempts, 1)

    def test_outside_read_denied(self):
        self.assertEqual(self.run_mode('read_escape'), {'status': 'denied', 'operation': 'read_escape'})

    def test_outside_write_denied(self):
        self.assertEqual(self.run_mode('write_escape'), {'status': 'denied', 'operation': 'write_escape'})

    def test_network_denied_with_unsandboxed_baseline(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
        self.assertEqual(self.run_mode('network'), {'status': 'denied', 'operation': 'network'})

    def test_timeout(self):
        with self.assertRaisesRegex(ToolFailure, '^timeout$'):
            self.run_mode('timeout')
        self.assertEqual(self.g.audit[-1]['reason'], 'timeout')

    def test_output_cap_and_audit_projection(self):
        with self.assertRaisesRegex(ToolFailure, '^output_limit$'):
            self.run_mode('output_limit')
        exported = json.dumps(self.g.audit)
        for private in (self.user, self.reviewer, self.g._vault_secret, 'synthetic-private-canary', 'xxxxxxxx'):
            self.assertNotIn(private, exported)
        self.assertEqual(self.g.audit[-1]['reason'], 'output_limit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
