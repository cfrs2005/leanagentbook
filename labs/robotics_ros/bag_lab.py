"""Generate and read real ROS2 SQLite/CDR bags; no ROS runtime or hardware."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
from core import BASE, NS, RATES, OFFSETS, align, thin, missing_sequences, validate_manifest

POINT = 'geometry_msgs/msg/PointStamped'
STRING = 'std_msgs/msg/String'


def dependencies():
    from rosbags.rosbag2 import Reader, Writer
    from rosbags.typesys import Stores, get_typestore
    return Reader, Writer, get_typestore(Stores.ROS2_HUMBLE)


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def generate(root):
    _, Writer, store = dependencies()
    manifest = {'schema': 1, 'synthetic': True, 'bag_version': 8, 'typestore': 'ROS2_HUMBLE',
                'software': 'synthetic-controller-1.2.0', 'config': {'motor_threshold_a': 8},
                'duration_s': 4, 'offsets_ns': OFFSETS, 'rates_hz': RATES,
                'missing_imu_sequences': list(range(100, 110)), 'anomaly_interval_s': [2, 2.4]}
    manifest['config_sha256'] = hashlib.sha256(json.dumps(manifest['config'], sort_keys=True).encode()).hexdigest()
    types = store.types
    events = []
    truth = []
    for topic, rate in RATES.items():
        for seq in range(4 * rate):
            if topic == '/imu' and 100 <= seq < 110:
                continue
            true_ns = BASE + seq * NS // rate
            stamp = true_ns + OFFSETS[topic]
            value = 12.0 if topic == '/motor' and 2 * NS <= true_ns - BASE < 2.4 * NS else float(seq % 7)
            msg = types[POINT](types['std_msgs/msg/Header'](types['builtin_interfaces/msg/Time'](stamp // NS, stamp % NS), topic[1:]),
                               types['geometry_msgs/msg/Point'](value, float(seq), 0.0))
            record_ns = true_ns + 5_000_000 + (seq % 3) * 1_000_000
            events.append((record_ns, topic, POINT, store.serialize_cdr(msg, POINT)))
            truth.append({'topic': topic, 'seq': seq, 'true_ns': true_ns})
    log = {'event_id': 'motor-overcurrent-001', 'true_ns': BASE + 2 * NS,
           'software': manifest['software'], 'config_sha256': manifest['config_sha256'], 'message': 'Synthetic overcurrent'}
    for topic, payload, timestamp in [('/context', manifest, BASE), ('/events', log, BASE + 2 * NS + 8_000_000)]:
        events.append((timestamp, topic, STRING, store.serialize_cdr(types[STRING](json.dumps(payload, sort_keys=True)), STRING)))
    with Writer(root / 'source_bag', version=8) as writer:
        connections = {topic: writer.add_connection(topic, POINT if topic in RATES else STRING, typestore=store)
                       for topic in [*RATES, '/context', '/events']}
        for timestamp, topic, _, data in sorted(events):
            writer.write(connections[topic], timestamp, data)
    dump(root / 'manifest.json', manifest)
    dump(root / 'truth.json', truth)


def read_rows(path, truth):
    Reader, _, store = dependencies()
    rows, context = [], []
    with Reader(path) as reader:
        for conn, timestamp, raw in reader.messages():
            msg = store.deserialize_cdr(raw, conn.msgtype)
            if conn.msgtype == POINT:
                seq = int(msg.point.y)
                rows.append({'topic': conn.topic, 'seq': seq, 'record_ns': timestamp,
                             'header_ns': msg.header.stamp.sec * NS + msg.header.stamp.nanosec,
                             'true_ns': truth[(conn.topic, seq)], 'value': msg.point.x})
            else:
                context.append({'topic': conn.topic, 'record_ns': timestamp, 'payload': json.loads(msg.data)})
    return rows, context


def extract(source, target, start, end):
    Reader, Writer, store = dependencies()
    with Reader(source) as reader, Writer(target, version=8) as writer:
        connections = {c.id: writer.add_connection(c.topic, c.msgtype, typestore=store) for c in reader.connections}
        for conn, timestamp, raw in reader.messages():
            # Preserve configuration context even when it precedes the event window.
            if start <= timestamp < end or conn.topic == '/context':
                writer.write(connections[conn.id], timestamp, raw)


def analyze(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    validate_manifest(manifest)
    truth = {(r['topic'], r['seq']): r['true_ns'] for r in json.loads((root / 'truth.json').read_text())}
    rows, context = read_rows(root / 'source_bag', truth)
    groups = {topic: [r for r in rows if r['topic'] == topic] for topic in RATES}
    stats = {}
    for topic, group in groups.items():
        stamps = [r['header_ns'] for r in group]
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        stats[topic] = {'count': len(group), 'expected': 4 * RATES[topic],
                        'missing_sequences': missing_sequences(group, 4 * RATES[topic]),
                        'median_period_ms': statistics.median(gaps) / 1e6,
                        'max_gap_ms': max(gaps) / 1e6,
                        'observed_hz': (len(group) - 1) * NS / (stamps[-1] - stamps[0]),
                        'record_minus_header_ms_range': [min(r['record_ns'] - r['header_ns'] for r in group) / 1e6,
                                                       max(r['record_ns'] - r['header_ns'] for r in group) / 1e6]}
    for item in context:
        stats[item['topic']] = {'count': 1, 'expected': 1, 'kind': 'nonperiodic String'}
    before = align(groups['/camera'], groups['/imu'])
    after = align(groups['/camera'], groups['/imu'], OFFSETS['/camera'])
    extract(root / 'source_bag', root / 'event_bag', BASE + 1_800_000_000, BASE + 2_600_000_000)
    event_rows, event_context = read_rows(root / 'event_bag', truth)
    anomalies = [r for r in event_rows if r['topic'] == '/motor' and r['value'] > manifest['config']['motor_threshold_a']]
    report = {'synthetic': True, 'python': platform.python_version(), 'rosbags': importlib.metadata.version('rosbags'),
              'topics': stats, 'alignment_before': before, 'alignment_after': after,
              'event': {'record_window_relative_s': [1.8, 2.6], 'sensor_rows': len(event_rows),
                        'context_rows': len(event_context), 'anomalous_motor_sequences': [r['seq'] for r in anomalies]},
              'thinned_motor_rows': len(thin(groups['/motor'])),
              'scope': 'Offline CDR/SQLite readback only; no DDS, ros2 bag play or physical device validation'}
    dump(root / 'report.json', report)
    dump(root / 'context.json', context)
    with (root / 'timeseries.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    dump(root / 'thinned_motor.json', thin(groups['/motor']))
    dump(root / 'checksums.json', {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'checksums.json'})
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    generate(args.out)
    report = analyze(args.out)
    print(json.dumps({'sensor_rows': sum(x['count'] for t, x in report['topics'].items() if t in RATES),
                      'event': report['event'], 'rosbags': report['rosbags']}, indent=2))


if __name__ == '__main__':
    main()
