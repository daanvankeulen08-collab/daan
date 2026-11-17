"""Offline tests for the skill-tool harness (no generation)."""

from __future__ import annotations

from block15 import order_v2_research as O
from block15 import skill_tool_research as S
from block15 import skill_tools as T


def _task(tid):
    return {t.id: t for t in O.TASKS}[tid]


def test_constants_and_conditions():
    assert S.NUM_PREDICT == 1200
    assert S.NUM_PREDICT_REQUEST == 300
    assert S.MAX_CALLS == 80
    assert S.MAX_RUNTIME_S == 3600.0
    assert S.MIN_FREE_MB == 450.0
    assert S.PLANNED_CALLS == 72
    assert S.CONDITIONS == ("L3_SHAM", "L3_REAL", "L0_SHAM", "L0_REAL")
    assert len(S.PILOT_IDS) == 9


def test_call1_prompt_identical_real_sham():
    for level in ("L3", "L0"):
        p = S.request_prompt(_task(S.PILOT_IDS[0]), level)
        # request_prompt has no exec parameter -> cannot differ by execution mode
        assert p == S.request_prompt(_task(S.PILOT_IDS[0]), level)
        assert "REAL" not in p and "SHAM" not in p


def test_assistance_presence():
    t = _task(S.PILOT_IDS[0])
    assert "PROCEDURE CARD" in S.request_prompt(t, "L3")
    assert "PROCEDURE CARD" not in S.request_prompt(t, "L0")
    assert T.TOOL_NAME in S.request_prompt(t, "L0")  # schema present in both


def test_prompts_no_gt_leak():
    check = S.verify_prompts_no_gt()
    assert all(v == [] for v in check.values())


def test_validate_request():
    good = {"tool_request": {"tool": T.TOOL_NAME,
                             "arguments": {"a": 1, "b": 5, "c": 1223, "n_max": 128}}}
    ok, norm = S.validate_request(good)
    assert ok and norm["arguments"]["c"] == 1223
    ok2, _ = S.validate_request({"tool_request": None})
    assert ok2
    bad = {"tool_request": {"tool": T.TOOL_NAME,
                            "arguments": {"a": 1, "b": 5, "c": 1223, "n_max": 0}}}
    assert not S.validate_request(bad)[0]


def test_parameters_correct():
    t = _task("V2M03_minimal_n2_plus_5n_plus_1223")
    good = {"tool": T.TOOL_NAME,
            "arguments": {"a": 1, "b": 5, "c": 1223, "n_max": 128}}
    assert S.parameters_correct(good, t)
    wrong = {"tool": T.TOOL_NAME,
             "arguments": {"a": 1, "b": 5, "c": 999, "n_max": 128}}
    assert not S.parameters_correct(wrong, t)


def test_frozen():
    assert S.verify_frozen()["frozen_byte_identical"] is True
