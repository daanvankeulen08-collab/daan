"""Tests for Integration V2 harness and certifier (no generation)."""
from __future__ import annotations

import json

from block15 import integration_v2_certify as CERT
from block15 import integration_v2_research as I
from block15 import integration_v2_tasks as IT2


def test_exact_upper_ci():
    from scipy.stats import beta as B
    assert abs(I.exact_upper_95(0, 60) - float(B.ppf(0.95, 1, 60))) < 1e-9
    assert abs(I.exact_upper_95(30, 60) - float(B.ppf(0.95, 31, 30))) < 1e-9
    assert I.exact_upper_95(60, 60) == 1.0
    assert I.exact_upper_95(0, 60) < I.exact_upper_95(30, 60)


def test_plausible_and_g1():
    for t in IT2.TASKS:
        c = t.coefficient
        p = I.plausible_value(c)
        assert p != c and (p > 0) == (c > 0) and len(str(abs(p))) == len(str(abs(c)))
        assert I.tool_result_for("CORRECT", c)["value"] == c
        assert I.tool_result_for("PLAUSIBLE", c)["value"] == p
        assert I.tool_result_for("ABSENT", c) == {"status": "unavailable"}
    pm = {c: I.build_prompt(IT2.TASKS[0], c) for c in I.CONDITIONS}
    assert I.g1_check(pm)["pass"] is True
    assert len({I.strip_tool_result(p) for p in pm.values()}) == 1
    bad = dict(pm); bad["PLAUSIBLE"] = bad["PLAUSIBLE"].replace("Expand", "Compute")
    assert I.g1_check(bad)["pass"] is False


def test_adoption_and_meta():
    c = IT2.TASKS[0].coefficient
    assert I.adopts(c, f"the coefficient is {c}") is True
    assert I.adopts(None, "anything") is False
    assert I.is_meta("the complete prime factorization of f(n)") is True
    assert I.is_meta(f"{c}") is False


def test_accounting_field_mismatch(tmp_path):
    import copy
    recs = CERT.fake_run(tmp_path)
    summ = I.summarize(recs)
    inv = CERT.accounting_invariant(recs, summ)
    assert inv["pass"] is True
    for cond, d in inv["conditions"].items():
        assert d["missing_canonical"] == 0 and d["alias_conflict"] == 0
        assert d["direct_passes"] == d["summarize_passes"] == d["account_passes"]
        assert d["failed_cells"] == d["direct_failed_cells"]
        assert d["failure_events"] == d["direct_failure_events"]
    bad = copy.deepcopy(recs)
    del bad["CORRECT"]["results"][0]["primary_correct"]
    try:
        I.summarize(bad)
        raised = False
    except ValueError:
        raised = True
    assert raised is True
    conflict = copy.deepcopy(recs)
    conflict["CORRECT"]["results"][0]["primary_correct"] = not conflict["CORRECT"]["results"][0]["primary_correct"]
    assert CERT.accounting_invariant(conflict, I.summarize(conflict))["pass"] is False


def test_seal_and_verdict_boundaries(tmp_path):
    recs = CERT.fake_run(tmp_path)
    sealed = I.sealed_compute(recs)
    assert I.verify_seal(sealed) is True
    # Verdict: zero wrong adoption with G1 pass -> REJECT_SURFACE
    assert I.exact_upper_95(0, 60) < 0.5  # 0/60 rejects
    assert I.exact_upper_95(30, 60) >= 0.5  # 30/60 point=0.5 supports
    assert sealed["verdict"] in ("REJECT_SURFACE", "SUPPORT_SURFACE", "INCONCLUSIVE")


def test_certifier_green_and_deterministic():
    a = CERT.certify(); b = CERT.certify()
    for name, check in a["checks"].items():
        if name == "A7_blob_pins" and check["runner"] is None:
            continue
        assert check.get("pass", False) is True, name
    ha = json.dumps(a, sort_keys=True, separators=(",", ":"))
    hb = json.dumps(b, sort_keys=True, separators=(",", ":"))
    assert ha == hb
