"""Synthetic receiver in a separate SQLite database, not an HTTP service.

No transaction spans the client and receiver. A crash after the receiver commits
leaves the client uncertain; only receiver-side deduplication closes that gap.
"""
import argparse
import json
import os
import sqlite3
import uuid


def deliver(client_path, receiver_path, operation, keyed=True, crash=False):
    with sqlite3.connect(client_path) as client:
        client.execute('CREATE TABLE IF NOT EXISTS receipts(operation TEXT PRIMARY KEY)')
        if client.execute('SELECT 1 FROM receipts WHERE operation=?', (operation,)).fetchone():
            return 'already_recorded'
    with sqlite3.connect(receiver_path) as receiver:
        receiver.execute('PRAGMA synchronous=FULL')
        receiver.execute('CREATE TABLE IF NOT EXISTS charges(operation TEXT PRIMARY KEY, amount INTEGER NOT NULL)')
        # The receiver owns the key and mutation in the same transaction.
        key = operation if keyed else uuid.uuid4().hex
        receiver.execute('INSERT OR IGNORE INTO charges VALUES(?,10)', (key,))
    if crash:
        os._exit(74)
    with sqlite3.connect(client_path) as client:
        client.execute('INSERT OR IGNORE INTO receipts VALUES(?)', (operation,))
    return 'recorded'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', required=True)
    parser.add_argument('--receiver', required=True)
    parser.add_argument('--operation', default='invoice-001:charge:v1')
    parser.add_argument('--unkeyed', action='store_true')
    parser.add_argument('--crash', action='store_true')
    args = parser.parse_args()
    state = deliver(args.client, args.receiver, args.operation, not args.unkeyed, args.crash)
    with sqlite3.connect(args.receiver) as receiver:
        count, total = receiver.execute('SELECT COUNT(*),COALESCE(SUM(amount),0) FROM charges').fetchone()
    print(json.dumps({'state': state, 'charges': count, 'total': total}))


if __name__ == '__main__':
    main()
