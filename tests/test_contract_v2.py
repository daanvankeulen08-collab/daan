"""Contract v2 and format-variant provenance tests.

Every fixture is inline.  No file under ``data/`` is read.
"""

from __future__ import annotations

import copy
import inspect
import json
import re

import httpx
import pytest

from block15 import contract_v2 as contract
from block15.tasks import SYSTEM_PROMPT as ROUND3_SYSTEM_PROMPT
from mdl.config import load_settings
from mdl.errors import ModelOutputError
from mdl.ollama_client import ModelResponse, OllamaClient

EXPECTED_ORDER = {
    "answer_first": ["final_answer", "derivation", "uncertainty", "confidence"],
    "derivation_first": ["derivation", "final_answer", "uncertainty", "confidence"],
}

EXPECTED_ANNOTATION = {
    "derivation": "derivation (array of short, independently checkable steps)",
    "final_answer": "final_answer (string)",
    "uncertainty": "uncertainty (string)",
    "confidence": "confidence (number from 0 to 1)",
}


def _instruction_fields(instruction: str) -> list[str]:
    """Parse the declared field list instead of eyeballing the string."""
    marker = "exactly these fields, in this order:"
    start = instruction.index(marker) + len(marker)
    clause = instruction[start:].split(". ", 1)[0]
    return re.findall(r"([a-z_]+) \(", clause)


def _conforming(schema: dict) -> dict:
    values = {
        "derivation": ["step one", "step two"],
        "final_answer": "42",
        "uncertainty": "none",
        "confidence": 0.5,
    }
    return {name: copy.deepcopy(values[name]) for name in schema["required"]}


# ---------------------------------------------------------------------------
# 1. Instruction order must equal schema required order, in both arms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arm", "instruction", "schema"),
    [
        ("answer_first", contract.ANSWER_FIRST_INSTRUCTION, contract.ANSWER_FIRST_V2),
        (
            "derivation_first",
            contract.DERIVATION_FIRST_INSTRUCTION,
            contract.DERIVATION_FIRST_V2,
        ),
    ],
)
def test_instruction_order_matches_schema_required_order(arm, instruction, schema):
    parsed = _instruction_fields(instruction)
    assert parsed == EXPECTED_ORDER[arm]
    assert parsed == schema["required"]
    assert list(schema["properties"]) == schema["required"]


@pytest.mark.parametrize(
    ("instruction", "expected"),
    [
        (
            contract.ANSWER_FIRST_INSTRUCTION,
            [
                "final_answer (string)",
                "derivation (array of short, independently checkable steps)",
                "uncertainty (string)",
                "confidence (number from 0 to 1)",
            ],
        ),
        (
            contract.DERIVATION_FIRST_INSTRUCTION,
            [
                "derivation (array of short, independently checkable steps)",
                "final_answer (string)",
                "uncertainty (string)",
                "confidence (number from 0 to 1)",
            ],
        ),
    ],
)
def test_instruction_annotates_every_field_with_its_type(instruction, expected):
    for fragment in EXPECTED_ANNOTATION.values():
        assert fragment in instruction
    positions = [instruction.index(fragment) for fragment in expected]
    assert positions == sorted(positions)


def test_answer_first_omits_derivation_first_clause():
    assert "Work through the derivation first" in contract.DERIVATION_FIRST_INSTRUCTION
    assert "Work through the derivation first" not in contract.ANSWER_FIRST_INSTRUCTION


def test_system_prompt_is_round3_verbatim():
    assert contract.SYSTEM_PROMPT_V2 == ROUND3_SYSTEM_PROMPT
    assert "You are LFM3" in contract.SYSTEM_PROMPT_V2
    assert "at most 120 words" in contract.SYSTEM_PROMPT_V2
    assert "Do not claim to have used a tool" in contract.SYSTEM_PROMPT_V2


def test_both_arms_have_identical_constraints():
    answer = contract.ANSWER_FIRST_V2
    derivation = contract.DERIVATION_FIRST_V2
    assert answer["required"] == EXPECTED_ORDER["answer_first"]
    assert derivation["required"] == EXPECTED_ORDER["derivation_first"]
    assert set(answer["properties"]) == set(derivation["properties"])
    for name in answer["properties"]:
        assert answer["properties"][name] == derivation["properties"][name]
    assert answer["type"] == derivation["type"] == "object"
    assert answer["additionalProperties"] is False
    assert derivation["additionalProperties"] is False


# ---------------------------------------------------------------------------
# 2. Schema serialization preserves insertion order; no sort_keys on the path
# ---------------------------------------------------------------------------


def _json_pairs(value: object):
    return json.loads(json.dumps(value), object_pairs_hook=lambda pairs: pairs)


@pytest.mark.parametrize(
    ("arm", "schema"),
    [
        ("answer_first", contract.ANSWER_FIRST_V2),
        ("derivation_first", contract.DERIVATION_FIRST_V2),
    ],
)
def test_json_dumps_preserves_property_insertion_order(arm, schema):
    top = dict(_json_pairs(schema))
    assert list(top) == ["type", "additionalProperties", "required", "properties"]
    assert top["required"] == EXPECTED_ORDER[arm]
    assert list(dict(top["properties"])) == EXPECTED_ORDER[arm]


def test_schema_path_does_not_apply_sort_keys(tmp_path, monkeypatch):
    assert "sort_keys" not in inspect.getsource(contract)
    assert "sort_keys" not in inspect.getsource(OllamaClient.chat_json)
    assert "sort_keys" not in inspect.getsource(OllamaClient._post)

    client = _new_client(tmp_path)
    captured: list[dict] = []

    def fake_post(path, payload):
        captured.append(payload)
        return httpx.Response(
            200,
            json={"message": {"content": '{"x": 1}'}, "done_reason": "stop"},
        )

    monkeypatch.setattr(client, "_post", fake_post)
    try:
        client.chat_json(
            [{"role": "user", "content": "x"}],
            contract.ANSWER_FIRST_V2,
            num_predict=8,
        )
    finally:
        client.close()

    assert len(captured) == 1
    sent = captured[0]["format"]
    assert sent is contract.ANSWER_FIRST_V2
    assert list(sent["properties"]) == contract.ANSWER_FIRST_V2["required"]
    assert list(dict(dict(_json_pairs(sent))["properties"])) == (
        contract.ANSWER_FIRST_V2["required"]
    )


# ---------------------------------------------------------------------------
# 3. validate_v2 rejects every cheap near miss, without mutating the object
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda obj: obj.__setitem__("derivation", ["x" * 501]),
        lambda obj: obj.__setitem__("derivation", ["x"] * 9),
        lambda obj: obj.__setitem__("derivation", []),
        lambda obj: obj.__setitem__("derivation", "x" * 4992),
        lambda obj: obj.__setitem__("final_answer", ""),
        lambda obj: obj.__setitem__("final_answer", "x" * 1401),
        lambda obj: obj.__setitem__("uncertainty", "x" * 701),
        lambda obj: obj.__setitem__("confidence", 100),
        lambda obj: obj.__setitem__("confidence", 2),
        lambda obj: obj.__setitem__("extra", "not allowed"),
        lambda obj: obj.pop("uncertainty"),
    ],
    ids=[
        "derivation_item_501_chars",
        "derivation_9_items",
        "derivation_0_items",
        "derivation_4992_char_string",
        "final_answer_empty",
        "final_answer_1401_chars",
        "uncertainty_701_chars",
        "confidence_100",
        "confidence_2",
        "extra_property",
        "missing_required_key",
    ],
)
def test_validate_v2_rejects(mutate):
    obj = _conforming(contract.DERIVATION_FIRST_V2)
    mutate(obj)
    snapshot = copy.deepcopy(obj)
    ok, violations = contract.validate_v2(obj, contract.DERIVATION_FIRST_V2)
    assert ok is False
    assert violations, "rejection must explain at least one violation"
    assert obj == snapshot, "validator must not repair, clamp, or coerce"


# ---------------------------------------------------------------------------
# 4. validate_v2 accepts conforming objects, including inclusive boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arm", "schema"),
    [
        ("answer_first", contract.ANSWER_FIRST_V2),
        ("derivation_first", contract.DERIVATION_FIRST_V2),
    ],
)
def test_validate_v2_accepts_conforming_object(arm, schema):
    obj = _conforming(schema)
    assert list(obj) == EXPECTED_ORDER[arm]
    ok, violations = contract.validate_v2(obj, schema)
    assert (ok, violations) == (True, [])


@pytest.mark.parametrize("confidence", [0, 1])
def test_validate_v2_accepts_inclusive_boundaries(confidence):
    obj = {
        "derivation": ["x" * 500] * 8,
        "final_answer": "x" * 1400,
        "uncertainty": "x" * 700,
        "confidence": confidence,
    }
    ok, violations = contract.validate_v2(obj, contract.DERIVATION_FIRST_V2)
    assert (ok, violations) == (True, [])


# ---------------------------------------------------------------------------
# 5. Forced HTTP fallbacks record the variant that actually succeeded
# ---------------------------------------------------------------------------


def _new_client(tmp_path) -> OllamaClient:
    settings = load_settings(
        model="fake:lfm3",
        db_path=tmp_path / "unused.sqlite3",
        jsonl_path=tmp_path / "unused.jsonl",
    )
    return OllamaClient(settings)


def _scripted_client(tmp_path, monkeypatch, statuses, content='{"x": 1}'):
    client = _new_client(tmp_path)
    calls: list[dict] = []
    queue = list(statuses)

    def fake_post(path, payload):
        calls.append(payload)
        status = queue.pop(0)
        if status >= 400:
            return httpx.Response(status, text=f"forced {status}")
        return httpx.Response(
            200,
            json={
                "message": {"content": content},
                "prompt_eval_count": 1,
                "eval_count": 1,
                "done_reason": "stop",
            },
        )

    monkeypatch.setattr(client, "_post", fake_post)
    return client, calls


def test_400_then_200_records_json_fallback(tmp_path, monkeypatch):
    client, calls = _scripted_client(tmp_path, monkeypatch, [400, 200])
    try:
        response = client.chat_json(
            [{"role": "user", "content": "x"}],
            contract.ANSWER_FIRST_V2,
            num_predict=8,
        )
    finally:
        client.close()

    assert len(calls) == 2
    assert calls[0]["format"] is contract.ANSWER_FIRST_V2
    assert calls[1]["format"] == "json"
    assert response.protocol_variant == "json_fallback"
    assert response.protocol_variant != "primary"
    assert response.schema_enforced is False
    assert response.think_sent is False


def test_400_400_200_records_json_without_think(tmp_path, monkeypatch):
    client, calls = _scripted_client(tmp_path, monkeypatch, [400, 400, 200])
    try:
        response = client.chat_json(
            [{"role": "user", "content": "x"}],
            contract.ANSWER_FIRST_V2,
            num_predict=8,
        )
    finally:
        client.close()

    assert len(calls) == 3
    assert "think" not in calls[2]
    assert response.protocol_variant == "json_without_think"
    assert response.schema_enforced is False
    assert response.think_sent is None


def test_parse_failure_after_fallback_still_records_variant(tmp_path, monkeypatch):
    client, calls = _scripted_client(
        tmp_path, monkeypatch, [400, 200], content='{"unterminated": '
    )
    try:
        with pytest.raises(ModelOutputError) as info:
            client.chat_json(
                [{"role": "user", "content": "x"}],
                contract.ANSWER_FIRST_V2,
                num_predict=8,
            )
    finally:
        client.close()

    assert len(calls) == 2
    assert info.value.protocol_variant == "json_fallback"
    assert info.value.schema_enforced is False
    assert info.value.think_sent is False


# ---------------------------------------------------------------------------
# 6. No-failure path behaves as before and the new fields have defaults
# ---------------------------------------------------------------------------


def test_model_response_and_error_defaults_are_additive():
    response = ModelResponse(
        content="{}",
        parsed={},
        prompt_eval_count=None,
        eval_count=None,
        total_duration_ns=None,
        load_duration_ns=None,
        eval_duration_ns=None,
        wall_ms=0.0,
        raw={},
    )
    assert response.protocol_variant == "primary"
    assert response.schema_enforced is False
    assert response.think_sent is None

    error = ModelOutputError("bad output")
    assert error.protocol_variant == "primary"
    assert error.schema_enforced is False
    assert error.think_sent is None


def test_primary_success_keeps_existing_fields_identical(tmp_path, monkeypatch):
    content = '{"answer": "4860", "confidence": 0.9}'
    payload = {
        "message": {"content": content},
        "prompt_eval_count": 11,
        "eval_count": 22,
        "done_reason": "stop",
        "total_duration": 1,
        "load_duration": 2,
        "eval_duration": 3,
    }
    client = _new_client(tmp_path)
    monkeypatch.setattr(
        client,
        "_post",
        lambda path, body: httpx.Response(200, json=payload),
    )
    try:
        response = client.chat_json(
            [{"role": "user", "content": "x"}],
            contract.ANSWER_FIRST_V2,
            num_predict=10,
        )
    finally:
        client.close()

    assert response.content == content
    assert response.parsed == {"answer": "4860", "confidence": 0.9}
    assert response.prompt_eval_count == 11
    assert response.eval_count == 22
    assert response.done_reason == "stop"
    assert response.raw == payload
    assert response.protocol_variant == "primary"
    assert response.schema_enforced is True
    assert response.think_sent is False
