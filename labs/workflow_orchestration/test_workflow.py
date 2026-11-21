import asyncio
import unittest
from unittest.mock import patch

from workflow import Policy, supervise


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_success(self):
        run = await supervise(approval="approve")
        self.assertEqual(run.state, "completed")
        self.assertEqual(run.attempts, 2)
        self.assertEqual(run.summary["readings"]["maximum"], 71)
        self.assertEqual(run.summary["review"]["recommendation"], "inspect")

    async def test_pending_by_default(self):
        run = await supervise()
        self.assertEqual(run.state, "awaiting_approval")
        self.assertNotIn("report_released", [e["kind"] for e in run.events])

    async def test_rejected(self):
        run = await supervise(approval="reject")
        self.assertEqual(run.state, "rejected")
        self.assertNotIn("report_released", [e["kind"] for e in run.events])

    async def test_transient_retry(self):
        run = await supervise(scenario="retry", approval="approve")
        self.assertEqual(run.state, "completed")
        self.assertEqual(run.results["readings"]["attempts"], 2)
        self.assertEqual(run.attempts, 3)

    async def test_retry_exhausted(self):
        run = await supervise(scenario="exhausted", approval="approve")
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.results["readings"]["attempts"], 2)
        self.assertIsNone(run.summary)

    async def test_permanent_failure_not_retried(self):
        run = await supervise(scenario="failure", approval="approve")
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.results["readings"]["attempts"], 1)
        self.assertNotIn("approval_requested", [e["kind"] for e in run.events])

    async def test_attempt_timeout(self):
        run = await supervise(scenario="timeout", policy=Policy(attempt_timeout=0.01))
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.results["review"]["error"], "attempt_timeout")
        self.assertEqual(run.results["review"]["attempts"], 2)

    async def test_total_timeout_cancels_workers(self):
        cancelled = []
        async def slow(context, attempt, scenario):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        with patch("workflow.readings_worker", slow), patch("workflow.review_worker", slow):
            run = await supervise(policy=Policy(run_timeout=0.02))
        self.assertEqual(run.state, "timed_out")
        self.assertEqual(len(cancelled), 2)
        self.assertIsNone(run.summary)

    async def test_external_cancellation_propagates(self):
        started = asyncio.Event()
        cleaned = asyncio.Event()
        async def slow(context, attempt, scenario):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cleaned.set()
        with patch("workflow.readings_worker", slow):
            task = asyncio.create_task(supervise())
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(cleaned.is_set())

    async def test_parallel_workers_overlap(self):
        both_started = asyncio.Event()
        count = 0
        async def barrier(context, attempt, scenario):
            nonlocal count
            count += 1
            if count == 2:
                both_started.set()
            await both_started.wait()
            return {"maximum": 71, "sample_count": 3, "recommendation": "inspect"}
        with patch("workflow.readings_worker", barrier), patch("workflow.review_worker", barrier):
            run = await supervise(approval="approve", policy=Policy(attempt_timeout=1))
        self.assertEqual(run.state, "completed")
        self.assertEqual(count, 2)

    async def test_serial_same_output(self):
        parallel = await supervise(approval="approve")
        serial = await supervise(approval="approve", mode="serial")
        self.assertEqual(serial.summary, parallel.summary)
        self.assertEqual(serial.attempts, parallel.attempts)

    async def test_conflict_blocks_all_approval_choices_in_both_modes(self):
        for mode in ("parallel", "serial"):
            for approval in ("pending", "approve", "reject"):
                run = await supervise(scenario="conflict", mode=mode, approval=approval)
                self.assertEqual(run.state, "needs_review")
                self.assertEqual(run.summary["readings"]["maximum"], 71)
                self.assertEqual(run.summary["review"]["recommendation"], "observe")
                kinds = [event["kind"] for event in run.events]
                self.assertIn("conflict_detected", kinds)
                self.assertNotIn("approval_requested", kinds)
                self.assertNotIn("report_released", kinds)

    async def test_invalid_input(self):
        for arguments in ({"approval": "yes"}, {"mode": "unknown"}, {"scenario": "unknown"}):
            with self.assertRaises(ValueError):
                await supervise(**arguments)
        for arguments in ({"attempt_timeout": 0}, {"run_timeout": float("nan")},
                          {"max_attempts": 0}, {"max_attempts": 6}, {"max_attempts": True}):
            with self.assertRaises(ValueError):
                Policy(**arguments)


if __name__ == "__main__":
    unittest.main()
