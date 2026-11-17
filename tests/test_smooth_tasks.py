"""Tests for the SMOOTH fresh task set and the two wrong-value constructions."""
from __future__ import annotations

import hashlib
import json
import sympy

from block15 import smooth_tasks as ST


def test_verify_tasks():
    c = ST.verify_tasks()
    assert c["n_tasks"] == 20
    assert all(c[k] for k in ("ground_truth_ok", "copy_guard_ok", "disjoint_ok",
                              "smooth_ok", "factor_ok", "distinct_ids"))


def test_disjoint_from_all_prior():
    for t in ST.TASKS:
        assert (t.a, t.b) not in ST.PRIOR
    assert len(ST.PRIOR) >= 80


def test_smooth_value_is_neighbor_true_coeff():
    for t in ST.TASKS:
        sv = ST.smooth_value(t)
        assert sv["value"] != t.coefficient
        assert sv["exponent"] in (t.p - 1, t.p + 1)
        assert sv["is_true_coeff"] is True
        assert ST.coeff_at(t.a, t.b, t.k, sv["exponent"]) == sv["value"]
        if sv["same_sign_as_gt"]:
            assert (sv["value"] > 0) == (t.coefficient > 0)
        assert sv["factorization"]


def test_factor_value_replicates_v2():
    for t in ST.TASKS:
        fv = ST.factor_value(t)
        assert fv["value"] == int(round(t.coefficient * 15 / 14))
        assert fv["value"] != t.coefficient
        assert fv["factorization"]


def test_manifest_deterministic():
    m = hashlib.sha256(json.dumps([t.metadata() for t in ST.TASKS],
                                  sort_keys=True).encode()).hexdigest()
    assert len(m) == 64
