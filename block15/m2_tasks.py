"""Frozen fresh 30-task set for M2 (card intervention), disjoint from all prior sets.

20 tool-needed bounded-minimality tasks (first composite n<=64) and 10 tool-not-needed
binomial coefficient tasks. Ground truth by SymPy; copy guard; disjoint from Round 3,
H1-H5, C01-M08, V2C*/V2M*, TFM*/TFC*.
"""
from __future__ import annotations

import hashlib
import re

import sympy

# All prior minimality (a,b,c) and coefficient (a,b) parameter sets.
PRIOR_MIN = {
    (1,1,1301),(2,2,1279),(1,5,1187),(1,1,1091),(1,3,1213),(3,3,1013),
    (1,1,1427),(2,2,1447),(1,3,1279),(2,2,1009),(1,1,101),(1,1,1277),
    (1,5,1217),(1,7,1163),(1,5,1223),(2,6,1031),(4,2,1013),(1,3,1429),
    (1,1,1481),(1,1,1487),(3,3,1033),(2,4,1483),(4,4,1163),(5,5,1021),
    (2,6,1193),(5,5,1399),(3,3,1283),
    (1,1,1607),(1,3,1549),(1,5,1277),(1,7,1289),(1,9,1087),(1,11,1277),
    (2,0,1031),(2,2,1567),(2,4,1621),(2,6,1109),(2,8,1009),(2,10,1021),
    (3,3,1453),(3,9,1009),(4,0,1087),(4,2,1217),(4,4,1193),(4,6,1153),
    (4,8,1019),(4,10,1187),
}
PRIOR_COEFF = {
    (2,-3),(1,-4),(1,5),(3,-4),(5,2),(2,5),(4,-3),(3,2),(6,-1),(2,-5),
    (5,-3),(4,1),(3,5),(6,-5),(2,7),(1,4),(2,-7),(5,-2),(1,-6),(4,3),
    (7,-2),(2,9),(3,-5),(6,5),(1,8),(5,4),(4,-7),(7,3),(3,6),(6,-7),
    (2,-9),(2,-8),(2,-6),(2,-4),(2,-2),(2,1),(2,2),(2,4),(2,6),(2,8),
}

MINIMALITY = [
    (1,1,2237,3,2249,[13,173]),(1,3,2203,4,2231,[23,97]),(1,5,2207,3,2231,[23,97]),
    (1,7,2333,3,2363,[17,139]),(1,9,2131,3,2167,[11,197]),(1,11,2087,4,2147,[19,113]),
    (2,0,2129,3,2147,[19,113]),(2,2,2239,3,2263,[31,73]),(2,4,2011,3,2041,[13,157]),
    (2,6,2273,4,2329,[17,137]),(2,8,2029,3,2071,[19,109]),(2,10,2239,7,2407,[29,83]),
    (3,3,2063,4,2123,[11,193]),(3,9,2099,4,2183,[37,59]),(4,0,2083,3,2119,[13,163]),
    (4,2,2063,3,2105,[5,421]),(4,4,2003,3,2051,[7,293]),(4,6,2389,3,2443,[7,349]),
    (4,8,2099,3,2159,[17,127]),(4,10,2207,13,3013,[23,131]),
]
COEFFICIENT = [
    (4,-9,6,1,-1417176),(4,-8,6,1,-786432),(4,-6,6,1,-186624),
    (4,-5,6,1,-75000),(4,-4,6,1,-24576),(4,-2,6,1,-768),
    (4,-1,6,3,-1280),(4,2,6,1,768),(4,4,6,1,24576),(4,5,6,1,75000),
]


def _min_q(a, b, c):
    terms = ["n^2" if a == 1 else f"{a}n^2"]
    if b:
        terms.append("n" if b == 1 else f"{b}n")
    return ("Let f(n) = " + " + ".join(terms) + f" + {c}. Find the smallest integer "
            "n >= 0 such that f(n) is composite. Give n, the value f(n), and the complete "
            "prime factorization of f(n).")


def _coeff_q(a, b, k, p):
    ax = "x" if a == 1 else f"{a}x"
    sgn = "+" if b >= 0 else "-"
    return (f"Expand ({ax} {sgn} {abs(b)})^{k} and report the coefficient of x^{p}. "
            "Give the exact integer coefficient, including its sign.")


class Task:
    def __init__(self, id, kind, question, **kw):
        self.id, self.kind, self.question = id, kind, question
        self.prompt = question
        self.a = self.b = self.c = self.expression = self.power = self.coefficient = None
        self.n = self.value = self.primes = None
        for k, v in kw.items():
            setattr(self, k, v)

    def truth(self):
        if self.kind == "minimality":
            return {"kind": "minimality", "n": self.n, "value": self.value,
                    "primes": list(self.primes),
                    "answer_tokens": [self.n, self.value, *self.primes]}
        return {"kind": "coefficient", "coefficient": self.coefficient,
                "answer_tokens": [self.coefficient]}

    def metadata(self):
        return {"id": self.id, "kind": self.kind, "question": self.question,
                "prompt_sha256": hashlib.sha256(self.prompt.encode()).hexdigest(),
                "a": self.a, "b": self.b, "c": self.c,
                "expression": self.expression, "power": self.power,
                "coefficient": self.coefficient, "n": self.n,
                "value": self.value, "primes": self.primes}


def build_tasks():
    out = []
    for i, (a, b, c, n, v, pr) in enumerate(MINIMALITY, 1):
        out.append(Task(f"M2M{i:02d}_tool_needed", "minimality", _min_q(a, b, c),
                        a=a, b=b, c=c, n=n, value=v, primes=pr))
    for i, (a, b, k, p, coef) in enumerate(COEFFICIENT, 1):
        out.append(Task(f"M2C{i:02d}_tool_not_needed", "coefficient", _coeff_q(a, b, k, p),
                        a=a, b=b, expression=f"({a}*x + {b})**{k}", power=p,
                        coefficient=coef))
    return out


TASKS = build_tasks()
TOOL_NEEDED_IDS = tuple(t.id for t in TASKS if t.kind == "minimality")
TOOL_NOT_NEEDED_IDS = tuple(t.id for t in TASKS if t.kind == "coefficient")
GT = {t.id: t.truth() for t in TASKS}


def _num_present(text, value):
    t = text.replace("\u2212", "-").replace("\u2013", "-")
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    sign = "-" if value < 0 else ""
    prefix = r"(?<![\d])" if value < 0 else r"(?<![\d-])"
    return re.search(prefix + sign + re.escape(str(abs(value))) + r"(?![\d])", t) is not None


def verify_tasks():
    x = sympy.Symbol("x")
    for (a, b, c, en, ev, ep), t in zip(MINIMALITY, [t for t in TASKS if t.kind == "minimality"]):
        found = None
        for n in range(0, 65):
            v = a*n*n + b*n + c
            if v > 1 and not sympy.isprime(v):
                fac = sympy.factorint(v)
                found = (n, v, sorted(int(p) for p in fac), all(int(e)==1 for e in fac.values()))
                break
        assert found and found[:3] == (en, ev, ep) and found[3], (t.id, found)
        assert (a, b, c) not in PRIOR_MIN
    for (a, b, k, p, coef), t in zip(COEFFICIENT, [t for t in TASKS if t.kind == "coefficient"]):
        val = int(sympy.expand(sympy.sympify(f"({a}*x + {b})**{k}")).coeff(x, p))
        assert val == coef and (a, b) not in PRIOR_COEFF, (t.id, val)
    for t in TASKS:
        for tok in t.truth()["answer_tokens"]:
            assert not _num_present(t.prompt, int(tok)), (t.id, tok)
    return {"n_tasks": len(TASKS), "tool_needed": 20, "tool_not_needed": 10,
            "ground_truth_ok": True, "copy_guard_ok": True,
            "disjoint_ok": True, "distinct_ids": len({t.id for t in TASKS}) == 30}
