"""Deterministic orchestration lab; no LLM or external side effects."""
import argparse
import asyncio
from dataclasses import asdict, dataclass, field
import json
import math
import time


class TransientError(Exception):
    pass


@dataclass(frozen=True)
class Context:
    task_id: str = "synthetic-001"
    readings: tuple[int, ...] = (42, 56, 71)


@dataclass(frozen=True)
class Policy:
    attempt_timeout: float = 0.1
    run_timeout: float = 1.0
    max_attempts: int = 2
    backoff: float = 0.01

    def __post_init__(self):
        for name in ("attempt_timeout", "run_timeout", "backoff"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be an integer from 1 to 5")


@dataclass
class Run:
    state: str = "created"
    results: dict = field(default_factory=dict)
    summary: dict | None = None
    events: list = field(default_factory=list)
    attempts: int = 0
    elapsed_seconds: float = 0.0

    def emit(self, kind, **fields):
        self.events.append({"seq": len(self.events) + 1, "kind": kind, **fields})


async def readings_worker(context, attempt, scenario):
    await asyncio.sleep(0.03)
    if scenario == "retry" and attempt == 1:
        raise TransientError("scripted temporary read failure")
    if scenario == "exhausted":
        raise TransientError("scripted repeated read failure")
    if scenario == "failure":
        raise ValueError("scripted permanent input failure")
    return {"maximum": max(context.readings), "sample_count": len(context.readings)}


async def review_worker(context, attempt, scenario):
    await asyncio.sleep(1.0 if scenario == "timeout" else 0.03)
    return {"recommendation": "inspect" if max(context.readings) >= 70 else "observe"}


async def execute_worker(name, worker, context, scenario, policy, run):
    for attempt in range(1, policy.max_attempts + 1):
        run.attempts += 1
        run.emit("attempt_started", worker=name, attempt=attempt)
        try:
            async with asyncio.timeout(policy.attempt_timeout):
                value = await worker(context, attempt, scenario)
        except (TimeoutError, TransientError) as exc:
            error = "attempt_timeout" if isinstance(exc, TimeoutError) else "transient_error"
            run.emit("attempt_failed", worker=name, attempt=attempt, error=error)
            if attempt < policy.max_attempts:
                run.emit("retry_scheduled", worker=name, attempt=attempt + 1)
                await asyncio.sleep(policy.backoff * attempt)
                continue
            result = {"ok": False, "attempts": attempt, "error": error}
        except ValueError:
            run.emit("attempt_failed", worker=name, attempt=attempt, error="permanent_error")
            result = {"ok": False, "attempts": attempt, "error": "permanent_error"}
        else:
            result = {"ok": True, "attempts": attempt, "value": value}
            run.emit("attempt_succeeded", worker=name, attempt=attempt)
        run.results[name] = result
        return


async def supervise(*, scenario="success", approval="pending", mode="parallel", policy=None):
    if scenario not in ("success", "retry", "exhausted", "failure", "timeout"):
        raise ValueError("unknown scenario")
    if approval not in ("pending", "approve", "reject"):
        raise ValueError("unknown approval")
    if mode not in ("parallel", "serial"):
        raise ValueError("unknown mode")
    policy = policy or Policy()
    context = Context()
    run = Run()
    started = time.perf_counter()
    run.state = "running"
    run.emit("run_started", task_id=context.task_id, mode=mode)
    workers = (("readings", readings_worker), ("review", review_worker))
    try:
        async with asyncio.timeout(policy.run_timeout):
            if mode == "parallel":
                async with asyncio.TaskGroup() as group:
                    for name, worker in workers:
                        group.create_task(execute_worker(name, worker, context, scenario, policy, run))
            else:
                for name, worker in workers:
                    await execute_worker(name, worker, context, scenario, policy, run)
    except TimeoutError:
        run.state = "timed_out"
        run.emit("run_timeout")
    else:
        if any(not result["ok"] for result in run.results.values()):
            run.state = "failed"
        else:
            # Namespaced outputs prevent last-writer-wins merging.
            run.summary = {name: run.results[name]["value"] for name, _ in workers}
            run.state = "awaiting_approval"
            run.emit("approval_requested")
            if approval == "reject":
                run.state = "rejected"
                run.emit("approval_rejected")
            elif approval == "approve":
                run.state = "completed"
                run.emit("approval_granted")
                run.emit("report_released", simulated=True)
    finally:
        run.elapsed_seconds = round(time.perf_counter() - started, 6)
    run.emit("run_finished", state=run.state)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("success", "retry", "exhausted", "failure", "timeout"), default="success")
    parser.add_argument("--approval", choices=("pending", "approve", "reject"), default="pending")
    parser.add_argument("--mode", choices=("parallel", "serial"), default="parallel")
    parser.add_argument("--attempt-timeout", type=float, default=0.1)
    parser.add_argument("--run-timeout", type=float, default=1.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args()
    try:
        policy = Policy(args.attempt_timeout, args.run_timeout, args.max_attempts)
    except ValueError as exc:
        parser.error(str(exc))
    run = asyncio.run(supervise(scenario=args.scenario, approval=args.approval, mode=args.mode, policy=policy))
    print(json.dumps(asdict(run), ensure_ascii=False, indent=2))
    return {"completed": 0, "awaiting_approval": 3, "rejected": 4, "failed": 1, "timed_out": 1}[run.state]


if __name__ == "__main__":
    raise SystemExit(main())
