"""Derivation-aware variant of the Round 3 R3B check for the QAD comparison.

Round 4 re-scores the stored Round 3 R3B answer under two readings:

* **strict** -- exactly the Round 3 R3B rule: only ``final_answer`` is
  inspected, so the status stays directly comparable with Round 3 numbers;
* **combined** -- the same objective facts are also searched in the
  derivation text, reporting whether the model reached the counterexample in
  its derivation even when the ``final_answer`` field was truncated.

The strict result is never overwritten by the combined reading.  Both
statuses are returned.  Only the pure helpers of ``block15.round3`` are
reused by import; ``independent_check`` and every other existing function are
untouched.  The status vocabulary matches Round 3: ``objective_partial``
passes the objective counterexample facts, ``objective_fail`` does not; the
minimality argument itself remains a manual-review question in both readings.
"""

from __future__ import annotations

import sympy

from block15.round3 import _answer_text, _derivation_text, _number_present
from block15.round3_tasks import Round3Task

R3B_TASK_ID = "R3B_counterexample_minimality"

_MINIMALITY_TOKENS = ("minimal", "smallest", "preceding", "previous")


def _r3b_facts() -> dict:
    """Independently compute the R3B counterexample facts with SymPy."""

    values: list[dict] = []
    first: int | None = None
    first_value: int | None = None
    for k in range(0, 101):
        value = k * k + k + 101
        if not sympy.isprime(value):
            first = k
            first_value = value
            break
        values.append({"n": k, "value": value, "prime": True})
    factors = sympy.factorint(first_value) if first_value is not None else None
    return {
        "first_n": first,
        "first_value": first_value,
        "factors": factors,
        "preceding": values,
    }


def _factorization_present(haystack: str) -> bool:
    compact = haystack.replace(" ", "")
    if "11^2" in compact or "11**2" in compact or "11*11" in compact:
        return True
    return _number_present(haystack, 11) and (
        "factor" in haystack.lower() or "=" in haystack
    )


def _mentions_minimality(haystack: str) -> bool:
    return any(token in haystack.lower() for token in _MINIMALITY_TOKENS)


def _status_from(n_ok: bool, value_ok: bool, factor_ok: bool) -> str:
    return (
        "objective_partial"
        if n_ok and value_ok and factor_ok
        else "objective_fail"
    )


def r3b_derivation_aware(
    task: Round3Task, final: dict, tool: dict | None = None
) -> dict:
    """Score the R3B answer strictly (final answer only) and combined
    (final answer plus derivation).

    ``tool`` is accepted for signature parity with
    ``block15.round3.independent_check`` and is unused, exactly as the Round 3
    R3B branch ignores it.  The input ``final`` is never mutated.
    """

    if task.id != R3B_TASK_ID:
        raise ValueError(
            f"derivation-aware scorer is registered for {R3B_TASK_ID!r}, "
            f"got {task.id!r}"
        )

    text = _answer_text(final)
    derivation = _derivation_text(final)
    combined_text = f"{text} {derivation}"
    facts = _r3b_facts()
    first_n = facts["first_n"]
    first_value = facts["first_value"]
    preceding = facts["preceding"]

    strict = {
        "final_contains_first_n": (
            first_n is not None and _number_present(text, first_n)
        ),
        "final_contains_counterexample_value": (
            first_value is not None and _number_present(text, first_value)
        ),
        "final_contains_factorization": _factorization_present(text),
        "derivation_contains_first_n": (
            first_n is not None and _number_present(derivation, first_n)
        ),
        "mentions_all_preceding_values": (
            all(_number_present(combined_text, item["value"]) for item in preceding)
            if preceding
            else False
        ),
        "mentions_minimality_language": _mentions_minimality(combined_text),
    }
    strict["status"] = _status_from(
        strict["final_contains_first_n"],
        strict["final_contains_counterexample_value"],
        strict["final_contains_factorization"],
    )

    combined = {
        "final_contains_first_n": (
            first_n is not None and _number_present(combined_text, first_n)
        ),
        "final_contains_counterexample_value": (
            first_value is not None
            and _number_present(combined_text, first_value)
        ),
        "final_contains_factorization": _factorization_present(combined_text),
        "derivation_contains_first_n": (
            first_n is not None and _number_present(derivation, first_n)
        ),
        "mentions_all_preceding_values": (
            all(_number_present(combined_text, item["value"]) for item in preceding)
            if preceding
            else False
        ),
        "mentions_minimality_language": _mentions_minimality(combined_text),
    }
    combined["status"] = _status_from(
        combined["final_contains_first_n"],
        combined["final_contains_counterexample_value"],
        combined["final_contains_factorization"],
    )

    return {
        "task_id": task.id,
        "method": task.verification,
        "expected": task.expected,
        "observed_answer": text,
        "observed_derivation": derivation,
        "observed_confidence": final["confidence"],
        "observed_uncertainty": final["uncertainty"],
        "computed_expected": {
            "first_n": first_n,
            "value": first_value,
            "factorization": facts["factors"],
            "preceding": preceding,
        },
        "strict": strict,
        "combined": combined,
        "strict_status": strict["status"],
        "combined_status": combined["status"],
    }


__all__ = ["R3B_TASK_ID", "r3b_derivation_aware"]