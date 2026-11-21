"""Fit real Isolation Forest and XGBoost on chronological synthetic windows."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

from series import CHANNELS, EVENTS, SPLITS, WINDOW, STRIDE, generate, windows, confusion, fit_threshold, event_metrics


def main():
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from xgboost import XGBClassifier
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = generate()
    records, skipped = windows(rows)
    subsets = {split: [r for r in records if r['split'] == split] for split in SPLITS}
    x = {split: np.array([r['features'] for r in group]) for split, group in subsets.items()}
    normal = np.array([r['features'] for r in subsets['train'] if r['clean_normal']])
    center, scale = normal.mean(axis=0), np.maximum(normal.std(axis=0), 1e-8)
    scores = {'z_score': {split: np.max(np.abs((values - center) / scale), axis=1).tolist()
                          for split, values in x.items()}}
    configs = {'isolation_forest': dict(n_estimators=100, max_samples=256, contamination='auto', random_state=41, n_jobs=1),
               'xgboost': dict(n_estimators=80, max_depth=3, learning_rate=.08, subsample=1,
                               colsample_bytree=1, objective='binary:logistic', eval_metric='logloss',
                               tree_method='hist', random_state=41, n_jobs=1)}
    durations = {}
    tick = time.perf_counter()
    isolation = IsolationForest(**configs['isolation_forest']).fit(normal)
    durations['isolation_forest_fit_seconds'] = time.perf_counter() - tick
    scores['isolation_forest'] = {split: (-isolation.score_samples(values)).tolist() for split, values in x.items()}
    tick = time.perf_counter()
    booster = XGBClassifier(**configs['xgboost']).fit(x['train'], [r['label'] for r in subsets['train']])
    durations['xgboost_fit_seconds'] = time.perf_counter() - tick
    scores['xgboost'] = {split: booster.predict_proba(values)[:, 1].tolist() for split, values in x.items()}
    results = {}
    for name, values in scores.items():
        fitted = fit_threshold(subsets['dev'], values['dev'])
        predicted = [int(s >= fitted['threshold']) for s in values['test']]
        results[name] = dict(**fitted, test_metrics=confusion([r['label'] for r in subsets['test']], predicted),
                             event_metrics=event_metrics(subsets['test'], predicted),
                             test_predictions=predicted)
    with (args.output / 'telemetry.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['t', 'label', *CHANNELS])
        writer.writeheader()
        writer.writerows(rows)
    report = dict(schema='time-series-lab-v1', synthetic=True, seed=41,
                  window=WINDOW, stride=STRIDE, split_intervals=SPLITS, events=EVENTS,
                  features=[f'{channel}_{stat}' for channel in CHANNELS
                            for stat in ['mean', 'variance', 'rms', 'peak', 'kurtosis', 'slope', 'missing_fraction']],
                  configs=configs, timings=durations, normal_fit_windows=len(normal),
                  normal_center=center.tolist(), normal_scale=scale.tolist(),
                  environment={'python': platform.python_version(), 'platform': platform.platform(),
                               'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'scikit-learn', 'xgboost']}},
                  hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          [Path(__file__), Path(__file__).with_name('series.py'), args.output / 'telemetry.csv']},
                  windows=records, skipped=skipped, scores=scores, results=results)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: {k: v for k, v in value.items() if k != 'test_predictions'}
                      for name, value in results.items()}, indent=2))


if __name__ == '__main__':
    main()
