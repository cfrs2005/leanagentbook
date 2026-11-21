"""Offline boundary lab: synthetic budgets and fixed JSON fixtures, no model."""
import argparse
import json


SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "source_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "source_ids"],
    "additionalProperties": False,
}
FIXTURES = {
    "valid": '{"answer":"样例记录中的设备温度是 42 摄氏度。","source_ids":["record-1"]}',
    "wrong-fact": '{"answer":"样例记录中的设备温度是 99 摄氏度。","source_ids":["record-1"]}',
    "invalid": '{"answer":42,"source_ids":["record-1"]}',
    "truncated": '{"answer":"unfinished',
}


def check_budget(input_units: int, output_reserve: int, capacity: int) -> int:
    """Check synthetic units, not tokens; return unallocated capacity."""
    values = (input_units, output_reserve, capacity)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("budget values must be non-negative integers")
    if capacity == 0:
        raise ValueError("capacity must be positive")
    remaining = capacity - input_units - output_reserve
    if remaining < 0:
        raise ValueError("context budget exceeded")
    return remaining


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-standard JSON constant: " + value)


def validate_output(raw: str) -> dict:
    """Validate this fixed schema only, not arbitrary JSON Schema documents."""
    if not isinstance(raw, str):
        raise ValueError("output must be text")
    if len(raw) > 4096:
        raise ValueError("output exceeds the lab character limit")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid or incomplete JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("output must be an object")
    if set(value) != {"answer", "source_ids"}:
        raise ValueError("missing or unexpected fields")
    if not isinstance(value["answer"], str) or len(value["answer"]) < 1:
        raise ValueError("answer must be a non-empty string")
    sources = value["source_ids"]
    if not isinstance(sources, list) or any(not isinstance(item, str) for item in sources):
        raise ValueError("source_ids must be an array of strings")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=FIXTURES, default="valid")
    parser.add_argument("--input-units", type=int, default=80)
    parser.add_argument("--output-reserve", type=int, default=20)
    parser.add_argument("--capacity", type=int, default=100)
    args = parser.parse_args(argv)
    report = {"mode": "offline_fixture", "budget_unit": "synthetic_unit",
              "fact_check": "not_performed", "fixture_read": False}
    try:
        report["remaining_units"] = check_budget(
            args.input_units, args.output_reserve, args.capacity)
        report["fixture_read"] = True
        report["output"] = validate_output(FIXTURES[args.scenario])
        report["status"] = "structure_valid"
    except ValueError as exc:
        report.update(status="rejected", error=str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "structure_valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
