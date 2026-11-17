"""A3 regressions: the two bugs that contaminated V1 and V2 must stay fixed."""
from __future__ import annotations

from block15 import tool_transfer_fixtures as F
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_tasks as TT
from block15 import tool_transfer_v3 as V3
from block15 import accounting as A

TN = list(TT.TOOL_NEEDED_IDS)
TNN = list(TT.TOOL_NOT_NEEDED_IDS)
ALL = TN + TNN


def test_v1_false_alarm_list_set_regression():
    """V1 bug: requested_ids (a list) & set -> TypeError at false-alarm aggregation.

    V2 fixed it with set() conversion. This test exercises the exact aggregation at
    0/1/10 false alarms and requires no TypeError and correct rates.
    """
    for k, expected in ((0, 0.0), (1, 0.1), (10, 1.0)):
        rec = F.make_records(TN, TNN, fa_count=k, real_tn_passes=14,
                             sham_tn_passes=4)
        out = SC.summarize(rec, ALL, TN, "h", True)
        assert out["criteria"]["false_alarm_rate"] == expected
        assert len(out["criteria"]["false_alarm_ids"]) == k


def test_v2_wrapper_nameerror_regression():
    """V2 bug: runner's summarize() called undefined scorer_blob_sha256().

    V3 renamed to scorer_blob_hash(). Assert the name resolves and the sealed
    wrapper computes end-to-end on synthetic records without NameError.
    """
    assert callable(V3.scorer_blob_hash)
    rec = F.make_records(TN, TNN, fa_count=1, real_tn_passes=14, sham_tn_passes=4)
    result = V3.sealed_compute(rec)
    assert V3.verify_seal(result) is True
    assert "G1" in result and "verdict" in result


def test_a1_seal_roundtrip_and_bypass():
    rec = F.make_records(TN, TNN, fa_count=1, real_tn_passes=14, sham_tn_passes=4)
    sealed = V3.sealed_compute(rec)
    assert V3.verify_seal(sealed) is True
    # bypass: scorer output with no seal must be refused
    bypass = SC.summarize(rec, ALL, TN, "h", True)
    assert V3.verify_seal(bypass) is False


def test_failure_accounting_passes_zero():
    rows = [F.make_row(f"T{i:02d}_x", primary=True, conf=99, copy=True,
                       status="error", done="length") for i in range(5)]
    assert A.account(rows)["failure_events"] == 0
