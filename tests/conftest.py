"""Shared fixtures and a scripted fake LFM3 client."""

from __future__ import annotations

import json

import pytest

from mdl.config import load_settings
from mdl.logging_store import ResearchStore
from mdl.ollama_client import ModelResponse


class FakeClient:
    """Deterministic stand-in for OllamaClient.

    ``script`` is a list of dicts (valid model answers) or exceptions raised
    from ``chat_json``.  Each call consumes one item.
    """

    def __init__(
        self,
        script: list,
        model: str = "fake:lfm3",
        digest: str = "sha256:fake-digest",
    ) -> None:
        self.script = list(script)
        self.model = model
        self.digest = digest
        self.calls: list[dict] = []

    def model_info(self) -> dict:
        return {"name": self.model, "digest": self.digest}

    def chat_json(self, messages, schema, *, num_predict: int) -> ModelResponse:
        self.calls.append(
            {"messages": messages, "schema": schema, "num_predict": num_predict}
        )
        if not self.script:
            raise AssertionError("FakeClient script exhausted")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        content = json.dumps(item)
        return ModelResponse(
            content=content,
            parsed=item,
            prompt_eval_count=10,
            eval_count=20,
            total_duration_ns=1_000_000,
            load_duration_ns=0,
            eval_duration_ns=500_000,
            wall_ms=1.0,
            raw={},
        )


HYPOTHESIS = {
    "statement": (
        "The expansion of (x + 1)**8 has only non-negative integer coefficients."
    ),
    "assumptions": [
        "x is a symbolic variable",
        "integer arithmetic is exact",
    ],
    "variables": ["x"],
}

PLAN = {
    "objective": "Expand the polynomial and inspect its coefficients.",
    "steps": [
        "Validate the expression",
        "Expand it with symbolic_expand",
        "Inspect the resulting coefficients",
    ],
    "tool": "symbolic_expand",
    "expected_outcome": "A degree-8 polynomial with non-negative coefficients.",
}

REQUEST = {"tool": "symbolic_expand", "arguments": {"expression": "(x + 1)**8"}}

INTERPRETATION = {
    "conclusion": (
        "All nine coefficients are non-negative integers, so the hypothesis "
        "is supported for this expression."
    ),
    "supports_hypothesis": True,
    "observed_outcome": (
        "The expansion has nine terms and every coefficient is a positive "
        "integer."
    ),
    "uncertainties": ["Only the exponent 8 was checked."],
    "follow_up": ["Test several other exponents and record the coefficients."],
}

EXPECTED_EXPANSION = (
    "x**8 + 8*x**7 + 28*x**6 + 56*x**5 + 70*x**4 + 56*x**3 + 28*x**2 + 8*x + 1"
)


@pytest.fixture
def settings(tmp_path):
    return load_settings(
        db_path=tmp_path / "mdl.sqlite3",
        jsonl_path=tmp_path / "research_events.jsonl",
    )


@pytest.fixture
def store(settings):
    instance = ResearchStore(settings.db_path, settings.jsonl_path)
    yield instance
    instance.close()
