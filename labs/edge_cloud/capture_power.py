"""Measure reported host power while running the pinned ONNX models on macOS."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import threading
import time

FIELDS = ('cpu_power', 'gpu_power', 'chip_power', 'sys_power')


def run(monitor, models, output):
    import numpy as np
    import onnxruntime as ort
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('This measurement requires an Apple Silicon host')
    if output.exists():
        raise FileExistsError('Choose a new output directory')
    version = subprocess.check_output([str(monitor), '--version'], text=True).strip()
    if version != 'macmon 0.12.0':
        raise ValueError('Use the documented macmon 0.12.0 release')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    sessions = {name: ort.InferenceSession(str(models / (name+'.onnx')), sess_options=options,
                                          providers=['CPUExecutionProvider']) for name in ('float', 'int8')}
    data = np.load(models / 'data.npz')
    inputs = data['test_x'] if 'test_x' in data else data['x_test']
    inputs = np.asarray(inputs, dtype=np.float32)
    for session in sessions.values():
        for i in range(100):
            session.run(None, {'features': inputs[i % len(inputs):i % len(inputs)+1]})
    phases = []
    for name in ('baseline_before', 'float', 'int8', 'baseline_after'):
        stop, count, errors = threading.Event(), [0], []
        def load():
            try:
                while not stop.is_set():
                    index = count[0] % len(inputs)
                    result = sessions[name].run(None, {'features': inputs[index:index+1]})[0]
                    if not np.isfinite(result).all():
                        raise ValueError('Nonfinite inference result')
                    count[0] += 1
            except Exception as exc:
                errors.append(type(exc).__name__)
        worker = threading.Thread(target=load) if name in sessions else None
        started = time.perf_counter()
        started_utc = datetime.now(timezone.utc).isoformat()
        if worker:
            worker.start()
        try:
            raw = subprocess.check_output([str(monitor), 'pipe', '-s', '20', '-i', '500'],
                                          text=True, timeout=25, stderr=subprocess.PIPE)
        finally:
            stop.set()
            if worker:
                worker.join(timeout=5)
                if worker.is_alive():
                    raise RuntimeError('Inference thread failed to stop')
        elapsed = time.perf_counter() - started
        if errors:
            raise RuntimeError('Inference failed: '+','.join(errors))
        samples = [json.loads(line) for line in raw.splitlines() if line]
        if len(samples) != 20:
            raise ValueError('Incomplete monitoring window')
        for sample in samples:
            if any(type(sample.get(field)) not in (int, float) or not math.isfinite(sample[field])
                   or sample[field] < 0 for field in FIELDS):
                raise ValueError('Invalid or unavailable power reading')
        if len({s['cpu_power'] for s in samples}) < 2 or max(s['cpu_power'] for s in samples) <= 0:
            raise ValueError('CPU counter did not show live readings')
        selected = [{**{field: sample[field] for field in FIELDS}, 'timestamp': sample['timestamp'],
                     'cpu_temp_c': sample['temp']['cpu_temp_avg'],
                     'gpu_temp_c': sample['temp']['gpu_temp_avg']} for sample in samples]
        stats = {field: {'mean_w': statistics.mean(s[field] for s in samples),
                         'min_w': min(s[field] for s in samples), 'max_w': max(s[field] for s in samples)}
                 for field in FIELDS}
        phases.append({'phase': name, 'started_utc': started_utc, 'wall_seconds': elapsed,
                       'sample_count': len(samples), 'interval_ms': 500,
                       'inference_count': count[0], 'samples': selected, 'statistics': stats})
        print(name, count[0], round(stats['cpu_power']['mean_w'], 3), flush=True)
    summary = {'schema': 'host-power-observation-v1', 'monitor_version': version,
               'monitor_sha256': hashlib.sha256(monitor.read_bytes()).hexdigest(),
               'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                               'soc': subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip(),
                               'onnxruntime': ort.__version__, 'numpy': np.__version__},
               'models': {name: {'sha256': hashlib.sha256((models/(name+'.onnx')).read_bytes()).hexdigest(),
                                  'providers': sessions[name].get_providers()} for name in sessions},
               'input_sha256': hashlib.sha256((models/'data.npz').read_bytes()).hexdigest(),
               'load': 'Batch 1, one ORT intra/inter-op thread, continuous inference plus finite-output check; 100 warmup requests per model before measurement',
               'phases': phases,
               'scope': 'System-reported host CPU/chip/system power in watts, not process-exclusive energy and not calibrated wall-plug measurements. Background applications remain running. No energy-per-inference or causal speed/power claim.',
               'method': '20 samples at 500 ms per phase; before/float/int8/after fixed order, one pass. Baseline has no lab inference but includes background workload and monitoring.'}
    output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.monitor, args.models, args.output)
