"""Certification fixtures: exercise summarize() end-to-end (no generation)."""
from __future__ import annotations

import pytest

from block15 import tool_transfer_fixtures as F
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_tasks as TT
from block15 import accounting as A

TN = list(TT.TOOL_NEEDED_IDS)   # 20
TNN = list(TT.TOOL_NOT_NEEDED_IDS)  # 10
ALL = TN + TNN


def run(records, task_ids=None):
    return SC.summarize(records, task_ids or ALL, TN, "testhash", True)


def test_false_alarm_rates_0_1_10():
    for fa in (0, 1, 10):
        rec = F.make_records(TN, TNN, fa_count=fa, real_tn_passes=14, sham_tn_passes=4)
        out = run(rec)
        assert out["criteria"]["false_alarm_rate"] == round(fa / 10, 4)
        assert len(out["criteria"]["false_alarm_ids"]) == fa


def test_mixed_requested_valid_invalid():
    rec = F.make_records(TN, TNN, fa_count=2, real_tn_passes=12, sham_tn_passes=3)
    # flip one tool-needed row to invalid_request with no tool request
    rec["L0_REAL"]["results"][0]["tool_request_valid"] = False
    rec["L0_REAL"]["results"][0]["tool_requested"] = False
    out = run(rec)
    assert out["conditions"]["L0_REAL"]["params_correct"] >= 0
    assert out["criteria"]["false_alarm_rate"] == 0.2


def test_empty_tool_needed_set():
    # summarize with no tool-needed tasks: mcnemar(0,0) => p=1.0, not replicated
    rec = F.make_records([], TNN, fa_count=0, real_tn_passes=0, sham_tn_passes=0)
    out = SC.summarize(rec, TNN, [], "testhash", True)
    assert out["criteria"]["mcnemar_p"] == 1.0
    assert out["verdict"] == "NOT REPLICATED"


def test_all_pass_and_all_fail():
    rec = F.make_records(TN, TNN, fa_count=0, real_tn_passes=20, sham_tn_passes=20)
    out = run(rec)
    assert out["conditions"]["L0_REAL"]["passes"] == 20
    rec2 = F.make_records(TN, TNN, fa_count=0, real_tn_passes=0, sham_tn_passes=0)
    out2 = run(rec2)
    assert out2["conditions"]["L0_REAL"]["passes"] == 0


def test_missing_raw_content_does_not_crash():
    rec = F.make_records(TN, TNN, fa_count=1, real_tn_passes=5, sham_tn_passes=2,
                         missing_raw=True)
    out = run(rec)
    assert out["conditions"]["L0_REAL"]["cells"] == 30


def test_real_sham_pass_overlap_and_g1():
    rec = F.make_records(TN, TNN, fa_count=0, real_tn_passes=14, sham_tn_passes=4,
                         g1_identical=True)
    out = run(rec)
    assert out["G1"]["verdict"] == "PASS"
    ov = out["pass_overlaps"]["L0_REAL&L0_SHAM"]
    assert set(ov).issubset({t.split("_")[0] for t in TN})
    # G1 violation flips verdict
    rec2 = F.make_records(TN, TNN, fa_count=0, real_tn_passes=14, sham_tn_passes=4,
                          g1_identical=False)
    out2 = run(rec2)
    assert out2["G1"]["verdict"] == "INVALID"
    assert out2["criteria"]["replicated"] is False


def test_passes_contribute_zero_events():
    rows = [F.make_row(f"T{i:02d}_x", primary=True, conf=99, copy=True,
                       status="error", done="length") for i in range(5)]
    assert A.account(rows)["failure_events"] == 0
    assert A.partition(rows) == {}


def test_verdict_matrix_selective_and_not():
    # replicated + selective
    r1 = run(F.make_records(TN, TNN, fa_count=2, real_tn_passes=14, sham_tn_passes=4))
    assert r1["verdict"] == "PROCEDURAL SELECTION DEMONSTRATED"
    # replicated + not selective (10/10 false alarms)
    r2 = run(F.make_records(TN, TNN, fa_count=10, real_tn_passes=14, sham_tn_passes=4))
    assert r2["verdict"] == "PARAMETER BINDING ONLY, NOT SELECTION"
    # not replicated
    r3 = run(F.make_records(TN, TNN, fa_count=0, real_tn_passes=4, sham_tn_passes=4))
    assert r3["verdict"] == "NOT REPLICATED"
