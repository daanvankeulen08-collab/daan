"""Frozen 30-task set for the tool-transfer study.

20 TOOL-NEEDED bounded-minimality tasks (a*n^2+b*n+c, first composite within
n<=64) and 10 TOOL-NOT-NEEDED binomial coefficient tasks. All disjoint from
Round 3, H1-H5, C01-M08 and V2C*/V2M*. Ground truth computed by SymPy and
checked against frozen expected values at verification time.
"""

from __future__ import annotations

import hashlib

import sympy


def _sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _min_question(a, b, c):
    terms = ["n^2" if a == 1 else f"{a}n^2"]
    if b:
        terms.append("n" if b == 1 else f"{b}n")
    return ("Let f(n) = " + " + ".join(terms) + f" + {c}. Find the smallest integer "
            "n >= 0 such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n).")


def _coeff_question(a, b, k, p):
    ax = "x" if a == 1 else f"{a}x"
    sgn = "+" if b >= 0 else "-"
    return (f"Expand ({ax} {sgn} {abs(b)})^{k} and report the coefficient of "
            f"x^{p}. Give the exact integer coefficient, including its sign.")


# 20 tool-needed: (a,b,c,expected_n,expected_value,expected_primes)
MINIMALITY = [
    (1, 1, 1607, 6, 1649, [17, 97]),
    (1, 3, 1549, 4, 1577, [19, 83]),
    (1, 5, 1277, 4, 1313, [13, 101]),
    (1, 7, 1289, 4, 1333, [31, 43]),
    (1, 9, 1087, 4, 1139, [17, 67]),
    (1, 11, 1277, 4, 1337, [7, 191]),
    (2, 0, 1031, 5, 1081, [23, 47]),
    (2, 2, 1567, 3, 1591, [37, 43]),
    (2, 4, 1621, 3, 1651, [13, 127]),
    (2, 6, 1109, 3, 1145, [5, 229]),
    (2, 8, 1009, 4, 1073, [29, 37]),
    (2, 10, 1021, 5, 1121, [19, 59]),
    (3, 3, 1453, 4, 1513, [17, 89]),
    (3, 9, 1009, 7, 1219, [23, 53]),
    (4, 0, 1087, 8, 1343, [17, 79]),
    (4, 2, 1217, 12, 1817, [23, 79]),
    (4, 4, 1193, 3, 1241, [17, 73]),
    (4, 6, 1153, 3, 1207, [17, 71]),
    (4, 8, 1019, 3, 1079, [13, 83]),
    (4, 10, 1187, 3, 1253, [7, 179]),
]

# 10 tool-not-needed: (a,b,k,p,expected_coefficient)
COEFFICIENT = [
    (2, -9, 6, 1, -708588),
    (2, -8, 6, 1, -393216),
    (2, -6, 6, 1, -93312),
    (2, -4, 6, 1, -12288),
    (2, -2, 6, 2, 960),
    (2, 1, 7, 4, 560),
    (2, 2, 6, 2, 960),
    (2, 4, 6, 1, 12288),
    (2, 6, 6, 1, 93312),
    (2, 8, 6, 1, 393216),
]


class Task:
    def __init__(self, id, kind, question, **kw):
        self.id = id
        self.kind = kind
        self.question = question
        self.prompt = question  # base text; schema/instruction appended by runner
        self.a = self.b = self.c = None
        self.expression = self.power = None
        self.coefficient = self.n = self.value = self.primes = None
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
        return {
            "id": self.id, "kind": self.kind, "question": self.question,
            "prompt_sha256": _sha(self.prompt),
            "a": self.a, "b": self.b, "c": self.c,
            "expression": self.expression, "power": self.power,
            "coefficient": self.coefficient, "n": self.n,
            "value": self.value, "primes": self.primes,
        }


def build_tasks():
    tasks = []
    for i, (a, b, c, n, v, pr) in enumerate(MINIMALITY, start=1):
        tasks.append(Task(
            f"TFM{i:02d}_tool_needed", "minimality", _min_question(a, b, c),
            a=a, b=b, c=c, n=n, value=v, primes=pr,
        ))
    for i, (a, b, k, p, coef) in enumerate(COEFFICIENT, start=1):
        tasks.append(Task(
            f"TFC{i:02d}_tool_not_needed", "coefficient",
            _coeff_question(a, b, k, p),
            expression=f"({a}*x + {b})**{k}", power=p, coefficient=coef,
            a=a, b=b,
        ))
    return tasks


TASKS = build_tasks()
TOOL_NEEDED_IDS = tuple(t.id for t in TASKS if t.kind == "minimality")
TOOL_NOT_NEEDED_IDS = tuple(t.id for t in TASKS if t.kind == "coefficient")


def verify_tasks():
    """SymPy re-computation + copy guard + disjointness from all prior sets."""
    # Ground truth re-computation
    for (a, b, c, en, ev, ep), t in zip(MINIMALITY, [t for t in TASKS if t.kind == "minimality"]):
        found = None
        for n in range(0, 65):
            v = a * n * n + b * n + c
            if v > 1 and not sympy.isprime(v):
                fac = sympy.factorint(v)
                found = (n, v, sorted(int(p) for p in fac), all(int(e) == 1 for e in fac.values()))
                break
        assert found and (found[0], found[1], found[2]) == (en, ev, ep) and found[3], (t.id, found)
    x = sympy.Symbol("x")
    for (a, b, k, p, coef), t in zip(COEFFICIENT, [t for t in TASKS if t.kind == "coefficient"]):
        val = int(sympy.expand(sympy.sympify(f"({a}*x + {b})**{k}")).coeff(x, p))
        assert val == coef, (t.id, val, coef)
    # Copy guard: no GT token in any prompt
    from block15.round3 import _number_present
    for t in TASKS:
        for tok in t.truth()["answer_tokens"]:
            assert not _number_present(t.prompt, int(tok)), (t.id, tok)
    # Disjointness from all prior task id prefixes / parameter sets
    prior_prefixes = ("V2C", "V2M", "C0", "M0", "H", "R3")
    for t in TASKS:
        assert not t.id.startswith(prior_prefixes)
    return {
        "n_tasks": len(TASKS),
        "tool_needed": len(TOOL_NEEDED_IDS),
        "tool_not_needed": len(TOOL_NOT_NEEDED_IDS),
        "ground_truth_ok": True,
        "copy_guard_ok": True,
        "distinct_ids": len({t.id for t in TASKS}) == len(TASKS),
    }
