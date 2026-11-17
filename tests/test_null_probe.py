"""A2 tests: null-reachability probe logic with a fake client (no generation)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from block15 import null_probe as NP
from block15 import order_v2_research as O
from block15 import skill_tools as T


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def health(self):
        return True

    def model_info(self):
        return {"digest": O.MODEL_DIGEST, "details": {"quantization_level": O.QUANTIZATION}}

    def chat_json(self, messages, schema, *, num_predict):
        self.calls += 1
        # Emit the configured content; vary label by form for the multi test.
        content = self.content
        if isinstance(content, dict):
            form = "F2_nullable" if "null" in json.dumps(schema.get("properties", {}).get("tool_request", {}).get("type", [])) else "F1_anyof"
            content = content[form]
        return SimpleNamespace(content=content, done_reason="stop",
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


def test_schemas_forms():
    s = NP.probe_schemas()
    assert "anyOf" in json.dumps(s["F1_anyof"]["properties"]["tool_request"])
    tr = s["F2_nullable"]["properties"]["tool_request"]
    assert isinstance(tr["type"], list) and "null" in tr["type"] and "object" in tr["type"]
    assert "anyOf" not in tr


def test_prompt_only_schema_differs():
    s = NP.probe_schemas()
    p1 = NP.build_prompt(NP.PROBE_TASKS[0], s["F1_anyof"])
    p2 = NP.build_prompt(NP.PROBE_TASKS[0], s["F2_nullable"])
    # Same task and instruction text; the embedded schema block is the only change.
    assert p1.split("\n\n")[0] == p2.split("\n\n")[0]
    assert p1.split("\n\n")[-1] == p2.split("\n\n")[-1]
    assert p1 != p2


def test_classify_request():
    assert NP.classify_request('{"tool_request": null}')["label"] == "null"
    assert NP.classify_request('{"tool_request": {"tool": "x"}}')["label"] == "object"
    assert NP.classify_request('{"missing_process": "no_tool_needed"}')["label"] == "missing"
    assert NP.classify_request("not json")["label"] == "unparseable"
    assert NP.classify_request(None)["label"] == "unparseable"
    cls = NP.classify_request('```json\n{"tool_request": null}\n```')
    assert cls["label"] == "null"


def test_run_probe_fake_client(tmp_path):
    client = FakeClient('{"tool_request": null, "missing_process": "no_tool_needed"}')
    rec = NP.run_probe(tmp_path, client=client, store=FakeStore())
    assert len(rec["results"]) == 8
    assert client.calls == 8
    summ = NP.summarize(rec)
    assert summ["n_cells"] == 8
    for form in ("F1_anyof", "F2_nullable"):
        assert summ["per_form"][form]["counts"] == {"null": 4}
        assert summ["per_form"][form]["null_emitted"] == 4
    assert list((tmp_path).glob(NP.RESULTS_PREFIX + "*.json"))


def test_report_details(tmp_path):
    client = FakeClient('{"tool_request": null}')
    rec = NP.run_probe(tmp_path, client=client, store=FakeStore())
    details = NP.report_details(rec)
    assert len(details) == 8
    for d in details:
        assert d["label"] == "null" and d["tool_request"] is None
        assert d["protocol_variant"] == "primary" and d["schema_enforced"] is True
        assert d["task"] in NP.PROBE_TASKS


def test_run_probe_mixed_labels(tmp_path):
    client = FakeClient({
        "F1_anyof": '{"tool_request": {"tool": "first_composite_quadratic"}}',
        "F2_nullable": '{"tool_request": null}',
    })
    rec = NP.run_probe(tmp_path, client=client, store=FakeStore())
    summ = NP.summarize(rec)
    assert summ["per_form"]["F1_anyof"]["counts"] == {"object": 4}
    assert summ["per_form"]["F2_nullable"]["counts"] == {"null": 4}
