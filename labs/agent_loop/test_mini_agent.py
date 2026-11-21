"""Behavior tests for the offline teaching runtime."""
import asyncio
import unittest

from mini_agent import Harness, Policy, Runtime, ScriptedModel, SequenceModel, Tool, demo


def call(name="lookup", args=None):
    return {"type": "tool", "name": name, "args": {"item": "filter"} if args is None else args}


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_and_observation_flow(self):
        state = await demo("success")
        self.assertEqual((state.status, state.answer, state.steps), ("completed", "Total: 36 CNY", 3))
        tools = [m for m in state.messages if m["role"] == "tool"]
        self.assertEqual([m["name"] for m in tools], ["lookup", "multiply"])
        self.assertEqual(tools[-1]["content"]["value"], 36)
        self.assertEqual([e["seq"] for e in state.events], list(range(1, len(state.events) + 1)))
        self.assertEqual(state.events[-1]["kind"], "run_finished")

    async def test_failure_is_fed_back(self):
        state = await demo("failure")
        self.assertEqual(state.messages[2]["content"]["error"], "tool_failed")
        self.assertEqual(state.status, "completed")

    async def test_permission_blocks_execution(self):
        executed = []
        async def spy(item):
            executed.append(item)
        harness = Harness(policy=Policy(permissions=frozenset()))
        harness.tools["lookup"] = Tool(harness.tools["lookup"].schema, "catalog:read", spy)
        state = await Runtime(ScriptedModel(), harness).run("task")
        self.assertEqual(executed, [])
        self.assertEqual(state.messages[2]["content"]["error"], "permission_denied")
        self.assertIn("permission_denied", state.answer)

    async def test_argument_validation(self):
        harness = Harness()
        for args in ({}, {"a": True, "b": 2}, {"a": "2", "b": 3},
                     {"a": 1, "b": 2, "admin": True}, {"a": 1000001, "b": 1},
                     {"a": float("nan"), "b": 1}, []):
            with self.subTest(args=args):
                self.assertEqual((await harness.execute("multiply", args))["error"], "invalid_arguments")

    async def test_unknown_tool(self):
        self.assertEqual((await Harness().execute("shell", {}))["error"], "unknown_tool")

    async def test_repeat_limit(self):
        state = await demo("loop")
        self.assertEqual(state.status, "repeat_limit")
        self.assertEqual(len([e for e in state.events if e["kind"] == "tool_result"]), 2)

    async def test_step_limit_for_different_calls(self):
        model = SequenceModel([call("multiply", {"a": n, "b": 2}) for n in range(5)])
        state = await Runtime(model, Harness(policy=Policy(max_steps=3))).run("task")
        self.assertEqual((state.status, state.steps), ("step_limit", 3))

    async def test_tool_timeout_cancels_cooperative_tool(self):
        cancelled = []
        async def slow(item):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        harness = Harness(policy=Policy(operation_timeout=0.01))
        harness.tools["lookup"] = Tool(harness.tools["lookup"].schema, "catalog:read", slow)
        state = await Runtime(ScriptedModel(), harness).run("task")
        self.assertEqual(state.messages[2]["content"]["error"], "tool_timeout")
        self.assertEqual(cancelled, [True])

    async def test_model_timeout(self):
        class SlowModel:
            async def next(self, messages, tools):
                await asyncio.sleep(10)
        state = await Runtime(SlowModel(), Harness(policy=Policy(operation_timeout=0.01))).run("task")
        self.assertEqual(state.status, "model_timeout")

    async def test_total_deadline(self):
        class SlowModel:
            async def next(self, messages, tools):
                await asyncio.sleep(10)
        state = await Runtime(SlowModel(), Harness(policy=Policy(operation_timeout=1, run_timeout=0.01))).run("task")
        self.assertEqual(state.status, "run_timeout")
        self.assertEqual(state.events[-1]["status"], "run_timeout")

    async def test_context_budget(self):
        state = await Runtime(ScriptedModel(), Harness(policy=Policy(context_chars=1))).run("task")
        self.assertEqual(state.status, "context_limit")
        self.assertFalse(any(e["kind"] == "model_requested" for e in state.events))

    async def test_invalid_model_output(self):
        for output in (None, {"type": "final", "text": ""}, {"type": "tool", "name": "lookup"},
                       {"type": "tool", "name": "lookup", "args": {1: "bad", "item": "filter"}}):
            state = await Runtime(SequenceModel([output])).run("task")
            self.assertEqual(state.status, "invalid_model_output")

    async def test_model_failure(self):
        class BrokenModel:
            async def next(self, messages, tools):
                raise RuntimeError("Private diagnostic")
        state = await Runtime(BrokenModel()).run("task")
        self.assertEqual(state.status, "model_failed")
        self.assertNotIn("Private diagnostic", str(state.events))

    async def test_external_cancellation_propagates(self):
        started = asyncio.Event()
        class WaitingModel:
            async def next(self, messages, tools):
                started.set()
                await asyncio.sleep(10)
        task = asyncio.create_task(Runtime(WaitingModel()).run("task"))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    def test_invalid_policy(self):
        for values in ({"max_steps": 0}, {"repeat_limit": True}, {"operation_timeout": float("inf")}):
            with self.assertRaises(ValueError):
                Policy(**values)


if __name__ == "__main__":
    unittest.main()
