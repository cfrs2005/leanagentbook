"""Run actual HTTP ingestion, durable queue replay and human inspection approval."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import socket
import time

from platform_app import ROOT, connect, envelope, stage, sync, server, process, call, render, KNOWLEDGE_VERSION


def run(output, model=None):
    output.mkdir(parents=True, exist_ok=False)
    edge, cloud = output / 'edge.sqlite', output / 'cloud.sqlite'
    cases = [('normal', 'normal'), ('abnormal', 'abnormal'), ('missing', 'insufficient_data')]
    for case, _ in cases:
        stage(edge, envelope(case, case))
    # Bound but not listening: a real loopback connection failure without external traffic.
    with socket.socket() as unavailable:
        unavailable.bind(('127.0.0.1', 0))
        offline = sync(edge, f'http://127.0.0.1:{unavailable.getsockname()[1]}', 'demo-device-a')
    start = time.perf_counter()
    with server(cloud) as url:
        lost = sync(edge, url, 'demo-device-a', lose_ack=True)
        recovered = sync(edge, url, 'demo-device-a')
        while process(cloud, model=model):
            pass
        status, listing = call(url, '/reports', 'demo-viewer-a')
        assert status == 200
        states = {job['id'].rsplit(':', 1)[-1]: job['report']['status'] for job in listing['jobs']}
        assert states == dict(cases)
        abnormal = next(job for job in listing['jobs'] if job['report']['status'] == 'abnormal')
        approval = {'id': abnormal['id'], 'report_hash': abnormal['report_hash'], 'action': 'create_inspection_record'}
        denied = call(url, '/approve-inspection', 'demo-viewer-a', approval)[0]
        approved = call(url, '/approve-inspection', 'demo-approver-a', approval)
        duplicate = call(url, '/approve-inspection', 'demo-approver-a', approval)
        assert denied == 403 and approved[0] == duplicate[0] == 200 and duplicate[1]['duplicate']
        page = render(cloud)
        listing = call(url, '/reports', 'demo-viewer-a')[1]
    with closing(connect(cloud)) as db:
        audit = [dict(sequence=n, kind=k, job_id=j, tenant=t, detail=json.loads(d))
                 for n,k,j,t,d in db.execute('SELECT * FROM audit ORDER BY sequence')]
        job_count = db.execute('SELECT count(*) FROM jobs').fetchone()[0]
    result = {'schema': 'robot-platform-demo-v1', 'synthetic': True,
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'offline_attempt': offline, 'simulated_ack_loss': lost, 'recovered_sync': recovered,
              'expected': dict(cases), 'actual': states, 'correct_cases': sum(states[k] == v for k,v in cases),
              'case_count': len(cases), 'unique_jobs': job_count, 'approval_denied_status': denied,
              'approval': approved, 'duplicate_approval': duplicate, 'reports': listing, 'audit': audit,
              'knowledge_version': KNOWLEDGE_VERSION, 'wall_seconds_excluding_model_load': time.perf_counter() - start,
              'model_mode': 'real_local_model' if model else 'extractive_template',
              'scope': 'Local HTTP and SQLite; no robot, cloud host, real identity provider or physical control',
              'source_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ('platform_app.py', 'demo.py', 'model_adapter.py')}}
    (output / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (output / 'report.html').write_text(page)
    print(json.dumps({k: result[k] for k in ['correct_cases', 'case_count', 'unique_jobs', 'model_mode', 'wall_seconds_excluding_model_load']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to((ROOT / 'results').resolve()):
        parser.error('Published evidence is read-only; choose /tmp or output/')
    adapter = None
    if args.model_dir:
        from model_adapter import LocalDraftModel
        adapter = LocalDraftModel(args.model_dir)
    run(args.output, adapter)
