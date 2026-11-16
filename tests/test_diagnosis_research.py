"""Offline tests for the diagnosis-guided retry harness."""

from __future__ import annotations

import pytest

from block15 import diagnosis_research as D
from block15 import order_v2_research as O


def test_twelve_failures_and_classification():
    assert len(D.FAILURE_IDS) == 12
    assert set(D.FAILURE_IDS) == set(D.CLASSIFICATION)
    dist = {
        c: sum(1 for v in D.CLASSIFICATION.values() if v["class"] == c)
        for c in {v["class"] for v in D.CLASSIFICATION.values()}
    }
    assert dist == {
        "NO_SEARCH": 9,
        "ARITHMETIC_ERROR": 1,
        "TRUNCATION": 1,
        "UNCLASSIFIED": 1,
    }
    assert D.CLASSIFICATION["V2M02_minimal_n2_plus_7n_plus_1163"]["class"] == "ARITHMETIC_ERROR"
    assert D.CLASSIFICATION["V2M08_minimal_n2_plus_n_plus_1487"]["class"] == "TRUNCATION"
    assert D.CLASSIFICATION["V2C02_coeff_2x_minus_7_pow6_x4"]["class"] == "UNCLASSIFIED"


def test_arithmetic_error_evidence_verified_by_sympy():
    f = D.TASK_BY_ID["V2M02_minimal_n2_plus_7n_plus_1163"]
    # derivation claimed f(4)=1217; SymPy from parameters gives 1207
    assert f.a * 4 * 4 + f.b * 4 + f.c == 1207
    assert O.ground_truth_manifest()["V2M02_minimal_n2_plus_7n_plus_1163"]["value"] == 1207


def test_oracle_text_leaks_no_ground_truth():
    checks = D.verify_oracle_no_gt()
    assert len(checks) == 12
    for tid, c in checks.items():
        assert c["copy"]["copy_possible"] is False
        assert c["oracle_sha256"]


def test_no_search_locus_is_not_a_ground_truth_token():
    gt = O.ground_truth_manifest()
    for tid, c in D.CLASSIFICATION.items():
        if c["class"] == "NO_SEARCH":
            locus = c["locus"]
            assert locus not in gt[tid]["answer_tokens"]


def test_prompt_construction():
    task = D.TASK_BY_ID["V2M03_minimal_n2_plus_5n_plus_1223"]
    a = D._prompt(task, "A")
    b = D._prompt(task, "B")
    c = D._prompt(task, "C")
    assert a == task.prompt
    assert b == task.prompt + "\n\n" + D.LABEL_TEXT
    assert c == task.prompt + "\n\n" + D.oracle_text(task.id)
    assert "judged incorrect" in b
    assert "NO_SEARCH" in c


def test_sampling_matches_order_v2():
    assert D.MODEL == O.MODEL
    assert D.NUM_PREDICT == O.NUM_PREDICT == 1200
    assert D.THINK is False
    assert D.NUM_CTX == O.NUM_CTX == 8192
    assert D.TEMPERATURE == O.TEMPERATURE == 0.1
    assert D.TOP_P == O.TOP_P == 1.0
    assert D.REPEAT_PENALTY == O.REPEAT_PENALTY == 1.1
    assert D.SEED == O.SEED == 42
    assert D.KEEP_ALIVE == O.KEEP_ALIVE == "10m"
    assert D.MAX_CALLS == 40
    assert D.MAX_RUNTIME_S == 2400.0
    assert D.MIN_FREE_MB == 450.0
    assert D.PLANNED_CALLS == 26


def test_budget_planned_calls_within_max():
    # 2 A verify + 12 B + 12 C, or 12 A (if determinism fails) + 12 B + 12 C
    assert D.PLANNED_CALLS == 26
    assert 12 + 12 + 12 <= D.MAX_CALLS


def test_frozen_verification_against_order_v2():
    v = D.verify_frozen_against_order_v2()
    assert v["frozen_byte_identical"] is True
    assert v["frozen_path_count"] == v["frozen_baseline_path_count"]
