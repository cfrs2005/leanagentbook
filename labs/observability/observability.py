"""Original standard-library tracing lab; synthetic data, no model/network calls."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
import html
import json
import math
from pathlib import Path
import time
import uuid

# Only bounded, known values cross the telemetry boundary. Free text is omitted.
ENUMS = {
    "dataset": {"synthetic-v1"}, "model": {"scripted-v1"},
    "effect": {"read", "write"}, "approval": {"approved", "rejected"},
    "result": {"inspect", "observe", "draft_only"},
}
COUNTS = {"documents", "samples"}
KINDS = {"workflow", "retrieval", "model", "approval", "tool"}
ERRORS = {"TimeoutError", "PermissionError", "ValueError", "RuntimeError"}
_active: ContextVar[tuple[str, str] | None] = ContextVar("observability_span", default=None)


def redact(attributes: dict) -> dict:
    """Drop arbitrary keys/text, including prompts, credentials and exception messages."""
    safe = {}
    for key, value in attributes.items():
        if key in ENUMS and isinstance(value, str) and value in ENUMS[key]:
            safe[key] = value
        elif key in COUNTS and type(value) is int and 0 <= value <= 1000000:
            safe[key] = value
    return safe


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    kind: str
    start_ns: int
    end_ns: int | None
    status: str
    attributes: dict
    error_type: str | None = None


class Tracer:
    def __init__(self):
        self.trace_id = uuid.uuid4().hex
        self.spans: list[Span] = []

    @contextmanager
    def span(self, kind: str, **attributes):
        if kind not in KINDS:
            raise ValueError("Unsupported span kind")
        active = _active.get()
        if active is not None and active[0] != self.trace_id:
            raise ValueError("Cross-trace parent is forbidden")
        span = Span(self.trace_id, uuid.uuid4().hex[:16],
                    active[1] if active else None, kind,
                    time.perf_counter_ns(), None, "ok", redact(attributes))
        self.spans.append(span)
        token = _active.set((self.trace_id, span.span_id))
        try:
            yield span
        except BaseException as exc:
            span.status = "error"
            name = type(exc).__name__
            span.error_type = name if name in ERRORS else "OtherError"
            raise
        finally:
            span.end_ns = time.perf_counter_ns()
            # Reapply the boundary if a caller changed attributes in the body.
            span.attributes = redact(span.attributes)
            _active.reset(token)

    def record(self):
        record = {"schema": "lab-trace-v1", "trace_id": self.trace_id,
                  "spans": [asdict(span) for span in self.spans]}
        validate(record)
        return record


def validate(record: dict):
    """Reject malformed, unsafe or causally invalid persisted traces."""
    if set(record) != {"schema", "trace_id", "spans"} or record["schema"] != "lab-trace-v1":
        raise ValueError("Unsupported schema")
    trace_id = record["trace_id"]
    def is_hex(value, size):
        return isinstance(value, str) and len(value) == size and all(c in "0123456789abcdef" for c in value)
    if not is_hex(trace_id, 32) or not isinstance(record["spans"], list) or not record["spans"]:
        raise ValueError("Invalid trace")
    spans = record["spans"]
    index = {}
    for s in spans:
        if set(s) != set(Span.__dataclass_fields__):
            raise ValueError("Unexpected span fields")
        if s["trace_id"] != trace_id or not is_hex(s["span_id"], 16) or s["span_id"] in index:
            raise ValueError("Invalid or duplicate span identity")
        if s["kind"] not in KINDS or s["status"] not in {"ok", "error"}:
            raise ValueError("Invalid kind/status")
        if s["error_type"] not in ERRORS | {None, "OtherError"}:
            raise ValueError("Unsafe error value")
        if (s["status"] == "error") != (s["error_type"] is not None):
            raise ValueError("Inconsistent error status")
        if not isinstance(s["attributes"], dict) or redact(s["attributes"]) != s["attributes"]:
            raise ValueError("Unsafe attributes")
        if any(type(s[k]) is not int or s[k] < 0 for k in ("start_ns", "end_ns")) or s["end_ns"] < s["start_ns"]:
            raise ValueError("Invalid timing")
        index[s["span_id"]] = s
    roots = [s for s in spans if s["parent_id"] is None]
    if len(roots) != 1 or roots[0]["kind"] != "workflow":
        raise ValueError("Expected one workflow root")
    for s in spans:
        seen = {s["span_id"]}
        current = s
        while current["parent_id"] is not None:
            parent_id = current["parent_id"]
            if parent_id not in index or parent_id in seen:
                raise ValueError("Missing parent or cycle")
            parent = index[parent_id]
            if not (parent["start_ns"] <= current["start_ns"] <= current["end_ns"] <= parent["end_ns"]):
                raise ValueError("Child outside parent lifetime")
            seen.add(parent_id)
            current = parent
    return record


def run_task(scenario="success"):
    if scenario not in {"success", "tool_failure", "rejected"}:
        raise ValueError("Unknown scenario")
    tracer = Tracer()
    try:
        with tracer.span("workflow", dataset="synthetic-v1", prompt="private input"):
            with tracer.span("retrieval", documents=2):
                readings = (42, 56, 71)
            with tracer.span("model", model="scripted-v1") as model:
                recommendation = "inspect" if max(readings) > 60 else "observe"
                model.attributes["result"] = recommendation
            with tracer.span("approval", approval="rejected" if scenario == "rejected" else "approved"):
                if scenario == "rejected":
                    raise PermissionError("Synthetic rejection; private reason omitted")
            with tracer.span("tool", effect="read", samples=len(readings)):
                if scenario == "tool_failure":
                    raise TimeoutError("Synthetic secret=never-export-this")
                max(readings)
            with tracer.span("tool", effect="write", result="draft_only"):
                # This is a planned external write; no external writer exists in this lab.
                pass
    except (TimeoutError, PermissionError):
        pass
    return tracer.record()


def replay(record: dict) -> dict:
    """Read recorded evidence only. No tools, imports, callbacks or network dispatch."""
    validate(record)
    events = []
    for span in sorted(record["spans"], key=lambda s: s["start_ns"]):
        action = "inspect_recorded"
        if span["kind"] == "tool":
            # Missing/unknown effects cannot authorize execution either.
            action = "blocked_write" if span["attributes"].get("effect") == "write" else "inspect_recorded_tool"
        events.append({"span_id": span["span_id"], "kind": span["kind"],
                       "recorded_status": span["status"], "action": action})
    return {"trace_id": record["trace_id"], "mode": "read_only",
            "executed_tools": 0, "events": events}


def quantiles(values):
    """Nearest-rank quantiles; one sample can occupy every reported quantile."""
    ordered = sorted(values)
    return {f"p{p}": ordered[math.ceil(p / 100 * len(ordered)) - 1] if ordered else None
            for p in (50, 95, 99)}


def summarize(records):
    roots, tools = [], []
    failed = 0
    seen = set()
    for record in records:
        validate(record)
        if record["trace_id"] in seen:
            raise ValueError("Duplicate trace in aggregation")
        seen.add(record["trace_id"])
        for span in record["spans"]:
            duration = (span["end_ns"] - span["start_ns"]) / 1e6
            if span["parent_id"] is None:
                roots.append(duration)
                failed += span["status"] == "error"
            if span["kind"] == "tool":
                tools.append(duration)
    return {"trace_count": len(roots), "failed_traces": failed,
            "failure_rate": failed / len(roots) if roots else None,
            "task_latency_ms": quantiles(roots), "tool_latency_ms": quantiles(tools),
            "tool_sample_count": len(tools), "ttft_ms": None, "tpot_ms": None,
            "input_tokens": None, "output_tokens": None, "cost_usd": None,
            "measurement": "local perf_counter_ns; synthetic scripted model; nearest-rank"}


def dashboard(records):
    summary = summarize(records)
    escape = lambda value: html.escape(str(value), quote=True)
    cards = []
    for record in records:
        rows = []
        base = min(s["start_ns"] for s in record["spans"])
        for s in record["spans"]:
            rows.append("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in (
                s["span_id"], s["parent_id"] or "根节点", s["kind"], s["status"],
                f'{(s["start_ns"]-base)/1e6:.4f}', f'{(s["end_ns"]-s["start_ns"])/1e6:.4f}',
                s["error_type"] or "—", json.dumps(s["attributes"], ensure_ascii=False))) + "</tr>")
        cards.append(f'<section><h2>任务 {escape(record["trace_id"])}</h2><div class="scroll"><table><thead><tr>'
                     '<th>Span</th><th>Parent</th><th>类型</th><th>状态</th><th>起点 ms</th><th>耗时 ms</th><th>错误</th><th>安全属性</th>'
                     '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
                     '<details><summary>只读回放（不执行任何工具）</summary><pre>'
                     + escape(json.dumps(replay(record), ensure_ascii=False, indent=2)) + '</pre></details></section>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>第15章 · 离线观测报告</title><style>
body{background:#F6F1E7;color:#22312F;font:16px/1.6 'PingFang SC','Microsoft YaHei',sans-serif;margin:2rem}
h1{color:#B94F2D}section{background:#FFFCF6;padding:1rem;margin:1rem 0;border:1px solid #D9D2C4}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.5rem;border-bottom:1px solid #D9D2C4}
pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;color:#316653}h2{overflow-wrap:anywhere;font-size:1.1rem}
</style><h1>第15章 · 离线观测报告</h1>
<p>合成数据 / 确定性脚本模型 / 本机实测耗时。写入步骤仅为计划。没有外部调用。</p>
<section><h2>运行摘要</h2><p>本批全部任务含失败；nearest-rank 分位数，单位毫秒。小样本不能估计生产尾延迟。
null 表示未知：无流式 token 事件、供应商用量与价格，因此不报告 TTFT、TPOT、token 或费用。</p><pre>''' + escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre></section>' + "".join(cards) + '</html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("labs/observability/output"))
    parser.add_argument("--replay", type=Path, help="Inspect one saved trace; never execute tools")
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(json.loads(args.replay.read_text(encoding="utf-8"))), indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    records = [run_task(s) for s in ("success", "tool_failure", "rejected")]
    for index, record in enumerate(records, 1):
        (args.output / f"trace-{index}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    summary = summarize(records)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.output / "dashboard.html").write_text(dashboard(records), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
