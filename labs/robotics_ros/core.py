"""Dependency-free time alignment and fixture contract."""
NS = 1_000_000_000
BASE = 1_700_000_000 * NS
RATES = {'/lidar': 10, '/camera': 10, '/imu': 50, '/encoder': 20, '/motor': 20, '/battery': 2}
OFFSETS = {topic: (70_000_000 if topic == '/camera' else 0) for topic in RATES}


def validate_manifest(manifest):
    if manifest.get('schema') != 1 or manifest.get('typestore') != 'ROS2_HUMBLE':
        raise ValueError('Unsupported fixture schema or message typestore')
    if manifest.get('bag_version') != 8:
        raise ValueError('Unsupported bag metadata version')


def missing_sequences(rows, expected):
    return sorted(set(range(expected)) - {r['seq'] for r in rows})


def align(cameras, imus, correction_ns=0, tolerance_ns=10_000_000):
    """Return matches and gaps; never fabricate a missing sample."""
    result = []
    for camera in cameras:
        target = camera['header_ns'] - correction_ns
        candidate = min(imus, key=lambda r: (abs(r['header_ns'] - target), r['header_ns'])) if imus else None
        if candidate is None or abs(candidate['header_ns'] - target) > tolerance_ns:
            result.append({'camera_seq': camera['seq'], 'imu_seq': None, 'true_error_ns': None})
        else:
            result.append({'camera_seq': camera['seq'], 'imu_seq': candidate['seq'],
                           'true_error_ns': abs(camera['true_ns'] - candidate['true_ns'])})
    return result


def thin(rows, bin_ns=100_000_000):
    """Keep first, minimum and maximum in each time bin."""
    bins = {}
    for row in rows:
        bins.setdefault(row['true_ns'] // bin_ns, []).append(row)
    selected = {}
    for group in bins.values():
        for row in (group[0], min(group, key=lambda r: r['value']), max(group, key=lambda r: r['value'])):
            selected[row['seq']] = row
    return sorted(selected.values(), key=lambda r: r['true_ns'])
