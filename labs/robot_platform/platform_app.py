"""Local synthetic edge/cloud prototype; never sends robot control commands."""
import argparse
from contextlib import closing, contextmanager
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'robot_diagnosis'))
from detector import analyze

SCHEMA = 'robot-event-v1'
POLICY = 'readonly-inspection-v1'
OPENER = build_opener(ProxyHandler({}))
# Fixed teaching credentials; not production authentication or secrets.
IDENTITIES = {'demo-device-a': ('tenant-a', 'device', 'robot-a'),
              'demo-device-b': ('tenant-b', 'device', 'robot-b'),
              'demo-viewer-a': ('tenant-a', 'viewer', None),
              'demo-approver-a': ('tenant-a', 'approver', None),
              'demo-viewer-b': ('tenant-b', 'viewer', None)}
KNOWLEDGE = [
    {'id': 'current', 'signal': 'motor_current_a', 'text': '电流超限支持检查负载与传感器；不能直接确认电机损坏。'},
    {'id': 'vibration', 'signal': 'vibration_mm_s', 'text': '振动教学标量没有频带定义；现场需先核对采样、单位与安装。'},
    {'id': 'missing', 'signal': 'missing', 'text': '缺失样本不能当作正常；先检查采集链路并补充记录。'},
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


KNOWLEDGE_VERSION = digest(KNOWLEDGE)


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,tenant TEXT,device TEXT,payload_hash TEXT,payload TEXT,status TEXT,
      report TEXT,report_hash TEXT);
    CREATE TABLE IF NOT EXISTS inspections (job_id TEXT PRIMARY KEY,report_hash TEXT,actor TEXT,action TEXT);
    CREATE TABLE IF NOT EXISTS audit (sequence INTEGER PRIMARY KEY,kind TEXT,job_id TEXT,tenant TEXT,detail TEXT);
    CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY,payload_hash TEXT,payload TEXT,sent INTEGER DEFAULT 0);
    ''')
    return db


def audit(db, kind, job, tenant, detail):
    db.execute('INSERT INTO audit(kind,job_id,tenant,detail) VALUES (?,?,?,?)',
               (kind, job, tenant, canonical(detail)))


def envelope(case, event_id='event-1', tenant='tenant-a', device='robot-a'):
    raw = (ROOT.parent / 'robot_diagnosis' / 'data' / f'{case}.csv').read_text()
    return dict(schema=SCHEMA, event_id=event_id, tenant=tenant, device=device, csv=raw,
                software_version='synthetic-fw-1', config_version='synthetic-config-1',
                knowledge_version=KNOWLEDGE_VERSION, policy_version=POLICY,
                synthetic=True, image_id='motor-schematic-v1')


def validate_payload(payload):
    fields = set(envelope('normal'))
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError('Invalid payload fields')
    if (payload['schema'] != SCHEMA or payload['synthetic'] is not True
            or payload['knowledge_version'] != KNOWLEDGE_VERSION or payload['policy_version'] != POLICY
            or payload['software_version'] != 'synthetic-fw-1' or payload['config_version'] != 'synthetic-config-1'
            or payload['image_id'] != 'motor-schematic-v1'):
        raise ValueError('Unsupported data or version')
    if any(not isinstance(payload[k], str) or not 1 <= len(payload[k]) <= 80
           or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in payload[k])
           for k in ('event_id', 'tenant', 'device')):
        raise ValueError('Invalid identity field')
    if not isinstance(payload['csv'], str) or not 1 <= len(payload['csv'].encode()) <= 16384:
        raise ValueError('CSV exceeds bounded input contract')
    # Reuse the actual detector contract; a local temporary file is never a client path.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.csv'
        path.write_text(payload['csv'])
        return analyze(path)


def stage(database, payload):
    validate_payload(payload)
    with closing(connect(database)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        key = f"{payload['tenant']}:{payload['device']}:{payload['event_id']}"
        old = db.execute('SELECT payload_hash FROM outbox WHERE id=?', (key,)).fetchone()
        if old and old[0] != digest(payload):
            raise ValueError('Conflicting local event ID')
        db.execute('INSERT OR IGNORE INTO outbox(id,payload_hash,payload) VALUES (?,?,?)',
                   (key, digest(payload), canonical(payload)))
        return key


def call(url, path, token, payload=None):
    body = None if payload is None else canonical(payload).encode()
    req = Request(url + path, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with OPENER.open(req, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def sync(database, url, token, lose_ack=False):
    sent = 0
    with closing(connect(database)) as db:
        rows = db.execute('SELECT id,payload FROM outbox WHERE sent=0 ORDER BY id').fetchall()
        for key, payload in rows:
            try:
                status, _ = call(url, '/ingest', token, json.loads(payload))
            except (URLError, TimeoutError, OSError):
                return {'sent': sent, 'offline': True}
            if status not in (200, 201):
                return {'sent': sent, 'offline': False, 'error_status': status}
            if lose_ack:
                return {'sent': sent, 'offline': False, 'ack_lost': True}
            with db:
                db.execute('UPDATE outbox SET sent=1 WHERE id=?', (key,))
            sent += 1
    return {'sent': sent, 'offline': False}


def make_report(payload, model=None):
    started = time.perf_counter()
    diagnosis = validate_payload(payload)
    signals = {e['field'] for event in diagnosis['events'] for e in event['evidence'] if len(e['threshold_hits']) >= 2}
    if any(event['missing'] for event in diagnosis['events']):
        signals.add('missing')
    references = [dict(item, source_version=KNOWLEDGE_VERSION) for item in KNOWLEDGE if item['signal'] in signals]
    status = ('abnormal' if any(e['status'] == 'abnormal' for e in diagnosis['events']) else
              'insufficient_data' if any(e['status'] == 'insufficient_data' for e in diagnosis['events']) else 'normal')
    image_path = ROOT / 'fixtures' / 'motor-schematic.svg'
    picture = {'id': payload['image_id'], 'sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
               'source': 'original synthetic diagram; not a field photograph', 'model_recognition': False}
    report = dict(status=status, diagnosis=diagnosis, references=references, picture=picture,
                  review_required=True, root_cause_confirmed=False, automatic_control=False,
                  trace=[{'step': 1, 'tool': 'analyze_synthetic_csv'},
                         {'step': 2, 'tool': 'retrieve_by_observed_signal'},
                         {'step': 3, 'tool': 'attach_hashed_synthetic_diagram'}],
                  versions={k: payload[k] for k in ('software_version', 'config_version', 'policy_version', 'knowledge_version')})
    # Language output cannot change observed status, references, approval or control policy.
    report['language'] = {'mode': 'extractive_template', 'text': '请人工核对证据；当前结果不是根因确认。', 'verified': True}
    if model is not None:
        try:
            report['language'] = model(status, references)
        except Exception as exc:
            report['language']['fallback_reason'] = type(exc).__name__
    report['trace'].append({'step': 4, 'tool': 'language_draft', 'mode': report['language']['mode']})
    report['measurement'] = {'processing_seconds': time.perf_counter() - started,
                             'input_bytes': len(payload['csv'].encode()), 'external_api_cost': 0,
                             'cost_note': 'No paid API; local compute, power and human cost not priced'}
    return report


def process(database, crash=None, model=None):
    with closing(connect(database)) as db:
        row = db.execute("SELECT id,tenant,payload FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
    if not row:
        return None
    key, tenant, payload = row
    report = make_report(json.loads(payload), model)
    with closing(connect(database)) as db, db:
        current = db.execute('SELECT status FROM jobs WHERE id=?', (key,)).fetchone()[0]
        if current != 'queued':
            return key  # Another worker already committed; read-only calculation can repeat.
        changed = db.execute("UPDATE jobs SET status='review',report=?,report_hash=? WHERE id=? AND status='queued'",
                             (canonical(report), digest(report), key)).rowcount
        if not changed:
            return key
        audit(db, 'report_ready', key, tenant, {'report_hash': digest(report)})
        if crash == 'before_commit':
            os._exit(71)
    if crash == 'after_commit':
        os._exit(72)
    return key


def dispatch(database, token, path, payload):
    identity = IDENTITIES.get(token)
    if identity is None:
        return 401, {'error': 'unauthenticated'}
    tenant, role, device = identity
    with closing(connect(database)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if path == '/ingest':
            if role != 'device' or payload.get('tenant') != tenant or payload.get('device') != device:
                return 403, {'error': 'device scope denied'}
            validate_payload(payload)
            key = f"{tenant}:{device}:{payload['event_id']}"
            old = db.execute('SELECT payload_hash FROM jobs WHERE id=?', (key,)).fetchone()
            if old:
                return (200, {'id': key, 'duplicate': True}) if old[0] == digest(payload) else (409, {'error': 'event conflict'})
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)',
                       (key, tenant, device, digest(payload), canonical(payload), 'queued'))
            audit(db, 'ingested', key, tenant, {'payload_hash': digest(payload)})
            return 201, {'id': key}
        if path == '/reports':
            if role not in ('viewer', 'approver'):
                return 403, {'error': 'reader role required'}
            rows = db.execute('SELECT id,device,status,report,report_hash FROM jobs WHERE tenant=? ORDER BY id', (tenant,)).fetchall()
            inspections = [dict(job_id=k, report_hash=h, actor=a, action=act) for k,h,a,act in
                           db.execute('SELECT i.* FROM inspections i JOIN jobs j ON j.id=i.job_id WHERE j.tenant=?', (tenant,))]
            return 200, {'tenant': tenant, 'jobs': [dict(id=k, device=d, state=s, report=json.loads(r) if r else None,
                        report_hash=h) for k,d,s,r,h in rows], 'inspections': inspections}
        if path == '/approve-inspection':
            if role != 'approver':
                return 403, {'error': 'approver required'}
            if set(payload) != {'id', 'report_hash', 'action'} or payload['action'] != 'create_inspection_record':
                return 400, {'error': 'only inspection records are allowed'}
            row = db.execute('SELECT tenant,status,report_hash FROM jobs WHERE id=?', (payload['id'],)).fetchone()
            if not row or row[0] != tenant:
                return 404, {'error': 'report not found'}
            if row[1] != 'review' or row[2] != payload['report_hash']:
                return 409, {'error': 'stale or unavailable report'}
            exists = db.execute('SELECT 1 FROM inspections WHERE job_id=?', (payload['id'],)).fetchone()
            if not exists:
                db.execute('INSERT INTO inspections VALUES (?,?,?,?)',
                           (payload['id'], payload['report_hash'], role, payload['action']))
                audit(db, 'inspection_approved', payload['id'], tenant, {'action': payload['action']})
            return 200, {'duplicate': bool(exists), 'automatic_control': False}
        return 404, {'error': 'unknown route'}


def render(database):
    _, data = dispatch(database, 'demo-viewer-a', '/reports', {})
    cards = []
    names = {'normal': '当前规则未发现异常', 'abnormal': '观测异常，待复核',
             'insufficient_data': '数据不足，需补采'}
    for job in data['jobs']:
        report = job['report']
        title = html.escape(job['id'])
        raw = html.escape(json.dumps(job, ensure_ascii=False, indent=2))
        if report:
            status = names[report['status']]
            references = ''.join('<li>' + html.escape(row['text']) + '</li>' for row in report['references'])
            language = html.escape(report['language']['text'])
            cards.append(f'<article><h2>{title}</h2><strong>{status}</strong><ul>{references}</ul>'
                         f'<p>语言建议（须核对）：{language}</p>'
                         '<p>根因尚未确认；不发送机器人控制指令。</p>'
                         f'<details><summary>查看原始证据、版本与耗时</summary><pre>{raw}</pre></details></article>')
        else:
            cards.append(f'<article><h2>{title}</h2><p>等待诊断</p></article>')
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>机器人诊断教学原型</title>'
            '<style>body{max-width:980px;margin:40px auto;padding:0 20px;background:#f8f5ee;color:#233c34;font:16px sans-serif}'
            'article{background:#fffdf8;padding:24px;margin:18px 0;border:1px solid #c9d7cb;border-radius:12px}'
            'h2{font-size:20px}li{margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}'
            'summary{font-weight:bold;cursor:pointer}</style>'
            '<h1>机器人诊断 · 证据与复核</h1><p>教学租户 A · 只读页面 · 全部数据为合成 · 不发送控制指令</p>'
            + ''.join(cards) + f'<p>检查审批记录：{len(data["inspections"])}（演示脚本模拟人员提交）</p></html>')


@contextmanager
def server(database):
    with closing(connect(database)):
        pass
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path == '/':
                return self.reply(200, render(database).encode(), 'text/html; charset=utf-8')
            self.respond({})
        def do_POST(self):
            try:
                self.connection.settimeout(5)
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 32768:
                    raise ValueError('invalid size')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('object required')
                self.respond(body)
            except (ValueError, TypeError, TimeoutError):
                self.reply(400, b'{"error":"invalid request"}')
        def respond(self, body):
            try:
                if self.command == 'GET' and self.path != '/reports':
                    status, result = 405, {'error': 'POST required'}
                else:
                    token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                    status, result = dispatch(database, token, self.path, body)
            except (ValueError, TypeError, KeyError):
                status, result = 400, {'error': 'invalid payload'}
            self.reply(status, canonical(result).encode())
        def reply(self, status, body, content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{http.server_port}'
    finally:
        http.shutdown(); http.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--crash', choices=['before_commit', 'after_commit'])
    args = parser.parse_args()
    if args.serve:
        with server(args.database) as url:
            print(url, flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print(process(args.database, args.crash))
