"""Tests for the Block B harness and certifier (no generation)."""
from __future__ import annotations

import json

from block15 import integration_certify as CERT
from block15 import integration_research as I
from block15 import integration_tasks as IT
from block15 import order_v2_research as O


def test_plausible_value_properties():
    for t in IT.TASKS:
        c = t.coefficient
        p = I.plausible_value(c)
        assert p != c
        assert (p > 0) == (c > 0)
        assert len(str(abs(p))) == len(str(abs(c)))
        assert I.tool_result_for("CORRECT", c)["value"] == c
        assert I.tool_result_for("PLAUSIBLE", c)["value"] == p
        assert I.tool_result_for("ABSENT", c) == {"status": "unavailable"}


def test_g1_prompts_differ_only_by_tool_result():
    pm = {c: I.build_prompt(IT.TASKS[0], c) for c in I.CONDITIONS}
    assert I.g1_check(pm)["pass"] is True
    assert len({I.strip_tool_result(p) for p in pm.values()}) == 1
    bad = dict(pm); bad["PLAUSIBLE"] = bad["PLAUSIBLE"].replace("Expand", "Compute")
    assert I.g1_check(bad)["pass"] is False


def test_adoption_and_meta():
    c = IT.TASKS[0].coefficient
    assert I.adopts(c, f"the coefficient is {c}") is True
    assert I.adopts(c, "the coefficient is 1") is (c == 1)
    assert I.adopts(None, "anything") is False
    assert I.is_meta("the complete prime factorization of f(n)") is True
    assert I.is_meta(". We'll go with tool data.") is True
    assert I.is_meta(f"{c}") is False


def test_seal_and_atomic(tmp_path):
    # Build synthetic records via the shared fake run used by the certifier.
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
    # A5 requires the runner blob at HEAD; before the code commit it is None.
    for name, check in a["checks"].items():
        if name == "A5_blob_pins" and check["runner"] is None:
            continue
        assert check.get("pass", False) is True, name
    import json as _j
    ha = _j.dumps(a, sort_keys=True, separators=(",", ":"))
    hb = _j.dumps(b, sort_keys=True, separators=(",", ":"))
    assert ha == hb
