"""Offline tests for M2 card harness (no generation)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from block15 import m2_research as M2
from block15 import m2_tasks as M2T
from block15 import tool_transfer_fixtures as F


def test_fresh_tasks():
    c = M2T.verify_tasks()
    assert c["n_tasks"] == 30 and c["tool_needed"] == 20 and c["tool_not_needed"] == 10
    assert c["ground_truth_ok"] and c["copy_guard_ok"] and c["disjoint_ok"]


def test_cards_no_gt_and_lengths():
    chk = M2.verify_cards_no_gt()
    for v in chk.values():
        assert v["gt_token_hits"] == [] and v["task_id_hits"] == []
    assert chk["CARD_NEG"]["token_length"] > chk["CARD_FADE"]["token_length"]


def test_scorer_adapter_and_seal():
    recs = F.make_records(list(M2T.TOOL_NEEDED_IDS), list(M2T.TOOL_NOT_NEEDED_IDS),
                          fa_count=1, real_tn_passes=14, sham_tn_passes=4)
    m2recs = {"CARD_NEG": recs["L0_REAL"], "CARD_FADE": recs["L0_SHAM"]}
    result = M2.sealed_compute(m2recs)
    assert M2.verify_seal(result) is True
    assert "G1" in result and "verdict" in result


def test_atomic_no_leak_on_inject_fail():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        recs = F.make_records(list(M2T.TOOL_NEEDED_IDS), list(M2T.TOOL_NOT_NEEDED_IDS),
                              fa_count=1, real_tn_passes=14, sham_tn_passes=4)
        m2recs = {"CARD_NEG": recs["L0_REAL"], "CARD_FADE": recs["L0_SHAM"]}
        out = d / "s.json"
        try:
            M2.sealed_summarize(out, inject_fail=True, records=m2recs)
            assert False, "inject should raise"
        except RuntimeError:
            pass
        assert not out.exists()


def test_constants():
    assert M2.MAX_CALLS == 130 and M2.MAX_RUNTIME_S == 5400.0
    assert M2.PLANNED_CALLS == 120
    assert M2.CONDITIONS == ("CARD_NEG", "CARD_FADE")
