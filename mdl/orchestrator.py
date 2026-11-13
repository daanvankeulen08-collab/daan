"""Strict allowlist and validation layer between the model and tools."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from pydantic import ValidationError

from .errors import ToolExecutionError, ToolValidationError
from .expr_parser import parse_expression
from .schemas import SymbolicExpandResult, ToolRequest
from .worker import _expand_target, run_in_subprocess

ALLOWED_TOOLS = frozenset({"symbolic_expand"})


@dataclass(frozen=True)
class ToolExecution:
    request: ToolRequest
    result: SymbolicExpandResult
    latency_ms: float
    isolation: str = "spawned subprocess with hard timeout"


class ToolOrchestrator:
    def __init__(self, timeout_s: float = 5.0) -> None:
        self.timeout_s = timeout_s

    @property
    def allowed_tools(self) -> frozenset[str]:
        return ALLOWED_TOOLS

    def validate(self, request: ToolRequest | dict) -> ToolRequest:
        """Validate schema, allowlist and expression grammar before execution."""

        if isinstance(request, ToolRequest):
            parsed = request
        else:
            try:
                parsed = ToolRequest.model_validate(request)
            except ValidationError as exc:
                raise ToolValidationError(
                    f"invalid tool request schema: {exc}"
                ) from exc

        if parsed.tool not in ALLOWED_TOOLS:
            raise ToolValidationError(f"tool {parsed.tool!r} is not allowlisted")

        # Grammar/limit validation happens in the parent process, before any
        # child process or SymPy expansion is started.
        parse_expression(parsed.arguments.expression)
        return parsed

    def execute(self, request: ToolRequest | dict) -> ToolExecution:
        parsed = self.validate(request)
        started = perf_counter()
        raw = run_in_subprocess(
            _expand_target, parsed.arguments.expression, self.timeout_s
        )
        latency_ms = (perf_counter() - started) * 1000.0

        try:
            result = SymbolicExpandResult.model_validate(raw)
        except ValidationError as exc:
            raise ToolExecutionError(
                f"tool produced an invalid result: {exc}"
            ) from exc

        return ToolExecution(
            request=parsed, result=result, latency_ms=latency_ms
        )
