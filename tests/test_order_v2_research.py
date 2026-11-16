"""Offline tests for the order-v2 harness.

No file under ``data/`` is read and no generation is performed.
"""

from __future__ import annotations

import json

import pytest

from block15 import ceiling_research as ceiling
from block15 import contract_v2 as contract
from block15 import heldout_research as heldout
from block15 import order_v2_research as study
from block15 import round3_tasks as round3
from block15.tasks import TASKS as ROUND3_BASE_TASKS


def test_task_count_and_kind_split():
    assert len(study.TASKS) == 30
    coeff = [t for t in study.TASKS if t.kind == "coefficient"]
    minimal = [t for t in study.TASKS if t.kind == "minimality"]
    assert len(coeff) == 15
    assert len(minimal) == 15
    assert len({t.id for t in study.TASKS}) == 30


def test_effective_instruction_is_neutral_plus_exactly_one_sentence():
    assert study.EFFECTIVE_INSTRUCTION_V2.startswith(
        contract.OUTPUT_INSTRUCTION_V2
    )
    remainder = study.EFFECTIVE_INSTRUCTION_V2[len(contract.OUTPUT_INSTRUCTION_V2) :]
    assert remainder.strip() == study.SCHEMA_ORDER_SENTENCE
    assert remainder.strip().count(".") == 1
    assert study.EFFECTIVE_INSTRUCTION_V2 == (
        contract.OUTPUT_INSTRUCTION_V2 + "\n\n" + study.SCHEMA_ORDER_SENTENCE
    )


def test_arms_use_contract_v2_schemas_only():
    assert study.SCHEMAS == {
        "answer_first": contract.ANSWER_FIRST_V2,
        "derivation_first": contract.DERIVATION_FIRST_V2,
    }
    assert study.ARMS == ("answer_first", "derivation_first")
    assert study.SCHEMAS["answer_first"]["required"] == [
        "final_answer",
        "derivation",
        "uncertainty",
        "confidence",
    ]
    assert study.SCHEMAS["derivation_first"]["required"] == [
        "derivation",
        "final_answer",
        "uncertainty",
        "confidence",
    ]


def test_sampling_and_budget_constants():
    assert study.MODEL == "lfm3base:latest"
    assert study.MODEL_DIGEST == (
        "b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d"
    )
    assert study.QUANTIZATION == "Q4_K_M"
    assert study.NUM_PREDICT == 1200
    assert study.THINK is False
    assert study.NUM_CTX == 8192
    assert study.TEMPERATURE == 0.1
    assert study.TOP_P == 1.0
    assert study.REPEAT_PENALTY == 1.1
    assert study.SEED == 42
    assert study.KEEP_ALIVE == "10m"
    assert study.MAX_CALLS == 70
    assert study.MAX_RUNTIME_S == 5400.0
    assert study.MIN_FREE_MB == 450.0
    assert study.PLANNED_CALLS == 60


def test_frozen_and_live_manifests_are_disjoint_and_new_artifacts_excluded():
    frozen = set(study.frozen_paths())
    live = set(study.live_paths())
    assert frozen.isdisjoint(live)
    assert "block15/ceiling_research.py" in frozen
    assert "block15/heldout_research.py" in frozen
    assert "block15/contract_v2.py" in live
    assert "block15/order_v2_research.py" in live
    assert "PREREG_ORDER_V2.md" not in frozen
    assert "REPORT_ORDER_V2.md" not in frozen
    assert not any(p.startswith("data/block15_order_v2_") for p in frozen)
    assert not any("__pycache__" in p or p.endswith(".pyc") for p in frozen | live)


def test_frozen_byte_identity_verifies_at_baseline():
    result = study.verify_protected()
    assert result["frozen_byte_identical"] is True
    assert result["frozen_differences"] == {}
    assert result["frozen_path_count"] == result["frozen_baseline_path_count"]


def test_live_before_after_never_claims_all_unchanged():
    result = study.verify_protected()
    statuses = {v["status"] for v in result["live_rows"].values()}
    assert "changed" in statuses or "new" in statuses
    assert result["live_rows"]["block15/contract_v2.py"]["status"] == "changed"
    assert result["live_rows"]["block15/order_v2_research.py"]["status"] == "new"


def test_all_ground_truth_matches_frozen_hash_and_sympy():
    truth = study.ground_truth_manifest()
    assert study._sha256_json(truth) == study.FROZEN_GROUND_TRUTH_SHA256
    assert len(truth) == 30
    for task in study.TASKS:
        t = truth[task.id]
        if task.kind == "coefficient":
            assert t["coefficient"] == task.expected_coefficient
            assert len(t["answer_tokens"]) == 1
        else:
            assert t["n"] == task.expected_n
            assert t["value"] == task.expected_value
            assert t["primes"] == list(task.expected_primes)
            assert len(t["primes"]) == 2


def test_all_prompt_hashes_frozen():
    for task in study.TASKS:
        assert study._sha256_text(task.prompt) == study.FROZEN_PROMPT_SHA256[task.id]
    assert task.prompt.endswith(study.SCHEMA_ORDER_SENTENCE)


def test_no_ground_truth_token_in_any_prompt():
    truth = study.ground_truth_manifest()
    for task in study.TASKS:
        check = study.copy_possible(task, truth[task.id])
        assert check["copy_possible"] is False, task.id
        assert all(v is False for v in check["token_present_in_prompt"].values())


def test_tasks_independent_of_round3_h1_h5_and_c01_m08():
    new_questions = {t.question.strip() for t in study.TASKS}
    old_questions = {t.math_question.strip() for t in round3.RUN_ORDER}
    old_questions |= {t.question.strip() for t in heldout.TASKS}
    old_questions |= {t.question.strip() for t in ceiling.TASKS}
    old_questions |= {t.prompt.strip() for t in ROUND3_BASE_TASKS}
    assert new_questions.isdisjoint(old_questions)

    old_coeff = {(t.expression, t.power) for t in ceiling.TASKS + heldout.TASKS}
    old_coeff |= {
        (t.expression, t.power)
        for t in ceiling.TASKS + heldout.TASKS
        if t.expression is not None
    }
    new_coeff = {(t.expression, t.power) for t in study.TASKS if t.expression}
    assert new_coeff.isdisjoint({c for c in old_coeff if c[0] is not None})

    old_min = {(t.a, t.b, t.c) for t in ceiling.TASKS + heldout.TASKS}
    new_min = {(t.a, t.b, t.c) for t in study.TASKS if t.kind == "minimality"}
    assert new_min.isdisjoint(old_min)


def test_coefficient_audit_primary_is_presence_not_strict_set():
    truth = study.ground_truth_manifest()
    task = next(t for t in study.TASKS if t.id == "V2C01_coeff_x_plus_4_pow8_x5")
    audit = study.audit_answer(task, truth[task.id], "the coefficient is 3,584")
    assert audit["audit_passed"] is True
    assert audit["exact_value_present"] is True
    audit2 = study.audit_answer(
        task, truth[task.id], "coefficients are 7 and 3584 and 9"
    )
    assert audit2["audit_passed"] is True
    assert audit2["strict_single_int"] is False
    audit3 = study.audit_answer(task, truth[task.id], "I cannot tell")
    assert audit3["audit_passed"] is False


def test_minimality_audit_requires_all_tokens():
    truth = study.ground_truth_manifest()
    task = next(
        t for t in study.TASKS if t.id == "V2M01_minimal_n2_plus_5n_plus_1217"
    )
    ok = study.audit_answer(
        task, truth[task.id], "n = 3; value = 1241; factors = 17 and 73"
    )
    assert ok["audit_passed"] is True
    missing = study.audit_answer(
        task, truth[task.id], "n = 3; value = 1241; factor = 17"
    )
    assert missing["audit_passed"] is False
    none = study.audit_answer(task, truth[task.id], None)
    assert none["audit_passed"] is False


def test_fresh_parse_preserves_wire_key_order():
    raw = 'prefix {"final_answer": "x", "derivation": ["a"], "uncertainty": "u", "confidence": 0.5} trailing'
    parsed = study.fresh_parse(raw)
    assert contract.emitted_key_order(parsed) == (
        "final_answer",
        "derivation",
        "uncertainty",
        "confidence",
    )
    assert study.fresh_parse("not json") is None
    assert study.fresh_parse(None) is None
    assert study.fresh_parse('```json\n{"a": 1}\n```') == {"a": 1}


def test_failure_partition_total_matches_cells():
    row = {
        "status": "ok",
        "parseable": True,
        "validate_v2_ok": True,
        "done_reason": "stop",
        "audit_passed": True,
        "confidence_raw": 0.5,
        "copy_possible": False,
        "primary_correct": True,
    }
    assert study._failure_mode(row) == "primary_correct"
    assert study._failure_flags(row) == []
    assert study._truncation_invalid(row) is False
    truncated = {**row, "done_reason": "length", "parseable": False}
    assert study._truncation_invalid(truncated) is True
    assert "truncated" in study._failure_flags(truncated)


def test_mcnemar_exact_known_values():
    assert study._mcnemar_exact(0, 0) == 1.0
    assert study._mcnemar_exact(3, 0) == pytest.approx(0.25)
    assert study._mcnemar_exact(0, 3) == pytest.approx(0.25)
    assert study._mcnemar_exact(1, 1) == 1.0
