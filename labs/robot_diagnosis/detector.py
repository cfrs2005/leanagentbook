"""Detect teaching events in synthetic, one-hertz sensor CSV files."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

FIELDS = ["time_s", "motor_current_a", "vibration_mm_s"]
LIMITS = {"motor_current_a": 8.0, "vibration_mm_s": 6.0}
WINDOW_SECONDS = 5
MAX_SECONDS = 3600
MAX_BYTES = 1024 * 1024


def analyze(path):
    """Return evidence, never a root-cause diagnosis or control command."""
    with Path(path).open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("input exceeds the 1 MiB teaching limit")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    if reader.fieldnames != FIELDS:
        raise ValueError("header must be: " + ",".join(FIELDS))
    rows = {}
    previous = -1
    for line, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"line {line}: wrong column count")
        try:
            timestamp = int(row["time_s"])
        except ValueError as error:
            raise ValueError(f"line {line}: time_s must be an integer") from error
        if timestamp <= previous or not 0 <= timestamp < MAX_SECONDS:
            raise ValueError(f"line {line}: timestamps must increase within 0..3599")
        values = {}
        for field in LIMITS:
            value = row[field].strip()
            if not value:
                values[field] = None
                continue
            try:
                number = float(value)
            except ValueError as error:
                raise ValueError(f"line {line}: invalid {field}") from error
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"line {line}: {field} must be finite and nonnegative")
            values[field] = number
        rows[timestamp] = values
        previous = timestamp
    if not rows:
        raise ValueError("input contains no samples")
    events = []
    for start in range(0, previous + 1, WINDOW_SECONDS):
        evidence = []
        missing = []
        signals = []
        for field, threshold in LIMITS.items():
            observed = []
            hits = []
            for timestamp in range(start, start + WINDOW_SECONDS):
                value = rows.get(timestamp, {}).get(field)
                if value is None:
                    missing.append({"time_s": timestamp, "field": field})
                else:
                    observed.append(value)
                    if value >= threshold:
                        hits.append({"time_s": timestamp, "value": value})
            evidence.append({"field": field, "threshold": threshold,
                             "observed_count": len(observed),
                             "max": max(observed) if observed else None,
                             "threshold_hits": hits})
            if len(hits) >= 2:
                signals.append(field)
        status = "abnormal" if signals else "insufficient_data" if missing else "normal"
        uncertainty = ["阈值仅用于教学；未校准故障概率。", "合成数据不能证明实机表现；故障假设不等于根因。"]
        if missing:
            uncertainty.append("窗口有缺失值，无法排除未观测时段的异常。")
        events.append({
            "window": {"start_s": start, "end_exclusive_s": start + WINDOW_SECONDS},
            "status": status, "evidence": evidence, "missing": missing,
            "hypotheses": ([{"statement": "负载变化或传感器偏差可能解释超阈值。",
                             "basis_fields": signals, "confirmed": False}] if signals else []),
            "uncertainty": uncertainty,
            "next_step": "人工核对工况和传感器记录；必要时按现场安全规程补采。",
        })
    return {"schema_version": "1.0", "rule_version": "synthetic-threshold-v1",
            "source": {"sha256": hashlib.sha256(raw).hexdigest(), "synthetic": True,
                       "sample_count": len(rows), "expected_interval_s": 1},
            "rule": {"window_seconds": WINDOW_SECONDS, "minimum_hits_per_signal": 2,
                     "thresholds": LIMITS, "comparison": ">="},
            "scope": "synthetic_csv_only", "root_cause_confirmed": False,
            "automatic_control": False, "events": events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    try:
        report = analyze(args.input)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                          allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Wrote {len(report['events'])} windows to {args.output}")


if __name__ == "__main__":
    main()
