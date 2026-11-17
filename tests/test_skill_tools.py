"""Offline tests for the allowlisted first_composite_quadratic tool.

No generation, no data/ reads. The tool must be general: no task ids, no
ground-truth constants, no eval/exec, strict int validation.
"""

from __future__ import annotations

import inspect

import sympy

from block15 import skill_tools as S


def test_correct_first_composite():
    # f(n)=n^2+5n+1217: first composite at n=3 -> 1241 = 17*73
    r = S.first_composite_quadratic(1, 5, 1217, 128)
    assert r == {"n": 3, "value": 1241, "factors": [17, 73]}


def test_correct_negative_coefficients():
    # f(n)=n^2-n+41 is prime for n=0..40, composite at n=41 (Euler).
    r = S.first_composite_quadratic(1, -1, 41, 128)
    v = 41 * 41 - 41 + 41
    assert r["n"] == 41
    assert r["value"] == v
    assert r["factors"] == sorted(int(p) for p in sympy.factorint(v))


def test_no_composite_case():
    # A tight n_max before the first composite -> {"none": True}.
    r = S.first_composite_quadratic(1, 5, 1217, 2)
    assert r == {"none": True}


def test_bool_rejected():
    for args in [(True, 5, 1217, 128), (1, False, 1217, 128),
                 (1, 5, True, 128), (1, 5, 1217, True)]:
        try:
            S.first_composite_quadratic(*args)
            assert False, f"bool accepted: {args}"
        except ValueError:
            pass


def test_n_max_bounds():
    for bad in (0, -1, 129, 1000):
        try:
            S.first_composite_quadratic(1, 1, 1, bad)
            assert False, f"n_max accepted: {bad}"
        except ValueError:
            pass
    assert S.first_composite_quadratic(1, 0, 4, 128)["n"] == 0  # f(0)=4 composite


def test_non_int_rejected():
    for args in [(1.0, 5, 1217, 128), (1, 5, "1217", 128)]:
        try:
            S.first_composite_quadratic(*args)
            assert False, f"non-int accepted: {args}"
        except ValueError:
            pass


def test_never_returns_wrong_factorisation():
    # Sweep many parameter sets; every returned factorization must be exactly
    # SymPy's, the value must be composite, and n must be the FIRST composite.
    for a in range(1, 4):
        for b in range(-3, 4):
            for c in range(1, 60):
                r = S.first_composite_quadratic(a, b, c, 64)
                if r.get("none"):
                    continue
                n, v, fac = r["n"], r["value"], r["factors"]
                assert v == a * n * n + b * n + c
                assert not sympy.isprime(v)
                assert fac == sorted(int(p) for p in sympy.factorint(v))
                # minimality: no earlier value is composite (value<=1 or prime)
                for k in range(0, n):
                    earlier = a * k * k + b * k + c
                    assert earlier <= 1 or sympy.isprime(earlier)


def test_general_no_task_specific_constants_or_eval():
    src = inspect.getsource(S)
    low = src.lower()
    assert "eval(" not in low and "exec(" not in low
    # no pilot task ids or known ground-truth integers embedded
    for token in ("V2M03", "V2M04", "1247", "1067", "1457", "1207", "1159"):
        assert token not in src, f"task-specific constant present: {token}"
