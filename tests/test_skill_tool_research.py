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


def test_copy_surface_is_task_prompt_not_tool_result():
    """The corrected copy check scans the task/assistance prompt (GT-free),
    never the tool-result-augmented Call-2 prompt (which legitimately has GT)."""
    from block15 import accounting as A
    from block15 import order_v2_research as O
    t = _task("V2M04_minimal_2n2_plus_6n_plus_1031")
    gt = O.ground_truth_manifest()[t.id]
    r1 = S.request_prompt(t, "L3")
    # task+assistance prompt has no GT token
    assert not any(__import__("block15.round3", fromlist=["x"])._number_present(r1, int(v))
                   for v in gt["answer_tokens"])
    # a passing cell contributes zero failure events (accounting fix target)
    row = {"primary_correct": True, "status": "ok", "raw_content":
           '{"final_answer":"n=3, f(3)=1067, 11*97","derivation":["s"],"uncertainty":"u","confidence":0.9}',
           "validate_v2_ok": True, "done_reason": "stop", "confidence_raw": 0.9,
           "copy_possible": False}
    assert A.failure_events([row]) == 0
