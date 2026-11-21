"""Synthetic event stream with durable local state and optional real Parquet."""
import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import time


BASE = 1735689600


def generate(path, count=2000):
    records = []
    for i in range(count):
        event = dict(schema_version=1, event_id=f'e{i}', device=f'd{i % 8}',
                     event_time=BASE + i - (120 if i % 97 == 0 else 0), value=i % 100)
        records.append(json.dumps(event, sort_keys=True))
        if i % 101 == 0:
            records.append(records[-1])
        if i % 211 == 0:
            records.append('{bad json')
    path.write_text('\n'.join(records) + '\n', encoding='utf-8')


def decode(raw):
    item = json.loads(raw)
    if not isinstance(item, dict):
        raise ValueError('object required')
    if type(item.get('schema_version')) is not int or item['schema_version'] != 1:
        raise ValueError('unsupported schema_version')
    for key in ('event_id', 'device'):
        if not isinstance(item.get(key), str) or not item[key] or len(item[key]) > 80:
            raise ValueError(f'invalid {key}')
    for key in ('event_time', 'value'):
        if type(item.get(key)) is not int:
            raise ValueError(f'invalid {key}')
    if not 0 <= item['value'] <= 100 or not BASE - 3600 <= item['event_time'] <= BASE + 10**7:
        raise ValueError('out of range')
    # Unknown fields are ignored; a new meaning requires a new schema version.
    return {key: item[key] for key in ('schema_version', 'event_id', 'device', 'event_time', 'value')}


def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1),
        source_hash TEXT, offset INTEGER, max_time INTEGER);
    CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, device TEXT,
        event_time INTEGER, value INTEGER, late INTEGER, payload TEXT);
    CREATE TABLE IF NOT EXISTS quarantine (offset INTEGER PRIMARY KEY, raw TEXT, reason TEXT);
    ''')
    return db


def consume(source, database, crash=None, crash_offset=3):
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    db = connect(database)
    row = db.execute('SELECT source_hash,offset,max_time FROM state').fetchone()
    if row and row[0] != digest:
        db.close()
        raise ValueError('source changed; use a new dataset/database')
    if not row:
        db.execute('INSERT INTO state VALUES (1,?,0,?)', (digest, BASE - 3600))
        db.commit()
    offset, maximum = db.execute('SELECT offset,max_time FROM state').fetchone()
    latencies = []
    started = time.perf_counter()
    try:
        with source.open(encoding='utf-8') as handle:
            for index, raw in enumerate(handle):
                if index < offset:
                    continue
                tick = time.perf_counter()
                with db:
                    try:
                        event = decode(raw)
                        payload = json.dumps(event, sort_keys=True)
                        old = db.execute('SELECT payload FROM events WHERE event_id=?',
                                         (event['event_id'],)).fetchone()
                        if old and old[0] != payload:
                            raise ValueError('conflicting event_id')
                        late = int(event['event_time'] < maximum - 30)
                        db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)',
                                   (event['event_id'], event['device'], event['event_time'],
                                    event['value'], late, payload))
                        maximum = max(maximum, event['event_time'])
                    except (ValueError, TypeError) as exc:
                        db.execute('INSERT OR REPLACE INTO quarantine VALUES (?,?,?)',
                                   (index, raw.rstrip('\n'), str(exc)))
                    if crash == 'before_commit' and index == crash_offset:
                        os._exit(71)
                    db.execute('UPDATE state SET offset=?,max_time=? WHERE id=1', (index + 1, maximum))
                if crash == 'after_commit' and index == crash_offset:
                    os._exit(72)
                latencies.append((time.perf_counter() - tick) * 1000)
        elapsed = time.perf_counter() - started
        ordered = sorted(latencies)
        return dict(processed_lines=len(latencies), seconds=elapsed,
                    lines_per_second=len(latencies) / elapsed,
                    commit_latency_ms_p50=ordered[len(ordered) // 2] if ordered else 0,
                    commit_latency_ms_p95=ordered[min(len(ordered)-1, int(len(ordered)*.95))] if ordered else 0)
    finally:
        db.close()


def aggregate(rows):
    result = defaultdict(lambda: [0, 0])
    for row in rows:
        key = f"{row['device']}:{row['event_time'] // 60}"
        result[key][0] += 1
        result[key][1] += row['value']
    return dict(sorted(result.items()))


def oracle(source):
    unique, bad = {}, 0
    for raw in source.read_text().splitlines():
        try:
            item = decode(raw)
            if item['event_id'] in unique and unique[item['event_id']] != item:
                raise ValueError('conflict')
            unique[item['event_id']] = item
        except (ValueError, TypeError):
            bad += 1
    return list(unique.values()), bad


def snapshot(database):
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT event_id,device,event_time,value,late FROM events ORDER BY event_id')]
        offset = db.execute('SELECT offset FROM state').fetchone()[0]
        bad = db.execute('SELECT count(*) FROM quarantine').fetchone()[0]
    return rows, offset, bad


def export_parquet(rows, path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = pa.schema([('event_id', pa.string()), ('device', pa.string()),
                        ('event_time', pa.int64()), ('value', pa.int64()), ('late', pa.int64())])
    table = pa.Table.from_pylist(rows, schema=schema)
    started = time.perf_counter()
    temp = path.with_suffix('.tmp')
    pq.write_table(table, temp, compression='zstd', row_group_size=512)
    with temp.open('rb') as handle:
        os.fsync(handle.fileno())
    os.replace(temp, path)
    write_seconds = time.perf_counter() - started
    started = time.perf_counter()
    readback = pq.read_table(path).to_pylist()
    read_seconds = time.perf_counter() - started
    assert rows == readback
    return dict(pyarrow=pa.__version__, parquet_bytes=path.stat().st_size,
                parquet_write_seconds=write_seconds, parquet_read_seconds=read_seconds,
                parquet_rows=len(readback), parquet_aggregate=aggregate(readback))


def run(output, count, parquet):
    output.mkdir(parents=True, exist_ok=False)
    source, database = output / 'events.jsonl', output / 'state.sqlite'
    generate(source, count)
    metrics = consume(source, database)
    rows, offset, bad = snapshot(database)
    expected, expected_bad = oracle(source)
    assert aggregate(rows) == aggregate(expected) and len(rows) == len(expected) and bad == expected_bad
    assert offset == len(source.read_text().splitlines())
    metrics.update(unique_events=len(rows), quarantined=bad, offset=offset,
                   late_events=sum(row['late'] for row in rows), source_bytes=source.stat().st_size,
                   sqlite_bytes=database.stat().st_size, aggregate=aggregate(rows))
    metrics['resume'] = consume(source, database)
    # Reset only the cursor; deduplication must survive a full replay.
    with closing(sqlite3.connect(database)) as db:
        with db:
            db.execute('UPDATE state SET offset=0')
    metrics['replay'] = consume(source, database)
    assert snapshot(database)[0] == rows
    if parquet:
        metrics.update(export_parquet(rows, output / 'events.parquet'))
    try:
        cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        cpu = platform.processor() or 'unknown'
    metrics['environment'] = dict(python=platform.python_version(), system=platform.system(),
                                  release=platform.release(), machine=platform.machine(), cpu=cpu,
                                  logical_cpus=os.cpu_count(), sqlite=sqlite3.sqlite_version)
    metrics['lineage'] = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                              code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              schema_version=1, generator='deterministic synthetic v1', count=count,
                              timing='consume: file iteration + decode + per-line FULL SQLite commit; excludes hash and DB setup',
                              latency='per-line decode through commit; excludes queue wait and event age',
                              parquet_timing='write includes fsync and replace, excludes Arrow table construction; read includes to_pylist')
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: value for key, value in metrics.items() if key not in ('aggregate', 'parquet_aggregate')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--count', type=int, default=2000)
    parser.add_argument('--parquet', action='store_true')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--crash', choices=['before_commit', 'after_commit'])
    args = parser.parse_args()
    if args.source:
        consume(args.source, args.database, args.crash)
    else:
        if args.output is None or args.count < 1:
            parser.error('--output and positive --count required')
        run(args.output, args.count, args.parquet)
