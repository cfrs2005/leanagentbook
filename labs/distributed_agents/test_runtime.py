"""Offline HTTP/process integration tests with raw evidence output."""
from collections import Counter
import json
import os
from pathlib import Path
import platform
import time
import unittest
from urllib.request import Request
from urllib.error import HTTPError
from runtime import OPENER, coordinator, request, workers

RESULTS = Path(os.environ.get('DISTRIBUTED_RESULTS_DIR', Path(__file__).parent / 'output'))


def snapshot(url):
    status, body = request(url, '/snapshot')
    assert status == 200
    return body


def wait_for(url, predicate, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        state = snapshot(url)
        if predicate(state):
            return state
        time.sleep(0.02)
    raise AssertionError('condition timed out')


def submit(url, tenant='alpha', key='one', delay=0.12, cost=10, n=1000):
    return request(url, '/submit', dict(tenant=tenant, key=key, n=n, delay=delay, cost=cost))


def register(url, name):
    return request(url, '/register', dict(worker=name, pid=os.getpid(), capability='sum_squares'))


def save(name, data):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / (name + '.json')).write_text(json.dumps(dict(
        python=platform.python_version(), platform=platform.platform(),
        measurement='monotonic seconds; synthetic sum-of-squares; loopback HTTP',
        **data), ensure_ascii=False, indent=2) + '\n')


class Integration(unittest.TestCase):
    def test_load_and_backlog_recovery(self):
        for count in (1, 3):
            with coordinator() as url:
                for tenant, total in [('alpha', 36), ('beta', 12)]:
                    for index in range(total):
                        self.assertEqual(submit(url, tenant, str(index))[0], 201)
                before = snapshot(url)
                self.assertEqual(Counter(t['status'] for t in before['tasks']), {'queued': 48})
                start = time.monotonic()
                with workers(url, count) as processes:
                    state = wait_for(url, lambda s: all(t['status'] == 'done' for t in s['tasks']))
                    elapsed = time.monotonic() - start
                    self.assertTrue(all(p.poll() is None for p in processes))
                    pids = [p.pid for p in processes]
                self.assertTrue(all(p.poll() is not None for p in processes))
                assignments = [e for e in state['events'] if e['kind'] == 'assigned']
                completions = [e for e in state['events'] if e['kind'] == 'completed']
                first24 = Counter(e['tenant'] for e in assignments[:24])
                self.assertEqual(first24, {'alpha': 12, 'beta': 12})
                self.assertEqual(len(assignments), 48)
                self.assertEqual(len({e['worker'] for e in completions}), count)
                self.assertLessEqual(max(e['global_running'] for e in assignments), 3)
                self.assertLessEqual(max(e['tenant_running'] for e in assignments), 2)
                self.assertEqual(len(set(pids)), count)
                self.assertNotIn(os.getpid(), pids)
                per_tenant = {}
                for tenant in ('alpha', 'beta'):
                    tasks = [t for t in state['tasks'] if t['tenant'] == tenant]
                    per_tenant[tenant] = dict(completed=len(tasks),
                        aggregate=sum(t['result'] for t in tasks),
                        last_completion_s=max(e['t'] for e in completions if e['tenant'] == tenant))
                save(f'load-{count}', dict(worker_pids=pids, initial_backlog=48,
                    elapsed_s=elapsed, throughput_tasks_s=48 / elapsed,
                    first24_assignments=dict(first24), per_tenant=per_tenant, state=state))

    def test_crash_takeover_and_stale_fencing(self):
        with coordinator(lease=0.45) as url:
            self.assertEqual(submit(url)[0], 201)
            with workers(url, 1, prefix='victim', stall=True) as victims:
                original = wait_for(url, lambda s: s['tasks'][0]['status'] == 'running')['tasks'][0]
                start = time.monotonic()
                victims[0].kill()
                victims[0].wait(timeout=3)
                with workers(url, 2, prefix='replacement'):
                    state = wait_for(url, lambda s: s['tasks'][0]['status'] == 'done')
                recovery = time.monotonic() - start
            current = state['tasks'][0]
            self.assertEqual(current['generation'], 2)
            stale = dict(worker=original['worker'], id=original['id'],
                         generation=original['generation'], result=current['result'])
            self.assertEqual(request(url, '/complete', stale)[0], 409)
            self.assertEqual(request(url, '/heartbeat', stale)[0], 409)
            accepted = dict(worker=current['worker'], id=current['id'],
                            generation=current['generation'], result=current['result'])
            self.assertEqual(request(url, '/complete', accepted), (200, {'duplicate': True}))
            accepted['result'] = -1
            self.assertEqual(request(url, '/complete', accepted)[0], 409)
            final = snapshot(url)
            self.assertEqual(sum(e['kind'] == 'completed' for e in final['events']), 1)
            save('crash', dict(recovery_s=recovery, stale_complete_status=409,
                stale_heartbeat_status=409, duplicate_complete_status=200, state=final))

    def test_heartbeat_and_expired_owner(self):
        with coordinator(lease=0.35) as url:
            submit(url, delay=0.9)
            with workers(url, 1):
                state = wait_for(url, lambda s: s['tasks'][0]['status'] == 'done')
            self.assertEqual(state['tasks'][0]['generation'], 1)
            self.assertGreaterEqual(sum(e['kind'] == 'heartbeat' for e in state['events']), 3)
            save('heartbeat', dict(state=state))
        with coordinator(lease=0.12) as url:
            submit(url)
            register(url, 'old')
            _, response = request(url, '/claim', {'worker': 'old'})
            task = response['task']
            time.sleep(0.16)
            status, _ = request(url, '/heartbeat', dict(worker='old', id=task['id'], generation=1))
            self.assertEqual(status, 409)

    def test_validation_budget_and_duplicate_delivery(self):
        with coordinator(budget=20) as url:
            self.assertEqual(submit(url)[0], 201)
            self.assertEqual(submit(url), (200, {'id': 'alpha:one', 'duplicate': True}))
            self.assertEqual(submit(url, n=2000)[0], 409)
            self.assertEqual(submit(url, key='two')[0], 201)
            self.assertEqual(submit(url, key='three')[0], 429)
            self.assertEqual(submit(url, tenant='beta')[0], 201)
            self.assertEqual(submit(url, tenant='unknown')[0], 400)
            self.assertEqual(submit(url, n=100001)[0], 400)
            self.assertEqual(request(url, '/claim', {'worker': 'unknown'})[0], 403)
            self.assertEqual(request(url, '/submit', {'command': 'echo unsafe'})[0], 400)
            self.assertEqual(request(url, '/missing', {})[0], 404)
            self.assertEqual(request(url, '/claim')[0], 405)
            malformed = Request(url + '/submit', b'{broken', {'Content-Type': 'application/json'})
            with self.assertRaises(HTTPError) as error:
                OPENER.open(malformed, timeout=2)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
            register(url, 'manual')
            _, response = request(url, '/claim', {'worker': 'manual'})
            task = response['task']
            bad = dict(worker='manual', id=task['id'], generation=task['generation'], result=-1)
            self.assertEqual(request(url, '/complete', bad)[0], 422)
            self.assertIsNone(request(url, '/claim', {'worker': 'manual'})[1]['task'])
            self.assertEqual(snapshot(url)['reserved'], {'alpha': 20, 'beta': 10})
            save('validation', dict(scope='validation, idempotency and per-tenant budget', state=snapshot(url)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
