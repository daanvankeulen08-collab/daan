"""Tests for the null micro-probe (no generation)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from block15 import null_microprobe as NMP


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def health(self):
        return True

    def model_info(self):
        from block15 import order_v2_research as O
        return {"digest": O.MODEL_DIGEST, "details": {"quantization_level": O.QUANTIZATION}}

    def chat_json(self, messages, schema, *, num_predict):
        self.calls += 1
        return SimpleNamespace(content=self.content, done_reason="stop",
                               prompt_eval_count=10, eval_count=20,
                               protocol_variant="primary", schema_enforced=True,
                               think_sent=False)

    def close(self):
        pass


class FakeStore:
    def create_experiment(self, **kw):
        return "fake"

    def log_step(self, *a, **kw):
        pass

    def close(self):
        pass


def test_micro_schemas():
    s = NMP.micro_schemas()
    assert s["N1_null_only"]["properties"]["tool_request"] == {"type": "null"}
    assert "tool_request" in s["N1_null_only"]["required"]
    assert "tool_request" not in s["N2_optional_anyof"]["required"]
    assert "anyOf" in s["N2_optional_anyof"]["properties"]["tool_request"]


def test_classify():
    assert NMP.classify('{"tool_request": null}')["label"] == "null"
    assert NMP.classify('{"tool_request": {"tool": "x"}}')["label"] == "object"
    assert NMP.classify('{"missing_process": "no_tool_needed"}')["label"] == "omitted"
    assert NMP.classify("not json")["label"] == "unparseable"
    assert NMP.classify(None)["label"] == "unparseable"


def test_run_and_summarize(tmp_path):
    client = FakeClient('{"tool_request": null, "missing_process": "no_tool_needed"}')
    rec = NMP.run_probe(tmp_path, client=client, store=FakeStore())
    assert len(rec["results"]) == 8 and client.calls == 8
    summ = NMP.summarize(rec)
    assert summ["n_cells"] == 8
    for form in ("N1_null_only", "N2_optional_anyof"):
        assert summ["per_form"][form]["counts"] == {"null": 4}


def test_run_mixed_omitted_object(tmp_path):
    client = FakeClient('{"tool_request": {"tool": "first_composite_quadratic"}}')
    rec = NMP.run_probe(tmp_path, client=client, store=FakeStore())
    summ = NMP.summarize(rec)
    for form in ("N1_null_only", "N2_optional_anyof"):
        assert summ["per_form"][form]["counts"] == {"object": 4}
