"""Tests for the memory-retry pilot (no network, no data/ fixtures)."""

from __future__ import annotations

import json

import httpx
import pytest

from block15.memory_pilot import (
    A1A_TASK_ID,
    C_TASK_ID,
    CALL_BUDGET,
    CONDITIONS,
    MEMORY_LEVELS,
    PLANNED_CALLS,
    MemorySource,
    answer_present_in_memory,
    build_retry_prompt,
    compress_memory,
    evaluate_success_criterion,
    extract_answer_ints,
    _pilot_paths,
    score_attempt,
    strict_audit_a1a,
    strict_audit_c,
)
from block15.round3 import _number_present, independent_check
from block15.round3_tasks import RUN_ORDER
from mdl.config import load_settings
from mdl.errors import ModelOutputError
from mdl.ollama_client import OllamaClient

TASKS = {task.id: task for task in RUN_ORDER}
A1A = TASKS[A1A_TASK_ID]
C = TASKS[C_TASK_ID]

WRONG_SOURCE = MemorySource(
    final="The coefficient is -21.",
    derivation=(
        "Expand the binomial coefficient and collect the x^4 term. "
        + "padding " * 40
        + "The derivation reaches 4860 before the final line."
    ),
    raw_content=json.dumps(
        {
            "answer": "The coefficient is -21.",
            "reasoning": (
                "Expand the binomial coefficient and collect the x^4 term. "
                + "padding " * 40
                + "The derivation reaches 4860 before the final line."
            ),
            "confidence": 0.6,
            "uncertainty": "",
        }
    ),
)

C_WRONG_SOURCE = MemorySource(
    final="The hypothesis is not proved.",
    derivation="Checking several values does not establish a proof.",
    raw_content=json.dumps(
        {
            "derivation": ["Checking several values does not establish a proof."],
            "final_answer": "The hypothesis is not proved.",
            "uncertainty": "",
            "confidence": 0.5,
        }
    ),
)


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ("N", "0", "1", "2", "3", "4"))
def test_compressor_is_deterministic(level):
    first = compress_memory(level, WRONG_SOURCE)
    second = compress_memory(level, WRONG_SOURCE)
    assert first == second


def test_compressor_unknown_level_rejected():
    with pytest.raises(ValueError):
        compress_memory("5", WRONG_SOURCE)


def test_compressor_level_contents_and_ordering():
    level_1 = compress_memory("1", WRONG_SOURCE)
    level_2 = compress_memory("2", WRONG_SOURCE)
    level_3 = compress_memory("3", WRONG_SOURCE)
    level_4 = compress_memory("4", WRONG_SOURCE)

    assert level_1 == WRONG_SOURCE.final
    assert level_2 == WRONG_SOURCE.final + "\n" + WRONG_SOURCE.derivation[-200:]
    assert level_3 == WRONG_SOURCE.final + "\n" + WRONG_SOURCE.derivation
    assert level_4 == WRONG_SOURCE.raw_content
    assert len(level_1) <= len(level_2) <= len(level_3) <= len(level_4)


def test_compressor_short_derivation_keeps_whole_tail():
    source = MemorySource(
        final="wrong", derivation="short derivation", raw_content="{}"
    )
    assert compress_memory("2", source) == "wrong\nshort derivation"


def test_compressor_without_source_is_empty_for_memory_levels():
    for level in MEMORY_LEVELS:
        assert compress_memory(level, None) == ""


def test_level_n_prompt_is_byte_identical_to_attempt_one():
    task = C
    prompt = build_retry_prompt(task.prompt, "N", "")
    assert prompt == task.prompt
    assert prompt.encode("utf-8") == task.prompt.encode("utf-8")


def test_level_zero_has_label_and_no_memory_block():
    prompt = build_retry_prompt(C.prompt, "0", "ignored")
    block = prompt[len(C.prompt) :]
    assert "Your previous attempt was judged incorrect." in block
    assert "<previous_attempt>" not in block
    assert "No further information is available." not in block
    assert "ignored" not in prompt


def test_injection_wording_is_fixed_for_levels_one_to_four():
    for level in MEMORY_LEVELS:
        prompt = build_retry_prompt(C.prompt, level, "MEMORY")
        expected = (
            C.prompt
            + "\n\n"
            + "Your previous attempt was judged incorrect. "
            + "No further information is available.\n"
            + "<previous_attempt>\nMEMORY\n</previous_attempt>\n"
            + "Attempt the task again."
        )
        assert prompt == expected


def test_no_expected_answer_in_any_injected_block_for_c():
    """The harness must never add the C facts; only a previous model answer can."""

    for level in ("0", "1", "2", "3", "4"):
        prompt = build_retry_prompt(C.prompt, level, compress_memory(level, C_WRONG_SOURCE))
        block = prompt[len(C.prompt) :]
        for token in (7, 1333, 31, 43):
            assert not _number_present(block, token)
        assert C.expected not in block
        assert "31*43" not in block


# ---------------------------------------------------------------------------
# Copy-possible detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("memory", "token", "expected"),
    [
        ("value 1333", 1333, True),
        ("value 13330", 1333, False),
        ("value 1,333", 1333, True),
        ("value 4860", 4860, True),
        ("value 48600", 4860, False),
        ("no number here", 1333, False),
    ],
)
def test_answer_present_in_memory_exact_integer(memory, token, expected):
    assert answer_present_in_memory("1", memory, token) is expected


def test_answer_present_in_memory_false_without_memory_levels():
    assert answer_present_in_memory("N", "1333", 1333) is False
    assert answer_present_in_memory("0", "1333", 1333) is False
    assert answer_present_in_memory("4", "", 1333) is False


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------


def test_model_output_error_defaults_are_backward_compatible():
    exc = ModelOutputError("boom")
    assert str(exc) == "boom"
    assert exc.raw_content is None
    assert exc.done_reason is None
    assert exc.prompt_eval_count is None
    assert exc.eval_count is None


def test_model_output_error_carries_failure_metadata():
    exc = ModelOutputError(
        "boom",
        raw_content='{"broken": ',
        done_reason="length",
        prompt_eval_count=12,
        eval_count=34,
    )
    assert exc.raw_content == '{"broken": '
    assert exc.done_reason == "length"
    assert exc.prompt_eval_count == 12
    assert exc.eval_count == 34


def _client(tmp_path, monkeypatch, payload: dict) -> OllamaClient:
    settings = load_settings(
        model="lfm3base:latest",
        db_path=tmp_path / "unused.sqlite3",
        jsonl_path=tmp_path / "unused.jsonl",
    )
    client = OllamaClient(settings)
    monkeypatch.setattr(
        client,
        "_post",
        lambda path, body: httpx.Response(200, json=payload),
    )
    return client


def test_chat_json_success_unchanged(tmp_path, monkeypatch):
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
    client = _client(tmp_path, monkeypatch, payload)
    try:
        response = client.chat_json(
            [{"role": "user", "content": "x"}], None, num_predict=10
        )
    finally:
        client.close()
    assert response.content == content
    assert response.parsed == {"answer": "4860", "confidence": 0.9}
    assert response.prompt_eval_count == 11
    assert response.eval_count == 22
    assert response.done_reason == "stop"
    assert response.raw == payload


def test_chat_json_parse_failure_preserves_raw_output_and_metadata(
    tmp_path, monkeypatch
):
    content = '{"answer": "unterminated'
    payload = {
        "message": {"content": content},
        "prompt_eval_count": 7,
        "eval_count": 0,
        "done_reason": "length",
    }
    client = _client(tmp_path, monkeypatch, payload)
    try:
        with pytest.raises(ModelOutputError) as info:
            client.chat_json(
                [{"role": "user", "content": "x"}], None, num_predict=10
            )
    finally:
        client.close()
    exc = info.value
    assert exc.raw_content == content
    assert exc.done_reason == "length"
    assert exc.prompt_eval_count == 7
    assert exc.eval_count == 0


def test_chat_json_empty_content_preserves_empty_raw_output(tmp_path, monkeypatch):
    payload = {
        "message": {"content": ""},
        "prompt_eval_count": 3,
        "eval_count": 0,
        "done_reason": "stop",
    }
    client = _client(tmp_path, monkeypatch, payload)
    try:
        with pytest.raises(ModelOutputError) as info:
            client.chat_json(
                [{"role": "user", "content": "x"}], None, num_predict=10
            )
    finally:
        client.close()
    assert info.value.raw_content == ""
    assert info.value.done_reason == "stop"
    assert info.value.prompt_eval_count == 3


# ---------------------------------------------------------------------------
# Scoring and audit
# ---------------------------------------------------------------------------


def test_a1a_reward_uses_stored_objective_status():
    final = {
        "answer": "4860",
        "reasoning": "Expanded with the binomial theorem.",
        "confidence": 0.9,
        "uncertainty": "",
    }
    verification = independent_check(A1A, final, None)
    scored = score_attempt(A1A, final, verification)
    assert scored["stored_status"] == "objective_pass"
    assert scored["binary_reward"] is True
    assert scored["audit_passed"] is True
    assert scored["audit"]["extracted_answer_ints"] == [4860]


def test_a1a_stricter_audit_rejects_ambiguous_answer_but_keeps_reward():
    final = {
        "answer": "The derivation reaches 4860 but my final value is -21.",
        "reasoning": "Arithmetic slip.",
        "confidence": 0.5,
        "uncertainty": "",
    }
    verification = independent_check(A1A, final, None)
    scored = score_attempt(A1A, final, verification)
    assert scored["binary_reward"] is True
    assert scored["stored_status"] == "objective_pass"
    assert scored["audit_passed"] is False
    assert scored["audit"]["extracted_answer_ints"] == [-21, 4860]


def test_extract_answer_ints_does_not_split_decimals_or_thousands():
    assert extract_answer_ints("The value is 4,860.") == [4860]
    assert extract_answer_ints("The value is 4860.0") == []
    assert extract_answer_ints("The value is \u221221.") == [-21]


def test_strict_audit_a1a_requires_exact_single_value():
    good = {"answer": "4860"} | {
        "reasoning": "",
        "confidence": 0.9,
        "uncertainty": "",
    }
    bad = {"answer": "4860 or 4861"} | {
        "reasoning": "",
        "confidence": 0.9,
        "uncertainty": "",
    }
    assert strict_audit_a1a(good)["audit_passed"] is True
    assert strict_audit_a1a(bad)["audit_passed"] is False


def test_c_composite_is_new_and_stored_status_stays_manual_review():
    final = {
        "derivation": ["The first counterexample is n = 7."],
        "final_answer": "n = 7 gives 1333 = 31*43.",
        "uncertainty": "",
        "confidence": 0.8,
    }
    verification = independent_check(C, final, None)
    scored = score_attempt(C, final, verification)
    assert scored["stored_status"] == "manual_review_required"
    assert scored["composite"] == {
        "final_contains_first_n": True,
        "final_contains_counterexample_value": True,
        "final_contains_factors_31_43": True,
    }
    assert scored["binary_reward"] is True
    assert scored["audit_passed"] is True


def test_c_composite_fails_without_the_smallest_n():
    final = {
        "derivation": ["A counterexample exists."],
        "final_answer": "1333 = 31*43.",
        "uncertainty": "",
        "confidence": 0.8,
    }
    verification = independent_check(C, final, None)
    scored = score_attempt(C, final, verification)
    assert scored["stored_status"] == "manual_review_required"
    assert scored["composite"]["final_contains_first_n"] is False
    assert scored["binary_reward"] is False
    assert scored["audit_passed"] is False


def test_strict_audit_c_requires_sympy_factors_and_all_numbers():
    good = {"answer": "n=7, 1333 = 31*43"}
    missing = {"answer": "1333 = 31*43"}
    assert strict_audit_c(good)["audit_passed"] is True
    assert strict_audit_c(missing)["audit_passed"] is False
    assert strict_audit_c(good)["factorint_1333"] == {"31": 1, "43": 1}


# ---------------------------------------------------------------------------
# Success criterion and file naming
# ---------------------------------------------------------------------------


def _criterion_fixture(n_rewards, audit_success):
    conditions = {
        condition: {
            "rewards": [False, False, False],
            "audit_success_at_3": False,
        }
        for condition in CONDITIONS
    }
    conditions["N"]["rewards"] = list(n_rewards)
    for level, value in audit_success.items():
        conditions[level]["audit_success_at_3"] = value
    return {C_TASK_ID: {"conditions": conditions}}


def test_success_criterion_signal_when_n_fails_and_level_passes():
    verdict = evaluate_success_criterion(
        _criterion_fixture([False, False, False], {"2": True})
    )
    assert verdict["condition_N_fails_all_3"] is True
    assert verdict["compression_levels_with_composite_and_audit"] == ["2"]
    assert verdict["signal"] is True


def test_success_criterion_no_signal_if_n_passes():
    verdict = evaluate_success_criterion(
        _criterion_fixture([True, False, False], {"2": True})
    )
    assert verdict["signal"] is False


def test_success_criterion_level_zero_is_only_sensitivity():
    verdict = evaluate_success_criterion(
        _criterion_fixture([False, False, False], {"0": True})
    )
    assert verdict["signal"] is False
    assert verdict["sensitivity_level_0_composite_and_audit"] is True
    assert verdict["sensitivity_signal_including_level_0"] is True


def test_success_criterion_no_signal_without_composite_audit_pass():
    verdict = evaluate_success_criterion(
        _criterion_fixture([False, False, False], {})
    )
    assert verdict["signal"] is False


def test_call_plan_and_guards_are_fixed():
    assert PLANNED_CALLS == 26
    assert CALL_BUDGET == 30


def test_results_filename_cannot_match_round3_glob():
    paths = _pilot_paths("20261115T120000Z")
    assert paths.results.name == "block15_pilot_memory_results_20261115T120000Z.json"
    assert not paths.results.match("block15_round3_results_*.json")
    assert paths.db.name == "block15_pilot_memory.sqlite3"
    assert paths.jsonl.name == "block15_pilot_memory_events.jsonl"
