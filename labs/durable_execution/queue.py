"""Single-host durable queue; synthetic effects, Python 3.11+ only."""
import argparse
from contextlib import contextmanager
import json
import math
import os
import sqlite3
import time
import uuid


class LostLease(Exception):
    """The attempt is no longer authorized to mutate state."""


class Queue:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(
          id TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL,
          state TEXT NOT NULL, checkpoint INTEGER NOT NULL DEFAULT 0,
          attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
          available REAL NOT NULL, deadline REAL NOT NULL, total_timeout REAL NOT NULL, attempt_timeout REAL NOT NULL,
          token TEXT, lease_until REAL, attempt_until REAL, error TEXT);
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL,
          at REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS effects(
          task TEXT NOT NULL, step INTEGER NOT NULL, amount INTEGER NOT NULL,
          PRIMARY KEY(task, step));
        CREATE TABLE IF NOT EXISTS reversals(
          task TEXT NOT NULL, step INTEGER NOT NULL, amount INTEGER NOT NULL,
          PRIMARY KEY(task, step));
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')

    def event(self, task, kind, detail=''):
        self.db.execute('INSERT INTO events(task,at,kind,detail) VALUES(?,?,?,?)',
                        (task, self.clock(), kind, detail))

    def get(self, task):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task,)).fetchone()
        if row is None:
            raise KeyError(task)
        return dict(row)

    def enqueue(self, task, steps=3, delay=0.0, max_attempts=3,
                total_timeout=3600.0, attempt_timeout=600.0, version=1):
        if (not isinstance(task, str) or not task.strip()
                or any(type(value) is not int or value < 1 for value in (steps, max_attempts, version))
                or any(type(value) not in (int, float) for value in (delay, total_timeout, attempt_timeout))):
            raise ValueError('Invalid task identity or limit types')
        if (delay < 0 or total_timeout <= 0
                or attempt_timeout <= 0 or not all(map(math.isfinite,
                    (delay, total_timeout, attempt_timeout)))):
            raise ValueError('Invalid task limits')
        payload = json.dumps({'steps': steps, 'delay': delay}, sort_keys=True)
        with self.tx():
            old = self.db.execute('SELECT * FROM tasks WHERE id=?', (task,)).fetchone()
            if old:
                if (old['payload'], old['version'], old['max_attempts'], old['attempt_timeout'], old['total_timeout']) != (
                        payload, version, max_attempts, attempt_timeout, total_timeout):
                    raise ValueError('Idempotency key reused with different input')
                return False
            now = self.clock()
            self.db.execute('''INSERT INTO tasks(id,payload,version,state,max_attempts,
                available,deadline,total_timeout,attempt_timeout) VALUES(?,?,?,'queued',?,?,?,?,?)''',
                (task, payload, version, max_attempts, now, now + total_timeout, total_timeout, attempt_timeout))
            self.event(task, 'enqueued')
        return True

    def terminal(self, task, state, reason):
        self.db.execute('UPDATE tasks SET state=?,token=NULL,error=? WHERE id=?',
                        (state, reason, task))
        self.event(task, state, reason)

    def retry(self, row, reason):
        if row['attempts'] >= row['max_attempts']:
            self.terminal(row['id'], 'dlq', reason)
        else:
            backoff = min(30.0, 0.1 * 2 ** min(row['attempts'] - 1, 20))
            self.db.execute("UPDATE tasks SET state='queued',token=NULL,available=?,error=? WHERE id=?",
                            (self.clock() + backoff, reason, row['id']))
            self.event(row['id'], 'retry_scheduled', reason)

    def reap(self):
        # Called inside the claim transaction; no separate scheduler is required.
        now = self.clock()
        for row in self.db.execute("SELECT * FROM tasks WHERE state IN ('queued','running')").fetchall():
            if row['deadline'] <= now:
                self.terminal(row['id'], 'timed_out', 'total deadline')
            elif row['state'] == 'running' and min(row['lease_until'], row['attempt_until']) <= now:
                self.retry(row, 'lease or attempt timeout')

    def claim(self, lease=1.0):
        if lease <= 0 or not math.isfinite(lease):
            raise ValueError('Invalid lease')
        with self.tx():
            self.reap()
            while True:
                row = self.db.execute("SELECT * FROM tasks WHERE state='queued' AND available<=? ORDER BY available,id LIMIT 1",
                                      (self.clock(),)).fetchone()
                if row is None:
                    return None
                if row['version'] != 1:
                    self.terminal(row['id'], 'dlq', 'unsupported payload version')
                    continue
                token = uuid.uuid4().hex
                now = self.clock()
                self.db.execute("UPDATE tasks SET state='running',token=?,attempts=attempts+1,lease_until=?,attempt_until=? WHERE id=?",
                                (token, now + lease, now + row['attempt_timeout'], row['id']))
                self.event(row['id'], 'claimed', token)
                return self.get(row['id'])

    def owned(self, task, token):
        row = self.get(task)
        if (row['state'] != 'running' or row['token'] != token or
                min(row['lease_until'], row['attempt_until'], row['deadline']) <= self.clock()):
            raise LostLease(task)
        return row

    def heartbeat(self, task, token, lease):
        if lease <= 0 or not math.isfinite(lease):
            raise ValueError('Invalid lease')
        with self.tx():
            self.owned(task, token)
            self.db.execute('UPDATE tasks SET lease_until=? WHERE id=?', (self.clock() + lease, task))
            self.event(task, 'heartbeat')

    def effect(self, task, token, step, crash=False):
        with self.tx():
            row = self.owned(task, token)
            if step != row['checkpoint'] or step >= json.loads(row['payload'])['steps']:
                raise ValueError('Out-of-order effect')
            cur = self.db.execute('INSERT OR IGNORE INTO effects VALUES(?,?,10)', (task, step))
            self.event(task, 'effect_applied' if cur.rowcount else 'effect_deduplicated', str(step))
            if crash:
                os._exit(73)  # Real process exit before transaction commit.

    def checkpoint(self, task, token, step):
        with self.tx():
            row = self.owned(task, token)
            if row['checkpoint'] != step or not self.db.execute(
                    'SELECT 1 FROM effects WHERE task=? AND step=?', (task, step)).fetchone():
                raise ValueError('Missing or out-of-order effect')
            self.db.execute('UPDATE tasks SET checkpoint=? WHERE id=?', (step + 1, task))
            self.event(task, 'checkpoint', str(step + 1))

    def finish(self, task, token):
        with self.tx():
            row = self.owned(task, token)
            if row['checkpoint'] != json.loads(row['payload'])['steps']:
                raise ValueError('Incomplete task')
            self.terminal(task, 'succeeded', '')

    def fail(self, task, token, permanent=False):
        with self.tx():
            row = self.owned(task, token)
            if permanent:
                self.terminal(task, 'dlq', 'permanent failure')
            else:
                self.retry(row, 'transient failure')

    def cancel(self, task):
        with self.tx():
            row = self.get(task)
            if row['state'] in ('queued', 'running'):
                self.terminal(task, 'cancelled', 'operator request')
                return True
            return False

    def compensate(self, task):
        # A synthetic local Saga compensation, not a rollback of external work.
        with self.tx():
            row = self.get(task)
            if row['state'] not in ('cancelled', 'timed_out', 'dlq'):
                raise ValueError('Compensation requires unsuccessful terminal state')
            self.db.execute('''INSERT OR IGNORE INTO reversals
                SELECT task,step,-amount FROM effects WHERE task=?''', (task,))
            self.event(task, 'compensated')

    def inspect(self, task):
        return {'task': self.get(task), 'events': [dict(r) for r in self.db.execute(
            'SELECT * FROM events WHERE task=? ORDER BY seq', (task,))],
            'effects': [dict(r) for r in self.db.execute('SELECT * FROM effects WHERE task=? ORDER BY step', (task,))],
            'reversals': [dict(r) for r in self.db.execute('SELECT * FROM reversals WHERE task=? ORDER BY step', (task,))]}


def work_once(queue, lease=1.0, crash='none', failure='none'):
    row = queue.claim(lease)
    if row is None:
        return False
    task, token = row['id'], row['token']
    if crash == 'after-claim':
        os._exit(73)
    try:
        if failure != 'none':
            queue.fail(task, token, permanent=failure == 'permanent')
            return True
        payload = json.loads(row['payload'])
        for step in range(row['checkpoint'], payload['steps']):
            # Wall-clock lease timestamps survive restart; monotonic controls local sleep.
            end = time.monotonic() + payload['delay']
            while time.monotonic() < end:
                time.sleep(min(lease / 3, max(0, end - time.monotonic())))
                queue.heartbeat(task, token, lease)
            queue.effect(task, token, step, crash == 'inside-effect')
            if crash == 'after-effect':
                os._exit(73)
            queue.checkpoint(task, token, step)
            if crash == 'after-checkpoint':
                os._exit(73)
        queue.finish(task, token)
    except LostLease:
        # A cancelled or expired attempt cannot publish more local effects.
        pass
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('enqueue')
    add.add_argument('task')
    add.add_argument('--steps', type=int, default=3)
    add.add_argument('--delay', type=float, default=0)
    add.add_argument('--max-attempts', type=int, default=3)
    add.add_argument('--total-timeout', type=float, default=3600)
    add.add_argument('--attempt-timeout', type=float, default=600)
    worker = sub.add_parser('worker')
    worker.add_argument('--lease', type=float, default=1)
    worker.add_argument('--run-for', type=float, default=0,
                        help='Polling budget between tasks; a running task can exceed it')
    worker.add_argument('--crash', choices=['none', 'after-claim', 'inside-effect', 'after-effect', 'after-checkpoint'], default='none')
    worker.add_argument('--failure', choices=['none', 'transient', 'permanent'], default='none')
    for command in ('inspect', 'cancel', 'compensate'):
        sub.add_parser(command).add_argument('task')
    args = parser.parse_args()
    q = Queue(args.db)
    try:
        if args.command == 'enqueue':
            print(json.dumps({'inserted': q.enqueue(args.task, args.steps, args.delay,
                args.max_attempts, args.total_timeout, args.attempt_timeout)}))
        elif args.command == 'worker':
            if not math.isfinite(args.run_for) or args.run_for < 0:
                parser.error('run-for must be finite and nonnegative')
            end = time.monotonic() + args.run_for
            count = 0
            while True:
                count += bool(work_once(q, args.lease, args.crash, args.failure))
                if time.monotonic() >= end:
                    break
                time.sleep(0.02)
            print(json.dumps({'attempts_handled': count}))
        elif args.command == 'inspect':
            print(json.dumps(q.inspect(args.task), indent=2))
        elif args.command == 'cancel':
            print(json.dumps({'cancelled': q.cancel(args.task)}))
        else:
            q.compensate(args.task)
            print(json.dumps({'compensated': args.task}))
    finally:
        q.close()


if __name__ == '__main__':
    main()
