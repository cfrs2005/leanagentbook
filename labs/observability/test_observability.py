"""Behavioral checks for the original tracing lab."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from observability import Tracer, dashboard, quantiles, redact, replay, run_task, summarize, validate


class ObservabilityTests(unittest.TestCase):
    def test_success_tree(self):
        record = run_task()
        validate(record)
        root = record["spans"][0]
        self.assertEqual(len(record["spans"]), 6)
        self.assertEqual({s["kind"] for s in record["spans"]}, {"workflow", "model", "tool", "retrieval", "approval"})
        self.assertTrue(all(s["parent_id"] == root["span_id"] for s in record["spans"][1:]))

    def test_nested_parent(self):
        t = Tracer()
        with t.span("workflow"):
            with t.span("tool", effect="read") as parent:
                with t.span("retrieval") as child:
                    self.assertEqual(child.parent_id, parent.span_id)
        validate(t.record())

    def test_cross_trace_active_parent_rejected(self):
        a, b = Tracer(), Tracer()
        with a.span("workflow"):
            with self.assertRaises(ValueError):
                with b.span("model"):
                    self.fail("Cross-trace span entered")
        self.assertEqual(b.spans, [])

    def test_async_independent_contexts(self):
        async def task():
            t = Tracer()
            with t.span("workflow"):
                await asyncio.sleep(0)
                with t.span("model"):
                    await asyncio.sleep(0)
            return t.record()
        async def collect():
            return await asyncio.gather(task(), task())
        records = asyncio.run(collect())
        self.assertNotEqual(records[0]["trace_id"], records[1]["trace_id"])
        self.assertEqual(summarize(records)["trace_count"], 2)

    def test_redaction_allowlist(self):
        self.assertEqual(redact({"api_key": "secret", "prompt": "a@example.test", "password": {"secret": 1},
                                 "model": "Bearer secret", "samples": True, "documents": -1,
                                 "result": "inspect", "dataset": "synthetic-v1"}),
                         {"result": "inspect", "dataset": "synthetic-v1"})

    def test_mutation_redacted_on_exit(self):
        t = Tracer()
        with t.span("workflow") as span:
            span.attributes["email"] = "secret@example.test"
        self.assertNotIn("secret", json.dumps(t.record()))

    def test_failure_retains_path_without_message(self):
        record = run_task("tool_failure")
        failed = [s for s in record["spans"] if s["status"] == "error"]
        self.assertEqual([s["kind"] for s in failed], ["workflow", "tool"])
        self.assertTrue(all(s["error_type"] == "TimeoutError" for s in failed))
        self.assertNotIn("never-export", json.dumps(record))
        self.assertFalse(any(s["attributes"].get("effect") == "write" for s in record["spans"]))

    def test_rejection_prevents_tools(self):
        record = run_task("rejected")
        self.assertFalse(any(s["kind"] == "tool" for s in record["spans"]))
        self.assertEqual(record["spans"][0]["status"], "error")

    def test_exception_context_cleanup(self):
        t = Tracer()
        with self.assertRaises(RuntimeError):
            with t.span("workflow"):
                raise RuntimeError("private")
        validate(t.record())
        self.assertIsNone(run_task()["spans"][0]["parent_id"])

    def test_missing_or_cross_trace_parent(self):
        r = run_task()
        r["spans"][1]["parent_id"] = run_task()["spans"][0]["span_id"]
        with self.assertRaises(ValueError):
            validate(r)
        r = run_task()
        r["spans"][1]["trace_id"] = "0" * 32
        with self.assertRaises(ValueError):
            validate(r)

    def test_cycle_and_duplicate_rejected(self):
        r = run_task()
        r["spans"][1]["parent_id"] = r["spans"][1]["span_id"]
        with self.assertRaises(ValueError):
            validate(r)
        r = run_task()
        r["spans"].append(deepcopy(r["spans"][1]))
        with self.assertRaises(ValueError):
            validate(r)

    def test_invalid_time_rejected(self):
        r = run_task()
        r["spans"][1]["end_ns"] = r["spans"][0]["end_ns"] + 1
        with self.assertRaises(ValueError):
            validate(r)

    def test_safe_replay_never_calls_runner_or_network(self):
        r = run_task()
        original = deepcopy(r)
        with patch("observability.run_task", side_effect=AssertionError("No rerun")), \
             patch("socket.socket", side_effect=AssertionError("No network")):
            result = replay(r)
        self.assertEqual(result["executed_tools"], 0)
        self.assertEqual(result["mode"], "read_only")
        self.assertIn("blocked_write", [e["action"] for e in result["events"]])
        self.assertEqual(r, original)

    def test_tampered_replay_rejected(self):
        for key, value in (("command", "touch /tmp/forbidden"), ("effect", "execute"), ("result", "<script>bad</script>")):
            r = run_task()
            r["spans"][-1]["attributes"][key] = value
            with self.assertRaises(ValueError):
                replay(r)

    def test_quantile_exact_and_empty(self):
        self.assertEqual(quantiles(range(1, 101)), {"p50": 50, "p95": 95, "p99": 99})
        self.assertEqual(quantiles([7]), {"p50": 7, "p95": 7, "p99": 7})
        self.assertEqual(quantiles([]), {"p50": None, "p95": None, "p99": None})

    def test_summary_counts_unknowns_and_duplicates(self):
        records = [run_task(s) for s in ("success", "tool_failure", "rejected")]
        summary = summarize(records)
        self.assertEqual(summary["trace_count"], 3)
        self.assertEqual(summary["failed_traces"], 2)
        self.assertEqual(summary["tool_sample_count"], 3)
        self.assertEqual(summary["failure_rate"], 2 / 3)
        for key in ("ttft_ms", "tpot_ms", "input_tokens", "output_tokens", "cost_usd"):
            self.assertIsNone(summary[key])
        with self.assertRaises(ValueError):
            summarize([records[0], records[0]])
        self.assertIsNone(summarize([])["failure_rate"])

    def test_dashboard_offline_safe_content(self):
        page = dashboard([run_task(), run_task("tool_failure")])
        self.assertIn("TimeoutError", page)
        self.assertIn("blocked_write", page)
        self.assertIn("Content-Security-Policy", page)
        for forbidden in ("<script", "https://", "http://", "never-export", "private input"):
            self.assertNotIn(forbidden, page)

    def test_cli_export_and_read_only_replay(self):
        script = str(Path(__file__).with_name("observability.py"))
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, script, "--output", directory], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["failed_traces"], 2)
            files = list(Path(directory).glob("trace-*.json"))
            self.assertEqual(len(files), 3)
            for file in files:
                validate(json.loads(file.read_text()))
            replayed = subprocess.run([sys.executable, script, "--replay", str(Path(directory) / "trace-1.json")], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(replayed.stdout)["executed_tools"], 0)
            self.assertTrue((Path(directory) / "dashboard.html").is_file())


if __name__ == "__main__":
    unittest.main()
