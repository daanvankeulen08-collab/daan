"""Offline tests for the placebo-control harness."""

from __future__ import annotations

from block15 import accounting as A
from block15 import placebo_research as P


def test_twelve_tasks_same_order():
    assert len(P.FAILURE_IDS) == 12
    assert P.FAILURE_IDS == P.D.FAILURE_IDS


def test_sampling_matches_reference():
    assert P.NUM_PREDICT == 1200
    assert P.TEMPERATURE == 0.1
    assert P.TOP_P == 1.0
    assert P.REPEAT_PENALTY == 1.1
    assert P.NUM_CTX == 8192
    assert P.SEED == 42
    assert P.KEEP_ALIVE == "10m"
    assert P.THINK is False
    assert P.MAX_CALLS == 30
    assert P.MAX_RUNTIME_S == 1800.0
    assert P.MIN_FREE_MB == 450.0
    assert P.PLANNED_CALLS == 24


def test_d2_length_matches_c_per_task():
    chk = P.verify_placebo_texts()
    for tid, c in chk.items():
        conds = c["conditions"]
        assert conds["D2"]["token_length"] == conds["C"]["token_length"]


def test_placebos_carry_no_diagnostic_information():
    chk = P.verify_placebo_texts()
    for tid, c in chk.items():
        for name in ("D1", "D2"):
            p = c["conditions"][name]
            assert p["copy_possible"] is False
            assert p["class_words"] == []
            assert p["appended_text"]


def test_d1_is_the_specified_fixed_text():
    assert P.D1_TEXT == "Please review your work carefully and attempt the task again."


def test_appended_texts_only_differ_between_conditions():
    for tid in P.FAILURE_IDS:
        base = P.TASK_BY_ID[tid].prompt
        for c in ("B", "C", "D1", "D2"):
            p = P.prompt_for(tid, c)
            assert p.startswith(base)
            assert p[len(base):].startswith("\n\n")


def test_frozen():
    assert P.verify_frozen()["frozen_byte_identical"] is True


def test_accounting_flag_set_shared():
    assert A.FAILURE_FLAG_SET == P.A.FAILURE_FLAG_SET
