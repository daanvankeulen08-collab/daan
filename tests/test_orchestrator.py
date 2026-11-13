"""Tests for the allowlisted tool orchestrator and worker isolation."""

from __future__ import annotations

import pytest

from mdl.errors import ToolTimeoutError, ToolValidationError
from mdl.orchestrator import ToolOrchestrator
from mdl.worker import _sleep_for, run_in_subprocess


@pytest.fixture
def orchestrator():
    return ToolOrchestrator(timeout_s=10.0)


def test_executes_allowed_expansion(orchestrator):
    execution = orchestrator.execute(
        {"tool": "symbolic_expand", "arguments": {"expression": "(x + 1)**3"}}
    )
    assert execution.result.expanded == "x**3 + 3*x**2 + 3*x + 1"
    assert execution.result.term_count == 4
    assert execution.result.total_degree == 3
    assert execution.result.variables == ["x"]


@pytest.mark.parametrize(
    "request_data",
    [
        {"tool": "shell", "arguments": {"command": "dir"}},
        {"tool": "symbolic_expand", "arguments": {"expression": "x/y"}},
        {"tool": "symbolic_expand", "arguments": {"expression": "sin(x)"}},
        {"tool": "symbolic_expand", "arguments": {"expression": "x" * 201}},
        {
            "tool": "symbolic_expand",
            "arguments": {"expression": "x", "extra": 1},
        },
        {"tool": "symbolic_expand", "arguments": {}},
        {"tool": "symbolic_expand"},
    ],
)
def test_rejects_invalid_requests(orchestrator, request_data):
    with pytest.raises(ToolValidationError):
        orchestrator.execute(request_data)


def test_allowlist_is_explicit(orchestrator):
    assert orchestrator.allowed_tools == frozenset({"symbolic_expand"})


def test_worker_timeout_terminates_child():
    with pytest.raises(ToolTimeoutError):
        run_in_subprocess(_sleep_for, 5.0, 0.2)


def test_worker_returns_result():
    assert run_in_subprocess(_sleep_for, 0.01, 5.0) == {"slept": 0.01}
