"""Offline tests for the frozen tool-transfer scorer (no generation, no data reads)."""
from __future__ import annotations

import json

import sympy

from block15 import tool_transfer_score as SC
from block15 import skill_tools as T


def _task(kind, **kw):
    class Task:
        pass
    t = Task()
    t.id = kw.get("id", "T")
    t.kind = kind
    t.question = kw.get("question", "q")
    t.a, t.b, t.c = kw.get("a"), kw.get("b"), kw.get("c")
    t.expression, t.power = kw.get("expression"), kw.get("power")
    return t


def _truth_min(n, value, primes):
    return {"kind": "minimality", "n": n, "value": value,
            "primes": primes, "answer_tokens": [n, value, *primes]}


def _truth_coeff(c):
    return {"kind": "coefficient", "coefficient": c, "answer_tokens": [c]}


def test_audit_minimality_strict():
    t = _task("minimality")
    tr = _truth_min(3, 1099, [7, 157])
    a = SC.audit_answer(t, tr, "n=3, f(3)=1099, factors 7 and 157")
    assert a["audit_passed"] and a["strict_set_equal"]
    b = SC.audit_answer(t, tr, "n=3, f(3)=1099, factor 7")  # missing 157
    assert not b["audit_passed"]
    c = SC.audit_answer(t, tr, "7 * 157 = 1099 but n=2")
    assert not c["audit_passed"]


def test_audit_coefficient_exact_int():
    t = _task("coefficient")
    tr = _truth_coeff(2880)
    assert SC.audit_answer(t, tr, "the coefficient is 2,880")["audit_passed"]
    assert not SC.audit_answer(t, tr, "28800")["audit_passed"]


def test_copy_surface_is_r1_only():
    t = _task("minimality", question="Let f(n) = n^2 + n + 1087. smallest composite?")
    tr = _truth_min(3, 1099, [7, 157])
    r1 = "Let f(n) = n^2 + n + 1087. smallest composite?"
    row = {"task_id": t.id, "answer_text": "n=3, f(3)=1099, factors 7 and 157",
           "r1_prompt": r1, "raw_content": '{"final_answer":"x"}',
           "done_reason": "stop", "validate_v2_ok": True, "confidence_raw": 0.9,
           "status": "ok"}
    s = SC.score_cell(row, t, tr)
    assert s["audit_passed"] and not s["copy_possible"] and s["primary_correct"]
    # If r1 contained a GT token, copy would be true and pass disqualified
    row2 = dict(row, r1_prompt=r1 + " (answer 1099)")
    s2 = SC.score_cell(row2, t, tr)
    assert s2["copy_possible"] and not s2["primary_correct"]


def test_copy_check_ignores_tool_result_text():
    """The appended tool result legitimately has GT; never scanned."""
    assert SC.COPY_SURFACE == "r1_prompt"
    t = _task("minimality", question="q")
    tr = _truth_min(3, 1099, [7, 157])
    r2 = SC.build_r2_prompt(t, {"n": 3, "value": 1099, "factors": [7, 157]})
    assert "1099" in r2  # tool result present in Call 2
    row = {"task_id": t.id, "answer_text": "n=3, f(3)=1099, factors 7 and 157",
           "r1_prompt": "q", "raw_content": "{}", "validate_v2_ok": True,
           "confidence_raw": 0.9, "status": "ok", "done_reason": "stop"}
    s = SC.score_cell(row, t, tr)
    assert not s["copy_possible"]  # r2 text never used


def test_validate_request():
    good = {"tool_request": {"tool": T.TOOL_NAME,
                             "arguments": {"a": 1, "b": 1, "c": 1087, "n_max": 64}}}
    ok, norm = SC.validate_request(good)
    assert ok and norm["arguments"]["n_max"] == 64
    assert SC.validate_request({"tool_request": None})[0]
    assert not SC.validate_request({"tool_request": {"tool": T.TOOL_NAME,
        "arguments": {"a": 1, "b": 1, "c": 1, "n_max": 0}}})[0]


def test_parameters_correct():
    t = _task("minimality", a=1, b=1, c=1087)
    assert SC.parameters_correct({"arguments": {"a": 1, "b": 1, "c": 1087, "n_max": 64}}, t)
    assert not SC.parameters_correct({"arguments": {"a": 1, "b": 1, "c": 9, "n_max": 64}}, t)


def test_mcnemar_known():
    assert SC.mcnemar_exact(0, 0) == 1.0
    assert abs(SC.mcnemar_exact(3, 0) - 0.25) < 1e-9


def test_passing_cell_zero_events():
    t = _task("minimality")
    tr = _truth_min(3, 1099, [7, 157])
    row = {"task_id": t.id, "answer_text": "n=3, f(3)=1099, factors 7 and 157",
           "r1_prompt": "q", "raw_content": '{"final_answer":"ok"}',
           "validate_v2_ok": True, "confidence_raw": 0.9, "status": "ok",
           "done_reason": "stop"}
    s = SC.score_cell(row, t, tr)
    assert s["failure_flags"] == []
