"""Train an original synthetic classifier, export ONNX and measure real inference."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import resource
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker(model, dataset, output):
    import numpy as np
    import onnx
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    start = time.perf_counter_ns()
    session = ort.InferenceSession(str(model), opts, providers=['CPUExecutionProvider'])
    load_ms = (time.perf_counter_ns() - start) / 1e6
    data = np.load(dataset)
    x, y = data['x_test'], data['y_test']
    assert session.get_inputs()[0].name == 'features'
    assert session.get_inputs()[0].shape == [1, 16]
    assert session.get_outputs()[0].shape == [1, 3]
    for i in range(100):
        session.run(['logits'], {'features': x[i % len(x):i % len(x)+1]})
    rows, predictions, logits = [], [], []
    # Request construction and CSV writes are outside the timed region.
    for repeat in range(5):
        for i in range(len(x)):
            request = {'features': x[i:i+1]}
            start = time.perf_counter_ns()
            result = session.run(['logits'], request)[0]
            ns = time.perf_counter_ns() - start
            assert result.shape == (1, 3) and np.isfinite(result).all()
            pred = int(result.argmax())
            rows.append((repeat, i, ns, int(y[i]), pred))
            if repeat == 0:
                predictions.append(pred)
                logits.append(result[0])
    with (output / (model.stem + '-requests.csv')).open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['repeat', 'sample', 'inference_ns', 'label', 'prediction'])
        writer.writerows(rows)
    np.save(output / (model.stem + '-logits.npy'), np.array(logits))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if sys.platform == 'darwin' else peak * 1024
    # Operator/provider proof uses a separate profiling session, not timed calls.
    opts.enable_profiling = True
    opts.profile_file_prefix = str(output / (model.stem + '-profile'))
    profile_session = ort.InferenceSession(str(model), opts, providers=['CPUExecutionProvider'])
    profile_session.run(['logits'], {'features': x[:1]})
    profile_file = Path(profile_session.end_profiling())
    events = json.loads(profile_file.read_text())
    kernels = sorted({(e['args'].get('op_name'), e['args'].get('provider'))
                      for e in events if e.get('args', {}).get('provider')})
    values = np.array([r[2] for r in rows]) / 1000
    graph = onnx.load(model)
    result = {'sha256': sha(model), 'bytes': model.stat().st_size,
              'accuracy': float(np.mean(np.array(predictions) == y)),
              'median_us': float(np.median(values)), 'p95_us': float(np.percentile(values, 95)),
              'load_ms': load_ms, 'process_peak_rss_bytes': peak_bytes,
              'graph_ops': sorted({node.op_type for node in graph.graph.node}),
              'executed_kernels': kernels, 'providers': session.get_providers(),
              'requests': len(rows), 'warmup': 100, 'threads': 1,
              'input': {'features': {'dtype': 'float32', 'shape': [1, 16]}},
              'output': {'logits': {'dtype': 'float32', 'shape': [1, 3]}}}
    (output / (model.stem + '-metrics.json')).write_text(json.dumps(result, indent=2))


def train_export(output):
    import numpy as np
    import onnx
    from onnx import helper as h, numpy_helper as nh, TensorProto as T
    import onnxruntime as ort
    from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
    def mm(a, b):
        return np.einsum("ik,kj->ij", a, b, optimize=False)

    def data(seed, count):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(count, 16)).astype('float32')
        scores = np.stack([1.4*x[:, 0]+0.8*x[:, 1]*x[:, 2],
                           -1.1*x[:, 0]+x[:, 3], x[:, 4]-0.6*x[:, 1]*x[:, 2]], axis=1)
        return x, scores.argmax(1)
    xt, yt = data(2101, 2048)
    xv, yv = data(2102, 512)
    xe, ye = data(2103, 512)
    np.savez(output / 'data.npz', x_train=xt, y_train=yt, x_validation=xv,
             y_validation=yv, x_test=xe, y_test=ye)
    rng = np.random.default_rng(2104)
    w1 = (rng.normal(size=(16, 32))*0.25).astype('float32')
    b1 = np.zeros(32, dtype='float32')
    w2 = (rng.normal(size=(32, 3))*0.25).astype('float32')
    b2 = np.zeros(3, dtype='float32')
    history = []
    # Fixed schedule. Validation is reported but never used to select a model.
    for epoch in range(300):
        for indices in np.array_split(rng.permutation(len(xt)), 16):
            x, y = xt[indices], yt[indices]
            hidden = np.maximum(mm(x, w1) + b1, 0)
            scores = mm(hidden, w2) + b2
            p = np.exp(scores - scores.max(1, keepdims=True))
            p /= p.sum(1, keepdims=True)
            p[np.arange(len(y)), y] -= 1
            p /= len(y)
            dh = (mm(p, w2.T))*(hidden > 0)
            w2 -= 0.05 * mm(hidden.T, p)
            b2 -= 0.05 * p.sum(0)
            w1 -= 0.05 * mm(x.T, dh)
            b1 -= 0.05 * dh.sum(0)
        if epoch % 25 == 0 or epoch == 299:
            pred = (mm(np.maximum(mm(xv, w1) + b1, 0), w2) + b2).argmax(1)
            history.append({'epoch': epoch+1, 'validation_accuracy': float(np.mean(pred == yv))})
    assert all(np.isfinite(v).all() for v in (w1, b1, w2, b2))
    nodes = [h.make_node('MatMul', ['features', 'w1'], ['mm1']),
             h.make_node('Add', ['mm1', 'b1'], ['a1']), h.make_node('Relu', ['a1'], ['hidden']),
             h.make_node('MatMul', ['hidden', 'w2'], ['mm2']),
             h.make_node('Add', ['mm2', 'b2'], ['logits'])]
    graph = h.make_graph(nodes, 'original_synthetic_classifier',
                         [h.make_tensor_value_info('features', T.FLOAT, [1, 16])],
                         [h.make_tensor_value_info('logits', T.FLOAT, [1, 3])],
                         [nh.from_array(v, n) for n, v in [('w1', w1), ('b1', b1), ('w2', w2), ('b2', b2)]])
    model = h.make_model(graph, opset_imports=[h.make_opsetid('', 17)], ir_version=10,
                         producer_name='leanagentbook-original-numpy-training')
    onnx.checker.check_model(model)
    from onnxruntime.quantization.shape_inference import quant_pre_process
    onnx.save(model, output / 'source.onnx')
    quant_pre_process(str(output / 'source.onnx'), str(output / 'float.onnx'), skip_optimization=True)
    class Reader(CalibrationDataReader):
        def __init__(self):
            self.rows = iter([{'features': row[None, :]} for row in xt[:256]])
        def get_next(self):
            return next(self.rows, None)
    quantize_static(str(output / 'float.onnx'), str(output / 'int8.onnx'), Reader(),
                    quant_format=QuantFormat.QDQ, activation_type=QuantType.QInt8,
                    weight_type=QuantType.QInt8, per_channel=True,
                    op_types_to_quantize=['MatMul'])
    onnx.checker.check_model(onnx.load(output / 'int8.onnx'))
    session = ort.InferenceSession(str(output / 'float.onnx'), providers=['CPUExecutionProvider'])
    exported = np.vstack([session.run(None, {'features': row[None, :]})[0] for row in xv[:32]])
    expected = mm(np.maximum(mm(xv[:32], w1) + b1, 0), w2) + b2
    assert np.allclose(exported, expected, atol=1e-5)
    majority = int(np.bincount(yt).argmax())
    return {'seeds': {'train': 2101, 'validation': 2102, 'test': 2103, 'weights': 2104},
            'split_counts': [2048, 512, 512], 'calibration': 'first 256 training rows only',
            'data_sha256': sha(output / 'data.npz'), 'history': history,
            'baseline': {'strategy': 'training-majority', 'class': majority,
                         'test_accuracy': float(np.mean(ye == majority))},
            'export_numpy_max_abs_error': float(np.max(np.abs(exported-expected)))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--expect-arch')
    args = parser.parse_args()
    if args.expect_arch and platform.machine() != args.expect_arch:
        parser.error('Unexpected machine architecture: ' + platform.machine())
    if args.worker:
        worker(args.worker, args.output / 'data.npz', args.output)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    import numpy as np
    import onnx
    import onnxruntime as ort
    trained = train_export(args.output)
    metrics = {}
    for name in ('float', 'int8'):
        subprocess.run([sys.executable, __file__, '--worker', str(args.output / (name+'.onnx')),
                        '--output', str(args.output)], check=True)
        metrics[name] = json.loads((args.output / (name+'-metrics.json')).read_text())
    assert metrics['float']['accuracy'] >= 0.85
    assert metrics['int8']['accuracy'] >= metrics['float']['accuracy'] - 0.03
    assert 'QuantizeLinear' in metrics['int8']['graph_ops']
    assert all(provider == 'CPUExecutionProvider' for m in metrics.values()
               for _, provider in m['executed_kernels'])
    assert metrics['int8']['executed_kernels']
    soc = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip() if sys.platform == 'darwin' else platform.processor()
    summary = {'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
               'architecture': platform.machine(), 'soc': soc or 'not reported',
               'python': platform.python_version(), 'numpy': np.__version__, 'onnx': onnx.__version__,
               'onnxruntime': ort.__version__, 'training': trained, 'models': metrics,
               'power': {'status': 'not measured', 'watts': None},
               'scope': 'CPU only; synthetic data; no network or physical device actuation'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    write_chart(args.output, summary)
    print(json.dumps(summary, indent=2))


def write_chart(output, summary):
    models = summary['models']
    max_us = max(m['p95_us'] for m in models.values())
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 360" role="img" aria-labelledby="title desc">',
             '<title id="title">CPU ONNX 实测延迟</title><desc id="desc">两组真实推理的中位数和 P95；不是设备性能排名。</desc>',
             '<rect width="1000" height="360" fill="#F6F1E7"/>',
             '<g font-family="PingFang SC,Noto Sans CJK SC,sans-serif" fill="#22312F">',
             '<text x="30" y="44" font-size="25">CPU 单请求延迟 · 微秒 · 越短越快</text>',
             '<text x="30" y="76" font-size="16">每组 2560 次，预热 100 次，单线程；数据见 requests.csv</text>']
    for index, (name, m) in enumerate(models.items()):
        y = 120 + index*95
        parts.append(f'<text x="30" y="{y+20}" font-size="20">{name}</text>')
        for offset, key, color, label in [(0, 'median_us', '#316653', '中位'), (30, 'p95_us', '#B94F2D', 'P95')]:
            width = m[key]/max_us*560
            parts.append(f'<rect x="130" y="{y+offset}" width="{width:.1f}" height="20" fill="{color}"/>')
            parts.append(f'<text x="{145+width:.1f}" y="{y+offset+16}" font-size="16">{label} {m[key]:.3f} μs</text>')
    parts.append('<text x="30" y="335" font-size="16">小模型中量化开销可能超过收益；功耗未测，不能从延迟推算。</text></g></svg>')
    (output / 'latency.svg').write_text('\n'.join(parts))


if __name__ == '__main__':
    main()
