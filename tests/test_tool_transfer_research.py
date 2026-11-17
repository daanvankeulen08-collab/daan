"""Offline tests for the tool-transfer harness (no generation)."""
from __future__ import annotations

from block15 import tool_transfer_research as R
from block15 import tool_transfer_tasks as TT
from block15 import tool_transfer_score as SC
from block15 import skill_tools as T


def test_constants():
    assert R.NUM_PREDICT == 1200 and R.NUM_PREDICT_REQUEST == 300
    assert R.MAX_CALLS == 130 and R.MAX_RUNTIME_S == 5400.0
    assert R.MIN_FREE_MB == 450.0 and R.PLANNED_CALLS == 120
    assert R.CONDITIONS == ("L0_REAL", "L0_SHAM")


def test_tasks():
    c = TT.verify_tasks()
    assert c["n_tasks"] == 30 and c["tool_needed"] == 20 and c["tool_not_needed"] == 10
    assert c["ground_truth_ok"] and c["copy_guard_ok"]


def test_r1_prompt_identical_across_conditions():
    # build_r1_prompt has no condition/exec argument => cannot leak real/sham
    task = R.TASKS[0]
    schema = R.tool_schema_block()
    p = SC.build_r1_prompt(task, schema)
    assert SC.build_r1_prompt(task, schema) == p
    assert "REAL" not in p and "SHAM" not in p
    assert T.TOOL_NAME in p


def test_r2_differs_only_by_tool_result():
    task = R.TASKS[0]
    a = SC.build_r2_prompt(task, {"status": "unavailable"})
    b = SC.build_r2_prompt(task, {"n": 3, "value": 1649, "factors": [17, 97]})
    # common prefix and suffix identical; only the tool-result line differs
    assert a.split("Tool result: ")[0] == b.split("Tool result: ")[0]
    assert "unavailable" in a and "1649" in b


def test_scorer_fields():
    assert SC.SCORER_VERSION == "tool_transfer_scorer_v1_frozen"
    assert SC.COPY_SURFACE == "r1_prompt"
