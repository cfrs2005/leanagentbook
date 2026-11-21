"""Real database transitions plus real subprocess crash/restart tests."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

# Avoid shadowing Python's standard-library queue module.
SPEC = importlib.util.spec_from_file_location('durable_queue', Path(__file__).with_name('queue.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Queue, LostLease = MODULE.Queue, MODULE.LostLease


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'queue.db')
        self.clock = Clock()
        self.q = Queue(self.path, self.clock)

    def tearDown(self):
        self.q.close()
        self.temp.cleanup()

    def add(self, **kwargs):
        self.q.enqueue('a', **kwargs)
        return self.q.claim()

    def test_success(self):
        self.q.enqueue('a')
        MODULE.work_once(self.q)
        self.assertEqual(self.q.get('a')['state'], 'succeeded')
        self.assertEqual(len(self.q.inspect('a')['effects']), 3)

    def test_duplicate_submission(self):
        self.q.enqueue('a')
        self.assertFalse(self.q.enqueue('a'))
        MODULE.work_once(self.q)
        self.assertFalse(self.q.enqueue('a'))
        self.assertFalse(MODULE.work_once(self.q))
        self.assertEqual(self.q.get('a')['attempts'], 1)

    def test_duplicate_input_conflict(self):
        self.q.enqueue('a')
        for kwargs in ({'steps': 4}, {'total_timeout': 42}, {'delay': 1}, {'version': 2}):
            with self.assertRaises(ValueError):
                self.q.enqueue('a', **kwargs)

    def test_effect_deduplication(self):
        row = self.add()
        self.q.effect('a', row['token'], 0)
        self.q.effect('a', row['token'], 0)
        self.assertEqual(len(self.q.inspect('a')['effects']), 1)

    def test_exclusive_claim_connections(self):
        self.q.enqueue('a')
        other = Queue(self.path, self.clock)
        try:
            self.assertIsNotNone(self.q.claim())
            self.assertIsNone(other.claim())
        finally:
            other.close()

    def test_expired_owner_cannot_write_or_renew(self):
        row = self.add()
        self.clock.advance(2)
        for action in (lambda: self.q.effect('a', row['token'], 0),
                       lambda: self.q.heartbeat('a', row['token'], 1),
                       lambda: self.q.fail('a', row['token'])):
            with self.assertRaises(LostLease):
                action()

    def test_reclaimed_attempt_fences_old_token(self):
        old = self.add()
        self.clock.advance(2)
        self.assertIsNone(self.q.claim())
        self.clock.advance(0.11)
        new = self.q.claim()
        self.assertNotEqual(old['token'], new['token'])
        with self.assertRaises(LostLease):
            self.q.effect('a', old['token'], 0)
        self.q.effect('a', new['token'], 0)

    def test_heartbeat_extends_lease(self):
        row = self.add()
        self.clock.advance(0.8)
        self.q.heartbeat('a', row['token'], 2)
        self.clock.advance(1)
        self.q.effect('a', row['token'], 0)

    def test_heartbeat_cannot_extend_attempt_deadline(self):
        row = self.add(attempt_timeout=2)
        self.clock.advance(0.5)
        self.q.heartbeat('a', row['token'], 10)
        self.clock.advance(1.6)
        with self.assertRaises(LostLease):
            self.q.effect('a', row['token'], 0)
        self.q.claim()
        self.assertEqual(self.q.get('a')['state'], 'queued')

    def test_total_timeout_covers_queue_and_backoff(self):
        self.q.enqueue('a', total_timeout=0.05)
        row = self.q.claim()
        self.q.fail('a', row['token'])
        self.clock.advance(0.06)
        self.assertIsNone(self.q.claim())
        self.assertEqual(self.q.get('a')['state'], 'timed_out')

    def test_queued_cancellation(self):
        self.q.enqueue('a')
        self.assertTrue(self.q.cancel('a'))
        self.assertFalse(self.q.cancel('a'))
        self.assertIsNone(self.q.claim())

    def test_running_cancellation_preserves_past_effect(self):
        row = self.add()
        self.q.effect('a', row['token'], 0)
        self.q.cancel('a')
        with self.assertRaises(LostLease):
            self.q.checkpoint('a', row['token'], 0)
        self.assertEqual(len(self.q.inspect('a')['effects']), 1)

    def test_retry_backoff_and_dlq(self):
        row = self.add(max_attempts=2)
        self.q.fail('a', row['token'])
        self.assertIsNone(self.q.claim())
        self.clock.advance(0.11)
        row = self.q.claim()
        self.q.fail('a', row['token'])
        self.assertEqual(self.q.get('a')['state'], 'dlq')
        self.assertEqual(self.q.get('a')['attempts'], 2)
        self.clock.advance(100)
        self.assertIsNone(self.q.claim())

    def test_permanent_failure_no_retry(self):
        row = self.add()
        self.q.fail('a', row['token'], permanent=True)
        self.assertEqual(self.q.get('a')['state'], 'dlq')
        self.assertIsNone(self.q.claim())

    def test_unknown_version_is_quarantined(self):
        self.q.enqueue('a', version=2)
        self.assertIsNone(self.q.claim())
        self.assertEqual(self.q.get('a')['error'], 'unsupported payload version')

    def test_order_and_finish_guards(self):
        row = self.add()
        for action in (lambda: self.q.finish('a', row['token']),
                       lambda: self.q.checkpoint('a', row['token'], 0),
                       lambda: self.q.effect('a', row['token'], 2)):
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(self.q.inspect('a')['effects'], [])

    def test_compensation_is_idempotent(self):
        row = self.add()
        self.q.effect('a', row['token'], 0)
        with self.assertRaises(ValueError):
            self.q.compensate('a')
        self.q.cancel('a')
        self.q.compensate('a')
        self.q.compensate('a')
        data = self.q.inspect('a')
        self.assertEqual(len(data['reversals']), 1)
        self.assertEqual(sum(x['amount'] for x in data['effects'] + data['reversals']), 0)

    def test_invalid_configuration(self):
        for kwargs in ({'steps': 0}, {'delay': -1}, {'delay': float('nan')},
                       {'max_attempts': 0}, {'attempt_timeout': 0}, {'total_timeout': float('inf')},
                       {'steps': 1.5}, {'steps': True}, {'steps': '3'},
                       {'max_attempts': 2.5}, {'version': True}, {'version': 1.5},
                       {'delay': 'slow'}, {'attempt_timeout': False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.q.enqueue('a', **kwargs)
        for task in ('', '  ', None, 3):
            with self.subTest(task=task), self.assertRaises(ValueError):
                self.q.enqueue(task)
        self.assertEqual(self.q.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 0)


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'queue.db')
        self.q = Queue(self.path)

    def tearDown(self):
        self.q.close()
        self.temp.cleanup()

    def command(self, *args):
        return [sys.executable, str(Path(__file__).with_name('queue.py')), '--db', self.path, *args]

    def run_cli(self, *args):
        return subprocess.run(self.command(*args), capture_output=True, text=True, timeout=10)

    def crash_window(self, window, expected_effects, expected_checkpoint):
        self.q.enqueue('a')
        result = self.run_cli('worker', '--lease', '0.3', '--crash', window)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(len(self.q.inspect('a')['effects']), expected_effects)
        self.assertEqual(self.q.get('a')['checkpoint'], expected_checkpoint)
        result = self.run_cli('worker', '--lease', '0.3', '--run-for', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.q.inspect('a')
        self.assertEqual(data['task']['state'], 'succeeded')
        self.assertEqual(data['task']['attempts'], 2)
        self.assertEqual(len(data['effects']), 3)
        self.assertEqual(sum(x['amount'] for x in data['effects']), 30)
        if window == 'after-effect':
            self.assertIn('effect_deduplicated', [x['kind'] for x in data['events']])

    def test_crash_after_claim(self):
        self.crash_window('after-claim', 0, 0)

    def test_crash_inside_uncommitted_effect(self):
        self.crash_window('inside-effect', 0, 0)

    def test_crash_after_effect_before_checkpoint(self):
        self.crash_window('after-effect', 1, 0)

    def test_crash_after_checkpoint(self):
        self.crash_window('after-checkpoint', 1, 1)

    def test_real_heartbeat_during_longer_step(self):
        self.q.enqueue('a', steps=1, delay=0.8)
        result = self.run_cli('worker', '--lease', '0.3')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.q.inspect('a')
        self.assertEqual(data['task']['state'], 'succeeded')
        self.assertGreaterEqual(sum(e['kind'] == 'heartbeat' for e in data['events']), 3)

    def test_two_concurrent_workers(self):
        self.q.enqueue('a', delay=0.1)
        workers = [subprocess.Popen(self.command('worker', '--run-for', '0.8'),
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for worker in workers:
            out, err = worker.communicate(timeout=10)
            self.assertEqual(worker.returncode, 0, out + err)
        self.assertEqual(self.q.get('a')['attempts'], 1)
        self.assertEqual(len(self.q.inspect('a')['effects']), 3)

    def test_cli_failure_cancel_and_inspect(self):
        for args in [('enqueue', 'a'), ('worker', '--failure', 'permanent'), ('inspect', 'a'),
                     ('compensate', 'a'), ('enqueue', 'b'), ('cancel', 'b')]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            json.loads(result.stdout)
        self.assertEqual(self.q.get('a')['state'], 'dlq')
        self.assertEqual(self.q.get('b')['state'], 'cancelled')

    def test_cancel_live_worker(self):
        self.q.enqueue('a', steps=1, delay=1)
        worker = subprocess.Popen(self.command('worker', '--lease', '0.3'),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            end = time.monotonic() + 3
            while self.q.get('a')['state'] != 'running' and time.monotonic() < end:
                time.sleep(0.01)
            self.assertEqual(self.q.get('a')['state'], 'running')
            self.q.cancel('a')
            out, err = worker.communicate(timeout=5)
            self.assertEqual(worker.returncode, 0, out + err)
            self.assertEqual(self.q.get('a')['state'], 'cancelled')
            self.assertEqual(self.q.inspect('a')['effects'], [])
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.communicate()

    def test_real_attempt_timeout_reaches_dlq(self):
        self.q.enqueue('a', steps=1, delay=0.5, attempt_timeout=0.15, max_attempts=1)
        result = self.run_cli('worker', '--lease', '0.3', '--run-for', '0.6')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.q.get('a')['state'], 'dlq')
        self.assertEqual(self.q.inspect('a')['effects'], [])

    def remote_gap(self, unkeyed):
        command = [sys.executable, str(Path(__file__).with_name('remote_gap.py')),
                   '--client', str(Path(self.temp.name) / 'client.db'),
                   '--receiver', str(Path(self.temp.name) / 'receiver.db')]
        if unkeyed:
            command.append('--unkeyed')
        first = subprocess.run(command + ['--crash'], capture_output=True, text=True, timeout=5)
        self.assertEqual(first.returncode, 74, first.stderr)
        second = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(second.returncode, 0, second.stderr)
        data = json.loads(second.stdout)
        self.assertEqual(data['charges'], 2 if unkeyed else 1)
        self.assertEqual(data['total'], 20 if unkeyed else 10)

    def test_remote_receiver_key_closes_ack_gap(self):
        self.remote_gap(False)

    def test_remote_unkeyed_replay_duplicates_charge(self):
        self.remote_gap(True)


if __name__ == '__main__':
    unittest.main()
