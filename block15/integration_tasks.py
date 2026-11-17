"""Fresh, disjoint 10-task coefficient set for the integration study (Block B).

10 tool-inapplicable binomial-coefficient tasks ("expand (a*x+b)^k, coefficient
of x^p").  Ground truth by SymPy.  Disjoint from every prior coefficient task set
(Round 3 / H1-H5 / C01-M08 / V2C / TFC / M2C).  Copy guard: no ground-truth token
appears in any task prompt.  Deterministic generation in committed code; no
hardcoded list derived from scratch output.
"""
from __future__ import annotations

import hashlib
import re

import sympy

from block15 import tool_transfer_tasks as TT
from block15 import m2_tasks as M2T


def _prior_pairs() -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    # Explicit prior set carried through the project, plus all stored task modules.
    pairs |= set(M2T.PRIOR_COEFF)
    for mod in (TT, M2T):
        for t in getattr(mod, "TASKS", []):
            if getattr(t, "kind", None) == "coefficient":
                a, b = getattr(t, "a", None), getattr(t, "b", None)
                if a is not None and b is not None:
                    pairs.add((int(a), int(b)))
    # Any other research module that exposes coefficient tasks with a/b.
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


def _generate(n: int = 10) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for a in range(5, 13):
        for b in range(-12, 13):
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
    def __init__(self, id, a, b, k, p, coefficient, idx):
        self.id = id
        self.kind = "coefficient"
        self.a, self.b, self.k, self.p, self.coefficient = a, b, k, p, coefficient
        self.power = p
        self.expression = f"({a}*x + {b})**{k}"
        self.question = self.prompt = _question(a, b, k, p)
        self.idx = idx

    def truth(self):
        return {"kind": "coefficient", "coefficient": self.coefficient,
                "answer_tokens": [self.coefficient]}

    def metadata(self):
        return {"id": self.id, "kind": self.kind, "question": self.question,
                "a": self.a, "b": self.b, "k": self.k, "power": self.p,
                "expression": self.expression, "coefficient": self.coefficient,
                "prompt_sha256": hashlib.sha256(self.prompt.encode()).hexdigest()}


GENERATED = _generate()
TASKS = [Task(f"INT{i:02d}_tool_not_needed", a, b, k, p, val, i)
         for i, (a, b, k, p, val) in enumerate(GENERATED, 1)]
GT = {t.id: t.truth() for t in TASKS}


def verify_tasks() -> dict:
    assert len(TASKS) == 10, len(TASKS)
    for t in TASKS:
        val = int(sympy.expand(sympy.sympify(t.expression)).coeff(x, t.p))
        assert val == t.coefficient, (t.id, val)
        assert (t.a, t.b) not in PRIOR, (t.id, t.a, t.b)
        for tok in t.truth()["answer_tokens"]:
            assert not _num_present(t.prompt, int(tok)), (t.id, tok)
    return {"n_tasks": 10, "ground_truth_ok": True, "copy_guard_ok": True,
            "disjoint_ok": True, "distinct_ids": len({t.id for t in TASKS}) == 10,
            "prior_pairs_count": len(PRIOR)}


if __name__ == "__main__":
    print(verify_tasks())
    for t in TASKS:
        print(t.id, t.a, t.b, t.k, t.p, t.coefficient, "|", t.question)
