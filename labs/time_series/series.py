"""Causal features and temporal evaluation for synthetic industrial telemetry."""
import math
import random
import statistics

CHANNELS = ('current_a', 'temperature_c', 'speed_rpm')
SPLITS = {'train': (0, 5400), 'dev': (5400, 8400), 'test': (8400, 12000)}
WINDOW, STRIDE = 60, 15
EVENTS = [dict(id=f'fault-{i + 1}', onset=start, end=start + 120, kind=kind)
          for i, (start, kind) in enumerate([
              (1000, 'load'), (2200, 'heat'), (3800, 'load'), (4900, 'heat'),
              (5900, 'load'), (7100, 'heat'), (7900, 'load'),
              (9100, 'load'), (10100, 'heat'), (11200, 'speed_loss')])]


def generate(seed=41):
    rng = random.Random(seed)
    rows = []
    for t in range(12000):
        load = .6 * math.sin(2 * math.pi * t / 600)
        current = 5 + load + rng.gauss(0, .12)
        temperature = 40 + .8 * math.sin(2 * math.pi * t / 1200) + t / 12000 + rng.gauss(0, .08)
        speed = 1200 - 12 * load + rng.gauss(0, 2)
        # A short benign operating change is not labeled as a fault.
        if 300 <= t % 1800 < 350:
            current += .7
            speed -= 15
        for event in EVENTS:
            if event['onset'] - 40 <= t < event['end']:
                strength = min(1, (t - event['onset'] + 40) / 40)
                if event['kind'] == 'load':
                    current += 1.8 * strength
                    speed -= 35 * strength
                elif event['kind'] == 'heat':
                    temperature += 4 * strength
                else:
                    speed -= 110 * strength
                    current += .25 * strength
        values = [current, temperature, speed]
        if t % 877 == 0:
            values[0] += 2  # Isolated measurement impulse, not a machine fault.
        for i in range(3):
            if rng.random() < .003 or (i == 1 and 8500 <= t < 8510):
                values[i] = None
        label = int(any(e['onset'] <= t < e['end'] for e in EVENTS))
        rows.append(dict(t=t, label=label, **dict(zip(CHANNELS, values))))
    return rows


def validate(rows):
    for i, row in enumerate(rows):
        if type(row['t']) is not int or (i and row['t'] != rows[i - 1]['t'] + 1):
            raise ValueError('Expected strictly increasing regular one-second timestamps')
        if type(row['label']) is not int or row['label'] not in (0, 1):
            raise ValueError('Invalid binary label')
        for key in CHANNELS:
            value = row[key]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError('Nonfinite or invalid sensor value')


def stats(values):
    mean = statistics.mean(values)
    variance = statistics.pvariance(values)
    n = len(values)
    center = (n - 1) / 2
    slope = sum((i - center) * (v - mean) for i, v in enumerate(values)) / sum((i - center) ** 2 for i in range(n))
    return [mean, variance, math.sqrt(statistics.mean(v * v for v in values)),
            max(abs(v) for v in values),
            statistics.mean((v - mean) ** 4 for v in values) / variance ** 2 if variance else 0,
            slope]


def windows(rows):
    validate(rows)
    output, skipped = [], []
    for split, (start, end) in SPLITS.items():
        segment = [row for row in rows if start <= row['t'] < end]
        for offset in range(0, len(segment) - WINDOW + 1, STRIDE):
            chunk = segment[offset:offset + WINDOW]
            features, valid = [], True
            for channel in CHANNELS:
                filled, last, gap = [], None, 0
                missing = sum(row[channel] is None for row in chunk)
                for row in chunk:
                    value = row[channel]
                    if value is None:
                        gap += 1
                        if last is None or gap > 3:
                            valid = False
                            break
                        value = last
                    else:
                        gap = 0
                    filled.append(value)
                    last = value
                if not valid:
                    break
                features.extend(stats(filled) + [missing / WINDOW])
            if not valid:
                skipped.append(dict(split=split, start=chunk[0]['t'], end=chunk[-1]['t']))
                continue
            clean_normal = not any(chunk[0]['t'] < e['end'] and chunk[-1]['t'] >= e['onset'] - 40 for e in EVENTS)
            output.append(dict(split=split, start=chunk[0]['t'], end=chunk[-1]['t'],
                               label=chunk[-1]['label'], clean_normal=clean_normal, features=features))
    return output, skipped


def confusion(labels, predicted):
    if not labels or len(labels) != len(predicted) or any(type(v) not in (int, bool) or v not in (0, 1) for v in labels + predicted):
        raise ValueError('Nonempty aligned binary labels required')
    tp = sum(a == b == 1 for a, b in zip(labels, predicted))
    fp = sum(a == 0 and b == 1 for a, b in zip(labels, predicted))
    fn = sum(a == 1 and b == 0 for a, b in zip(labels, predicted))
    tn = len(labels) - tp - fp - fn
    return dict(tp=tp, fp=fp, fn=fn, tn=tn,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
                false_positive_rate=fp / (fp + tn) if fp + tn else None)


def fit_threshold(records, scores):
    if not records or len(records) != len(scores) or any(r['split'] != 'dev' for r in records):
        raise ValueError('Threshold fitting accepts aligned development records only')
    if any(not math.isfinite(s) for s in scores):
        raise ValueError('Scores must be finite')
    labels = [r['label'] for r in records]
    best = None
    for threshold in sorted(set(scores)) + [math.nextafter(max(scores), math.inf)]:
        metrics = confusion(labels, [int(s >= threshold) for s in scores])
        key = (metrics['f1'], -metrics['fp'], threshold)
        if best is None or key > best[0]:
            best = key, threshold, metrics
    return {'threshold': best[1], 'dev_metrics': best[2]}


def event_metrics(records, predictions, events=EVENTS, warning_horizon=60):
    if len(records) != len(predictions) or warning_horizon < 0:
        raise ValueError('Invalid event evaluation inputs')
    if not records:
        raise ValueError('No evaluated records')
    times = [r['end'] for r, alert in zip(records, predictions) if alert]
    start, end = min(r['start'] for r in records), max(r['end'] for r in records) + 1
    selected = [e for e in events if start <= e['onset'] and e['end'] <= end]
    result = []
    for event in selected:
        matches = [t for t in times if event['onset'] - warning_horizon <= t < event['end']]
        first = min(matches) if matches else None
        result.append(dict(id=event['id'], kind=event['kind'], onset=event['onset'],
                           first_alert=first, lead_seconds=event['onset'] - first if first is not None else None))
    unmatched = [t for t in times if not any(e['onset'] - warning_horizon <= t < e['end'] for e in selected)]
    # Group adjacent unmatched decision points into episodes; this is not point adjustment.
    episodes = sum(i == 0 or t - unmatched[i - 1] > STRIDE for i, t in enumerate(unmatched))
    return dict(events=result, detected=sum(r['first_alert'] is not None for r in result),
                total=len(result), false_alarm_episodes=episodes,
                false_alarm_episodes_per_hour=episodes / ((end - start) / 3600),
                evaluated_hours=(end - start) / 3600)
