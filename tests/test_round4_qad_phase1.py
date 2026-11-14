"""Phase 1 tests: separable Round 4 stores and the derivation-aware R3B scorer.

``data/`` is gitignored, so no fixture is read from disk.  A minimal inline
object reproduces the Round 3 R3B shape (final answer truncated to ``4`` while
the derivation reaches ``f(4)=121=11*11``), matching the observed Round 3
behaviour whose stored strict flag was ``objective_fail``.
"""

from __future__ import annotations

import copy

from block15.round3 import _round3_store_paths, independent_check
from block15.round3_tasks import RUN_ORDER
from block15.round4_scoring import r3b_derivation_aware
from block15.run_benchmark import DATA_DIR

B_TASK = next(
    task for task in RUN_ORDER if task.id == "R3B_counterexample_minimality"
)

INLINE_R3B_FINAL: dict = {
    "derivation": [
        "f(0)=101, f(1)=103, f(2)=107 and f(3)=113 are prime.",
        "f(4)=16+4+101=121=11*11, composite.",
    ],
    "final_answer": "4",
    "uncertainty": "Only n=0..4 were checked.",
    "confidence": 0.9,
}


def test_store_paths_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("BLOCK15_DB_PATH", raising=False)
    monkeypatch.delenv("BLOCK15_JSONL_PATH", raising=False)

    db_path, jsonl_path = _round3_store_paths()

    assert db_path == DATA_DIR / "block15_round3.sqlite3"
    assert jsonl_path == DATA_DIR / "block15_round3_events.jsonl"
    assert db_path.name == "block15_round3.sqlite3"
    assert jsonl_path.name == "block15_round3_events.jsonl"


def test_store_paths_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOCK15_DB_PATH", "block15_round4_arm_a.sqlite3")
    monkeypatch.setenv(
        "BLOCK15_JSONL_PATH", "block15_round4_arm_a_events.jsonl"
    )
    db_path, jsonl_path = _round3_store_paths()

    assert db_path == DATA_DIR / "block15_round4_arm_a.sqlite3"
    assert jsonl_path == DATA_DIR / "block15_round4_arm_a_events.jsonl"

    # Arm B must resolve to a different pair of store files.
    monkeypatch.setenv("BLOCK15_DB_PATH", "block15_round4_arm_b.sqlite3")
    monkeypatch.setenv(
        "BLOCK15_JSONL_PATH", "block15_round4_arm_b_events.jsonl"
    )
    db_path_b, jsonl_path_b = _round3_store_paths()

    assert db_path_b != db_path
    assert jsonl_path_b != jsonl_path
    assert db_path_b == DATA_DIR / "block15_round4_arm_b.sqlite3"
    assert jsonl_path_b == DATA_DIR / "block15_round4_arm_b_events.jsonl"


def test_store_paths_absolute_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOCK15_DB_PATH", str(tmp_path / "arm_b.sqlite3"))
    monkeypatch.setenv(
        "BLOCK15_JSONL_PATH", str(tmp_path / "arm_b_events.jsonl")
    )

    db_path, jsonl_path = _round3_store_paths()

    assert db_path == tmp_path / "arm_b.sqlite3"
    assert jsonl_path == tmp_path / "arm_b_events.jsonl"


def test_r3b_strict_fail_combined_pass():
    result = r3b_derivation_aware(B_TASK, INLINE_R3B_FINAL)

    strict = result["strict"]
    combined = result["combined"]

    # Strict reading: final_answer-only, Round 3 comparable.
    assert strict["status"] == "objective_fail"
    assert strict["final_contains_first_n"] is True
    assert strict["final_contains_counterexample_value"] is False
    assert strict["final_contains_factorization"] is False

    # The strict reading must agree with the untouched Round 3 checker.
    round3_result = independent_check(B_TASK, INLINE_R3B_FINAL, None)
    assert round3_result["status"] == strict["status"]

    # Combined reading: final_answer + derivation.
    assert combined["status"] == "objective_partial"
    assert combined["final_contains_first_n"] is True
    assert combined["final_contains_counterexample_value"] is True
    assert combined["final_contains_factorization"] is True
    assert combined["derivation_contains_first_n"] is True

    # Both statuses are exposed explicitly; strict is never overwritten.
    assert result["strict_status"] == "objective_fail"
    assert result["combined_status"] == "objective_partial"


def test_scorer_does_not_mutate_input():
    before = copy.deepcopy(INLINE_R3B_FINAL)

    r3b_derivation_aware(B_TASK, INLINE_R3B_FINAL)

    assert INLINE_R3B_FINAL == before


def test_scorer_rejects_other_tasks():
    other = next(
        task
        for task in RUN_ORDER
        if task.id != "R3B_counterexample_minimality"
    )

    try:
        r3b_derivation_aware(other, INLINE_R3B_FINAL)
    except ValueError:
        return
    raise AssertionError("derivation-aware scorer accepted a non-R3B task")