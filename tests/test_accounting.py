"""Offline tests for the canonical failure-accounting convention."""

from __future__ import annotations

from block15 import accounting as A


def test_fixed_flag_set_is_exactly_the_enumerated_set():
    assert A.FAILURE_FLAG_SET == frozenset({
        "call_error", "parse_failed", "schema_violation",
        "truncated", "primary_wrong", "confidence_out_of_range",
        "copy_possible",
    })


def test_passing_cell_contributes_zero_failure_events():
    # A passing cell with an otherwise anomalous field still contributes zero.
    passing = {
        "primary_correct": True,
        "status": "ok",
        "raw_content": '{"final_answer":"1","derivation":["s"],"uncertainty":"u","confidence":0.5}',
        "validate_v2_ok": True,
        "done_reason": "stop",
        "confidence_raw": 99,  # anomalous but the cell PASSED
        "copy_possible": True,  # anomalous but the cell PASSED
    }
    assert A.failure_events([passing]) == 0
    assert A.failed_cells([passing]) == 0
    assert A.account([passing])["audited_passes"] == 1


def test_failed_cell_flags_are_from_fixed_set_and_events_equals_sum():
    failing = {
        "primary_correct": False,
        "status": "output_error",
        "raw_content": None,
        "validate_v2_ok": False,
        "done_reason": "length",
        "confidence_raw": None,
        "copy_possible": False,
    }
    flags = A.failure_flags(failing)
    assert set(flags).issubset(A.FAILURE_FLAG_SET)
    assert "call_error" in flags
    assert "parse_failed" in flags
    assert "truncated" in flags
    assert "primary_wrong" in flags
    assert "confidence_out_of_range" in flags
    assert A.failure_events([failing]) == len(flags)
    assert A.failed_cells([failing]) == 1


def test_failure_events_is_sum_over_nonpass_only():
    passing = {
        "primary_correct": True, "status": "ok",
        "raw_content": '{"final_answer":"1","derivation":["s"],"uncertainty":"u","confidence":0.5}',
        "validate_v2_ok": True, "done_reason": "stop",
        "confidence_raw": 0.5, "copy_possible": False,
    }
    failing = {
        "primary_correct": False, "status": "ok",
        "raw_content": '{"final_answer":"x","derivation":["s"],"uncertainty":"u","confidence":0.5}',
        "validate_v2_ok": True, "done_reason": "stop",
        "confidence_raw": 0.5, "copy_possible": False,
    }
    rows = [passing, failing, failing]
    expected = len(A.failure_flags(failing)) * 2
    assert A.failure_events(rows) == expected
    assert A.failed_cells(rows) == 2
    assert A.account(rows)["audited_passes"] == 1
