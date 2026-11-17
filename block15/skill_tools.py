"""Allowlisted executable tool for the skill-tool study.

A single general-purpose procedure: find the first n in [0, n_max] for which a
quadratic f(n) = a*n^2 + b*n + c is composite, with its factorization.  It is
pure SymPy arithmetic.  It contains NO task-specific answers and uses no eval,
exec, or model-generated code.  The model may only request it by name with
integer arguments.
"""

from __future__ import annotations

import sympy


def first_composite_quadratic(a: int, b: int, c: int, n_max: int) -> dict:
    """First composite value of f(n)=a*n^2+b*n+c for integer n in [0, n_max].

    Returns ``{"n": int, "value": int, "factors": [int, ...]}`` for the first
    composite (factors are the distinct prime factors), or ``{"none": True}``
    if none is composite in the range.  Inputs are validated strictly: a, b, c
    must be ints (bool excluded); n_max must be an int with 0 < n_max <= 128.
    """
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(c, bool) \
            or isinstance(n_max, bool):
        raise ValueError("arguments must be integers, not booleans")
    if not all(isinstance(v, int) for v in (a, b, c, n_max)):
        raise ValueError("a, b, c, n_max must be integers")
    if not (0 < n_max <= 128):
        raise ValueError("n_max must satisfy 0 < n_max <= 128")

    for n in range(0, n_max + 1):
        value = a * n * n + b * n + c
        if value > 1 and not sympy.isprime(value):
            factors = sorted(int(p) for p in sympy.factorint(value))
            return {"n": n, "value": value, "factors": factors}
    return {"none": True}


TOOL_NAME = "first_composite_quadratic"

# The tool schema sent to the model.  IDENTICAL in L3 and L0 (asserted in
# skill_cards.py).  The description is generic and contains no answer tokens.
TOOL_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool_request"],
    "properties": {
        "tool_request": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "arguments"],
                    "properties": {
                        "tool": {"const": TOOL_NAME},
                        "arguments": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["a", "b", "c", "n_max"],
                            "properties": {
                                "a": {"type": "integer"},
                                "b": {"type": "integer"},
                                "c": {"type": "integer"},
                                "n_max": {"type": "integer", "minimum": 1, "maximum": 128},
                            },
                        },
                    },
                },
            ]
        },
        "missing_process": {
            "enum": ["need_tool", "no_tool_needed", "unclear"],
        },
    },
}
