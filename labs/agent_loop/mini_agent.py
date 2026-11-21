"""Offline teaching runtime. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol


class ModelAdapter(Protocol):
    async def next(self, messages: list[dict], tools: dict) -> dict: ...


@dataclass(frozen=True)
class Policy:
    max_steps: int = 8
    context_chars: int = 12000
    operation_timeout: float = 0.1
    run_timeout: float = 2.0
    repeat_limit: int = 2
    permissions: frozenset[str] = frozenset({"catalog:read", "math:use"})

    def __post_init__(self):
        for value in (self.max_steps, self.context_chars, self.repeat_limit):
            if type(value) is not int or value < 1:
                raise ValueError("Budgets must be positive integers")
        for value in (self.operation_timeout, self.run_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Timeouts must be finite and positive")


@dataclass(frozen=True)
class Tool:
    schema: dict
    permission: str
    execute: Callable[..., Awaitable[Any]]


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def validate(args: Any, schema: dict) -> None:
    """Validate only the small schema subset used by this lab, not full JSON Schema."""
    if type(args) is not dict:
        raise ValueError("Arguments must be an object")
    properties = schema["properties"]
    if set(args) != set(properties):
        raise ValueError("Missing or unexpected arguments")
    for key, spec in properties.items():
        value = args[key]
        if spec["type"] == "string":
            if type(value) is not str or not 1 <= len(value) <= spec["maxLength"]:
                raise ValueError("Invalid string argument")
        elif spec["type"] == "number":
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Expected a finite number, excluding bool")
            if not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError("Number outside allowed range")
        else:
            raise ValueError("Unsupported schema type")


async def lookup(item: str) -> dict:
    catalog = {"filter": {"price": 12, "currency": "CNY"},
               "brush": {"price": 8, "currency": "CNY"}}
    if item not in catalog:
        raise LookupError("Item unavailable")
    return catalog[item]


async def multiply(a: float, b: float) -> float:
    return a * b


def default_tools() -> dict[str, Tool]:
    number = {"type": "number", "minimum": -1000000, "maximum": 1000000}
    return {
        "lookup": Tool(object_schema({"item": {"type": "string", "maxLength": 64}}),
                       "catalog:read", lookup),
        "multiply": Tool(object_schema({"a": number, "b": number}), "math:use", multiply),
    }


@dataclass
class State:
    messages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    status: str = "created"
    answer: str | None = None
    steps: int = 0


class Harness:
    def __init__(self, tools: dict[str, Tool] | None = None, policy: Policy | None = None):
        self.tools = default_tools() if tools is None else tools
        self.policy = policy or Policy()

    def context(self, messages: list[dict]) -> list[dict]:
        encoded = json.dumps(messages, ensure_ascii=False, allow_nan=False)
        if len(encoded) > self.policy.context_chars:
            raise ValueError("Context budget exceeded")
        return copy.deepcopy(messages)

    def schemas(self) -> dict:
        return copy.deepcopy({name: tool.schema for name, tool in self.tools.items()})

    async def execute(self, name: str, args: Any) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            return {"ok": False, "error": "unknown_tool"}
        if tool.permission not in self.policy.permissions:
            return {"ok": False, "error": "permission_denied"}
        try:
            validate(args, tool.schema)
        except (ValueError, TypeError, OverflowError):
            return {"ok": False, "error": "invalid_arguments"}
        try:
            async with asyncio.timeout(self.policy.operation_timeout):
                value = await tool.execute(**args)
                json.dumps(value, allow_nan=False)
            return {"ok": True, "value": value}
        except TimeoutError:
            return {"ok": False, "error": "tool_timeout"}
        except Exception:
            # Do not expose raw exceptions, credentials, or stack traces to the model.
            return {"ok": False, "error": "tool_failed"}


class Runtime:
    """One isolated in-memory state per run; sequential tool execution."""
    def __init__(self, model: ModelAdapter, harness: Harness | None = None):
        self.model = model
        self.harness = harness or Harness()

    @staticmethod
    def emit(state: State, kind: str, **fields: Any) -> None:
        state.events.append({"seq": len(state.events) + 1, "kind": kind, **fields})

    def finish(self, state: State, status: str) -> State:
        state.status = status
        self.emit(state, "run_finished", status=status, steps=state.steps)
        return state

    async def run(self, task: str) -> State:
        state = State(messages=[{"role": "user", "content": task}], status="running")
        self.emit(state, "run_started")
        try:
            async with asyncio.timeout(self.harness.policy.run_timeout):
                return await self._loop(state)
        except TimeoutError:
            return self.finish(state, "run_timeout")
        except asyncio.CancelledError:
            self.finish(state, "cancelled")
            raise

    async def _loop(self, state: State) -> State:
        seen: dict[str, int] = {}
        for step in range(1, self.harness.policy.max_steps + 1):
            state.steps = step
            try:
                messages = self.harness.context(state.messages)
            except ValueError:
                return self.finish(state, "context_limit")
            self.emit(state, "model_requested", step=step)
            try:
                async with asyncio.timeout(self.harness.policy.operation_timeout):
                    raw = await self.model.next(messages, self.harness.schemas())
            except TimeoutError:
                return self.finish(state, "model_timeout")
            except Exception:
                return self.finish(state, "model_failed")
            try:
                decision = self.parse(raw)
            except (ValueError, TypeError, OverflowError):
                return self.finish(state, "invalid_model_output")
            state.messages.append({"role": "assistant", **decision})
            if decision["type"] == "final":
                state.answer = decision["text"]
                # This is a protocol completion, not independent business verification.
                return self.finish(state, "completed")
            key = json.dumps([decision["name"], decision["args"]], sort_keys=True, allow_nan=False)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > self.harness.policy.repeat_limit:
                return self.finish(state, "repeat_limit")
            self.emit(state, "tool_requested", step=step, tool=decision["name"])
            observation = await self.harness.execute(decision["name"], decision["args"])
            state.messages.append({"role": "tool", "name": decision["name"],
                                   "content": observation})
            self.emit(state, "tool_result", step=step, tool=decision["name"],
                      ok=observation["ok"], error=observation.get("error"))
        return self.finish(state, "step_limit")

    @staticmethod
    def parse(raw: Any) -> dict:
        if type(raw) is not dict:
            raise ValueError("Decision must be an object")
        if raw.get("type") == "final" and set(raw) == {"type", "text"}:
            if type(raw["text"]) is str and 0 < len(raw["text"]) <= 4000:
                return copy.deepcopy(raw)
        if raw.get("type") == "tool" and set(raw) == {"type", "name", "args"}:
            if type(raw["name"]) is str and 0 < len(raw["name"]) <= 64:
                encoded = json.dumps(raw["args"], sort_keys=True, allow_nan=False)
                if len(encoded) <= 4000:
                    return copy.deepcopy(raw)
        raise ValueError("Invalid decision envelope")


class ScriptedModel:
    """Deterministic fixture that reads observations. This is NOT an LLM."""
    async def next(self, messages: list[dict], tools: dict) -> dict:
        observations = [m["content"] for m in messages if m["role"] == "tool"]
        if not observations:
            return {"type": "tool", "name": "lookup", "args": {"item": "filter"}}
        latest = observations[-1]
        if not latest["ok"]:
            return {"type": "final", "text": "Unable to finish: " + latest["error"]}
        if len(observations) == 1:
            return {"type": "tool", "name": "multiply",
                    "args": {"a": latest["value"]["price"], "b": 3}}
        return {"type": "final", "text": f"Total: {latest['value']} CNY"}


class SequenceModel:
    """Fault-injection fixture. Repeats the last decision when exhausted."""
    def __init__(self, decisions: list[dict]):
        self.decisions = decisions
        self.index = 0

    async def next(self, messages: list[dict], tools: dict) -> dict:
        decision = self.decisions[min(self.index, len(self.decisions) - 1)]
        self.index += 1
        return copy.deepcopy(decision)


async def demo(scenario: str) -> State:
    harness = Harness()
    model: ModelAdapter = ScriptedModel()
    if scenario == "denied":
        harness = Harness(policy=Policy(permissions=frozenset()))
    elif scenario == "failure":
        model = SequenceModel([
            {"type": "tool", "name": "lookup", "args": {"item": "missing"}},
            {"type": "final", "text": "No catalog evidence; ask for another item."},
        ])
    elif scenario == "loop":
        model = SequenceModel([{"type": "tool", "name": "lookup", "args": {"item": "filter"}}])
    elif scenario == "timeout":
        async def slow_lookup(item: str) -> dict:
            await asyncio.sleep(1)
            return await lookup(item)
        harness.tools["lookup"] = Tool(harness.tools["lookup"].schema, "catalog:read", slow_lookup)
    return await Runtime(model, harness).run("Calculate the price of three filters.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["success", "failure", "denied", "loop", "timeout"],
                        default="success")
    result = asyncio.run(demo(parser.parse_args().scenario))
    print(json.dumps({"status": result.status, "answer": result.answer,
                      "messages": result.messages, "events": result.events}, indent=2, ensure_ascii=False))
