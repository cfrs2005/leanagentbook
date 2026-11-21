"""Real HTTP, subprocess crash and tenant-bound approval tests; standard library."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from platform_app import ROOT, connect, envelope, stage, sync, server, process, call, make_report, dispatch, render


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cloud = self.root / 'cloud.sqlite'
        self.edge = self.root / 'edge.sqlite'

    def ingest(self, case='abnormal'):
        status, result = dispatch(self.cloud, 'demo-device-a', '/ingest', envelope(case))
        self.assertEqual(status, 201)
        return result['id']

    def reports(self):
        return dispatch(self.cloud, 'demo-viewer-a', '/reports', {})[1]['jobs']

    def test_actual_offline_and_ack_loss_replay(self):
        stage(self.edge, envelope('abnormal'))
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            self.assertTrue(sync(self.edge, f'http://127.0.0.1:{unavailable.getsockname()[1]}', 'demo-device-a')['offline'])
        with server(self.cloud) as url:
            self.assertTrue(sync(self.edge, url, 'demo-device-a', lose_ack=True)['ack_lost'])
            self.assertEqual(sync(self.edge, url, 'demo-device-a')['sent'], 1)
            self.assertEqual(sync(self.edge, url, 'demo-device-a')['sent'], 0)
        self.assertEqual(len(self.reports()), 1)

    def test_conflicting_id_does_not_replace_evidence(self):
        payload = envelope('normal')
        self.ingest('normal')
        self.assertEqual(dispatch(self.cloud, 'demo-device-a', '/ingest', envelope('abnormal'))[0], 409)
        stage(self.edge, payload)
        with self.assertRaises(ValueError):
            stage(self.edge, envelope('abnormal'))

    def test_tenant_and_device_identity_bound_to_server(self):
        payload = envelope('normal', tenant='tenant-b', device='robot-b')
        self.assertEqual(dispatch(self.cloud, 'demo-device-a', '/ingest', payload)[0], 403)
        self.assertEqual(dispatch(self.cloud, 'demo-device-b', '/ingest', payload)[0], 201)
        self.assertEqual(self.reports(), [])
        self.assertEqual(dispatch(self.cloud, 'bad-token', '/reports', {})[0], 401)
        self.assertEqual(dispatch(self.cloud, 'demo-device-a', '/reports', {})[0], 403)
        self.assertNotIn('robot-b', render(self.cloud))

    def test_crash_before_and_after_atomic_commit(self):
        for crash, code, expected in [('before_commit', 71, 'queued'), ('after_commit', 72, 'review')]:
            database = self.root / f'{crash}.sqlite'
            dispatch(database, 'demo-device-a', '/ingest', envelope('abnormal'))
            result = subprocess.run([sys.executable, str(ROOT / 'platform_app.py'), '--database', str(database), '--crash', crash], capture_output=True)
            self.assertEqual(result.returncode, code)
            with closing(connect(database)) as db:
                self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0], expected)
            process(database)
            with closing(connect(database)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE kind='report_ready'").fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0], 'review')

    def test_concurrent_replay_and_workers_accept_one_report(self):
        with server(self.cloud) as url:
            with ThreadPoolExecutor(max_workers=4) as pool:
                statuses = list(pool.map(lambda _: call(url, '/ingest', 'demo-device-a', envelope('abnormal'))[0], range(4)))
            self.assertEqual(sorted(statuses), [200, 200, 200, 201])
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: process(self.cloud), range(4)))
        with closing(connect(self.cloud)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE kind='report_ready'").fetchone()[0], 1)

    def test_approval_role_hash_and_action_bounds(self):
        key = self.ingest(); process(self.cloud)
        job = self.reports()[0]
        request = dict(id=key, report_hash=job['report_hash'], action='create_inspection_record')
        self.assertEqual(dispatch(self.cloud, 'demo-viewer-a', '/approve-inspection', request)[0], 403)
        self.assertEqual(dispatch(self.cloud, 'demo-approver-a', '/approve-inspection', dict(request, report_hash='stale'))[0], 409)
        self.assertEqual(dispatch(self.cloud, 'demo-approver-a', '/approve-inspection', dict(request, action='move_robot'))[0], 400)
        self.assertFalse(dispatch(self.cloud, 'demo-approver-a', '/approve-inspection', request)[1]['duplicate'])
        self.assertTrue(dispatch(self.cloud, 'demo-approver-a', '/approve-inspection', request)[1]['duplicate'])
        with closing(connect(self.cloud)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM inspections').fetchone()[0], 1)

    def test_missing_and_abnormal_states_preserved(self):
        for case, expected in [('normal', 'normal'), ('abnormal', 'abnormal'), ('missing', 'insufficient_data')]:
            report = make_report(envelope(case))
            self.assertEqual(report['status'], expected)
            self.assertFalse(report['root_cause_confirmed'])
            self.assertFalse(report['automatic_control'])
            self.assertTrue(report['review_required'])
            self.assertEqual(len(report['trace']), 4)

    def test_version_and_schema_fail_closed(self):
        for field, value in [('schema', 'v9'), ('policy_version', 'v9'), ('knowledge_version', 'v9'),
                             ('synthetic', False), ('software_version', 'unknown')]:
            with self.assertRaises(ValueError):
                stage(self.edge, dict(envelope('normal'), **{field: value}))
        with self.assertRaises(ValueError):
            stage(self.edge, dict(envelope('normal'), unknown='extra'))

    def test_model_failure_falls_back_and_draft_cannot_control(self):
        def failed(*args):
            raise TimeoutError('synthetic timeout')
        report = make_report(envelope('abnormal'), failed)
        self.assertEqual(report['language']['fallback_reason'], 'TimeoutError')
        draft = lambda *_: {'mode': 'scripted_adversarial_test', 'text': '<script>move_robot()</script>', 'verified': False}
        self.ingest(); process(self.cloud, model=draft)
        page = render(self.cloud)
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertFalse(self.reports()[0]['report']['automatic_control'])


if __name__ == '__main__':
    unittest.main()
