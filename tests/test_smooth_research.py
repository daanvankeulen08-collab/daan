"""Tests for the SMOOTH harness and certifier (no generation)."""
from __future__ import annotations

import json

from scipy.stats import beta as B
from scipy.stats import fisher_exact as FE

from block15 import smooth_certify as CERT
from block15 import smooth_research as I
from block15 import smooth_tasks as ST


def test_exact_ci_and_fisher():
    assert abs(I.exact_upper_95(0, 20) - float(B.ppf(0.95, 1, 20))) < 1e-9
    assert abs(I.exact_upper_95(20, 20) - 1.0) < 1e-9
    lo, hi = I.exact_ci_95(3, 20)
    assert abs(hi - float(B.ppf(0.975, 4, 17))) < 1e-9
    assert lo < hi
    assert 0.0 <= float(FE([[3, 17], [0, 20]])[1]) <= 1.0


def test_endpoint_exclusive_vs_mention():
    t = ST.TASKS[0]
    v = ST.smooth_value(t)["value"]
    g = t.coefficient
    assert I.wrong_commit(v, str(v)) is True
    assert I.wrong_commit(v, f"{v} and {g}") is False
    assert I.mention_only(v, f"{v} and {g}") is True
    assert I.mention_only(v, str(v)) is False
    assert I.wrong_commit(None, str(v)) is False
    assert I.answer_ints("-12, 7 and -12") == {-12, 7}
    assert I.answer_ints("the coefficient is 540") == {540}


def test_g1_and_verdict():
    pm = {c: I.build_prompt(ST.TASKS[0], c) for c in I.CONDITIONS}
    assert I.g1_check(pm)["pass"] is True
    assert len({I.strip_tool_result(p) for p in pm.values()}) == 1
    bad = dict(pm); bad["ABSENT"] = bad["ABSENT"] + " X"
    assert I.g1_check(bad)["pass"] is False
    assert I.decide_verdict(8, 20, 1, 20, True, 0.01)["verdict"] == "STRUCTURAL_REJECTION"
    assert I.decide_verdict(0, 20, 1, 20, True, 0.5)["verdict"] == "GENUINE_REJECTION"
    assert I.decide_verdict(6, 20, 6, 20, True, 1.0)["verdict"] == "INCONCLUSIVE"
    assert I.decide_verdict(0, 20, 0, 20, False, 1.0)["verdict"] == "INVALID"


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
    # Make the row a pass via the alias only, then remove the canonical field:
    # canonical_pass falls back to the alias (counts a pass) but frozen accounting
    # reads primary_correct (counts a fail) -> summarize must detect the drift.
    bad["SMOOTH"]["results"][0]["audited_pass"] = True
    del bad["SMOOTH"]["results"][0]["primary_correct"]
    try:
        I.summarize(bad)
        raised = False
    except ValueError:
        raised = True
    assert raised is True
    conflict = copy.deepcopy(recs)
    conflict["SMOOTH"]["results"][0]["primary_correct"] = not conflict["SMOOTH"]["results"][0]["primary_correct"]
    assert CERT.accounting_invariant(conflict, I.summarize(conflict))["pass"] is False


def test_seal_and_atomic(tmp_path):
    recs = CERT.fake_run(tmp_path)
    sealed = I.sealed_compute(recs)
    assert I.verify_seal(sealed) is True
    out = tmp_path / "s.json"
    I.sealed_write(sealed, out)
    assert out.exists()
    try:
        I.sealed_compute(recs, inject_fail=True)
        assert False
    except RuntimeError:
        pass


def test_certifier_green_and_deterministic():
    a = CERT.certify(); b = CERT.certify()
    for name, check in a["checks"].items():
        if name == "A10_blob_pins" and check["runner"] is None:
            continue
        assert check.get("pass", False) is True, name
    ha = json.dumps(a, sort_keys=True, separators=(",", ":"))
    hb = json.dumps(b, sort_keys=True, separators=(",", ":"))
    assert ha == hb
