"""Fresh 20-task coefficient set for Integration V2.

20 tool-inapplicable binomial-coefficient tasks, SymPy ground truth, disjoint
from every prior coefficient (a,b) set including the 10 Block-B integration tasks.
Copy guard: no ground-truth token in any prompt. Deterministic generation in
committed code; no scratch-derived hardcoded list.
"""
from __future__ import annotations

import hashlib
import re

import sympy

from block15 import tool_transfer_tasks as TT
from block15 import m2_tasks as M2T
from block15 import integration_tasks as IT


def _prior_pairs() -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set(M2T.PRIOR_COEFF)
    for mod in (TT, M2T, IT):
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


def _generate(n: int = 20) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for a in range(6, 16):
        for b in range(-15, 16):
            if b == 0 or (a, b) in PRIOR:
                continue
            for k in range(6, 12):
                for p in range(1, k):
                    val = int(sympy.expand(sympy.sympify(f"({a}*x + {b})**{k}")).coeff(x, p))
                    if not (500 <= abs(val) <= 1_500_000):
                        continue
                    q = _question(a, b, k, p)
                    if _num_present(q, val):
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
TASKS = [Task(f"V2I{i:02d}_tool_not_needed", a, b, k, p, val)
         for i, (a, b, k, p, val) in enumerate(GENERATED, 1)]
GT = {t.id: t.truth() for t in TASKS}


def verify_tasks() -> dict:
    assert len(TASKS) == 20, len(TASKS)
    for t in TASKS:
        val = int(sympy.expand(sympy.sympify(t.expression)).coeff(x, t.p))
        assert val == t.coefficient, (t.id, val)
        assert (t.a, t.b) not in PRIOR, (t.id, t.a, t.b)
        for tok in t.truth()["answer_tokens"]:
            assert not _num_present(t.prompt, int(tok)), (t.id, tok)
    return {"n_tasks": 20, "ground_truth_ok": True, "copy_guard_ok": True,
            "disjoint_ok": True, "distinct_ids": len({t.id for t in TASKS}) == 20,
            "prior_pairs_count": len(PRIOR)}


if __name__ == "__main__":
    print(verify_tasks())
    for t in TASKS:
        print(t.id, t.a, t.b, t.k, t.p, t.coefficient)
