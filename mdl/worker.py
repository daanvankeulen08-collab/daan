"""Bounded worker process for tool execution.

On Windows, full memory/CPU cgroups are not available without extra native
dependencies.  The strongest practical isolation for Block 1 is a spawned
child process with a hard wall-clock timeout and termination.  Residual risks
are documented in ``README_BLOCK1.md``.
"""

from __future__ import annotations

import multiprocessing as mp
import time
from collections.abc import Callable
from typing import Any

from .errors import ToolExecutionError, ToolTimeoutError
from .symbolic import expand_expression


def _expand_target(expression: str) -> dict:
    return expand_expression(expression)


def _sleep_for(seconds: float) -> dict:
    """Test helper used to exercise timeout handling deterministically."""

    time.sleep(float(seconds))
    return {"slept": seconds}


def _child(connection: Any, target: Callable[[Any], Any], argument: Any) -> None:
    try:
        connection.send(("ok", target(argument)))
    except BaseException as exc:  # noqa: BLE001 - must cross the process boundary
        try:
            connection.send(("error", type(exc).__name__, str(exc)))
        except BaseException:
            pass
    finally:
        connection.close()


def run_in_subprocess(
    target: Callable[[Any], Any],
    argument: Any,
    timeout: float,
) -> Any:
    """Run *target(argument)* in a spawned process with a hard timeout."""

    if timeout <= 0:
        raise ToolTimeoutError("tool timeout must be positive")

    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(child, target, argument), daemon=True)
    process.start()
    child.close()

    message: tuple | None = None
    timed_out = False
    try:
        if not parent.poll(timeout):
            timed_out = True
        else:
            try:
                message = parent.recv()
            except EOFError as exc:
                raise ToolExecutionError(
                    "worker exited without returning a result"
                ) from exc
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(5)
        if process.is_alive():  # pragma: no cover - very unusual
            process.kill()
            process.join(5)

    if timed_out:
        raise ToolTimeoutError(
            f"tool exceeded {timeout:.1f}s and was terminated"
        )
    if message is None:  # pragma: no cover - defensive
        raise ToolExecutionError("worker produced no result")
    if message[0] == "ok":
        return message[1]
    raise ToolExecutionError(f"{message[1]}: {message[2]}")
