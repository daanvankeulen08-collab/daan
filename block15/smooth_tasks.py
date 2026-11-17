"""Fresh 20-task coefficient set for the SMOOTH study.

20 tool-inapplicable binomial-coefficient tasks, SymPy ground truth, disjoint from
every prior coefficient (a,b) pair (80 prior pairs across all prior studies).
Copy guard: no ground-truth token in any prompt. Deterministic generation.

Also provides the two WRONG injected-value constructions used by the study:
  smooth_value(task) = a neighbouring TRUE coefficient of the same expansion
                       (exponent p-1 or p+1), != GT, same sign where possible;
  factor_value(task) = round(GT*15/14), != GT (replicates the V2 construction).
"""
from __future__ import annotations

import hashlib
import re

import sympy

from block15 import tool_transfer_tasks as TT
from block15 import m2_tasks as M2T
from block15 import integration_tasks as IT
from block15 import integration_v2_tasks as IT2


def _prior_pairs() -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set(M2T.PRIOR_COEFF)
    for mod in (TT, M2T, IT, IT2):
        for t in getattr(mod, "TASKS", []):
            if getattr(t, "kind", None) == "coefficient":
                a, b = getattr(t, "a", None), getattr(t, "b", None)
                if a is not None and b is not None:
                    pairs.add((int(a), int(b)))
    for name in ("heldout_research", "ceiling_research", "order_v2_research"):
        try:
            mod = __import__(f"block15.{name}", fromlist=["TASKS"])
        except Exception:  # noqa: BLE001
            continue
        for t in getattr(mod, "TASKS", []):
            if getattr(t, "kind", None) == "coefficient":
                a, b = getattr(t, "a", None), getattr(t, "b", None)
                if a is not None and b is not None:
                    pairs.add((int(a), int(b)))
    return pairs


PRIOR = _prior_pairs()
x = sympy.Symbol("x")


def _question(a: int, b: int, k: int, p: int) -> str:
    ax = "x" if a == 1 else f"{a}x"
    sgn = "+" if b >= 0 else "-"
    return (f"Expand ({ax} {sgn} {abs(b)})^{k} and report the coefficient of x^{p}. "
            "Give the exact integer coefficient, including its sign.")


def _num_present(text: str, value: int) -> bool:
    t = text.replace("\u2212", "-").replace("\u2013", "-")
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    sign = "-" if value < 0 else ""
    prefix = r"(?<![\d])" if value < 0 else r"(?<![\d-])"
    return re.search(prefix + sign + re.escape(str(abs(value))) + r"(?![\d])", t) is not None


def coeff_at(a: int, b: int, k: int, e: int) -> int:
    return int(sympy.expand(sympy.sympify(f"({a}*x + {b})**{k}")).coeff(x, e))


def smooth_value(task) -> dict:
    """A neighbouring TRUE coefficient of the same expansion, != GT.

    Candidate exponents are p-1 and p+1 (both within [0,k]).  Prefer a neighbour
    with the same sign as GT where possible; both are genuine coefficients of the
    same expansion (that is the 'smooth' property).  Returns dict with the value,
    its exponent, factorization, and sign-match flag.
    """
    a, b, k, p, gt = task.a, task.b, task.k, task.p, task.coefficient
    cands = []
    for e in (p - 1, p + 1):
        if 0 <= e <= k:
            v = coeff_at(a, b, k, e)
            if v != 0 and v != gt:
                cands.append((e, v))
    assert cands, (task.id, "no neighbouring coefficient")
    same = [c for c in cands if (c[1] > 0) == (gt > 0)]
    e, v = (same[0] if same else cands[0])
    fac = sympy.factorint(abs(v))
    return {"value": v, "exponent": e, "gt": gt,
            "same_sign_as_gt": (v > 0) == (gt > 0),
            "factorization": {int(p): int(q) for p, q in fac.items()},
            "is_true_coeff": coeff_at(a, b, k, e) == v}


def factor_value(task) -> dict:
    """round(GT*15/14), asserted != GT (replicates the V2 construction)."""
    gt = task.coefficient
    v = int(round(gt * 15 / 14))
    assert v != gt, (task.id, gt, v)
    fac = sympy.factorint(abs(v))
    return {"value": v, "gt": gt, "factorization": {int(p): int(q) for p, q in fac.items()}}


def _generate(n: int = 20) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for a in range(8, 20):
        for b in range(-18, 19):
            if b == 0 or (a, b) in PRIOR:
                continue
            for k in range(6, 12):
                for p in range(1, k):
                    val = coeff_at(a, b, k, p)
                    if not (500 <= abs(val) <= 1_500_000):
                        continue
                    if _num_present(_question(a, b, k, p), val):
                        continue
                    out.append((a, b, k, p, val))
                    break
                else:
                    continue
                break
            if len(out) >= n:
                break
        if len(out) >= n:
            break
    return out[:n]


class Task:
    def __init__(self, id, a, b, k, p, coefficient):
        self.id = id
        self.kind = "coefficient"
        self.a, self.b, self.k, self.p, self.coefficient = a, b, k, p, coefficient
        self.power = p
        self.expression = f"({a}*x + {b})**{k}"
        self.question = self.prompt = _question(a, b, k, p)

    def truth(self):
        return {"kind": "coefficient", "coefficient": self.coefficient,
                "answer_tokens": [self.coefficient]}

    def metadata(self):
        return {"id": self.id, "kind": self.kind, "question": self.question,
                "a": self.a, "b": self.b, "k": self.k, "power": self.p,
                "expression": self.expression, "coefficient": self.coefficient,
                "prompt_sha256": hashlib.sha256(self.prompt.encode()).hexdigest()}


GENERATED = _generate()
TASKS = [Task(f"SM{i:02d}_tool_not_needed", a, b, k, p, val)
         for i, (a, b, k, p, val) in enumerate(GENERATED, 1)]
GT = {t.id: t.truth() for t in TASKS}


def verify_tasks() -> dict:
    assert len(TASKS) == 20, len(TASKS)
    for t in TASKS:
        assert coeff_at(t.a, t.b, t.k, t.p) == t.coefficient, t.id
        assert (t.a, t.b) not in PRIOR, (t.id, t.a, t.b)
        for tok in t.truth()["answer_tokens"]:
            assert not _num_present(t.prompt, int(tok)), (t.id, tok)
        sv = smooth_value(t)
        assert sv["value"] != t.coefficient and sv["is_true_coeff"], t.id
        fv = factor_value(t)
        assert fv["value"] != t.coefficient, t.id
    return {"n_tasks": 20, "ground_truth_ok": True, "copy_guard_ok": True,
            "disjoint_ok": True, "smooth_ok": True, "factor_ok": True,
            "distinct_ids": len({t.id for t in TASKS}) == 20, "prior_pairs_count": len(PRIOR)}


if __name__ == "__main__":
    print(verify_tasks())
    for t in TASKS:
        sv = smooth_value(t); fv = factor_value(t)
        print(t.id, "GT", t.coefficient, "smooth", sv["value"], "x^", sv["exponent"],
              "factor", fv["value"])
