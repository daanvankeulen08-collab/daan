"""Independent verification of tool results.

The verifier never trusts the model or the tool output.  It recomputes the
expansion from the *original* expression with SymPy, checks that the algebraic
difference with the reported result is exactly zero, and reconstructs the
result from the structured term list as a second, independent path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import sympy
from pydantic import ValidationError

from .expr_parser import ExpressionError, parse_expression
from .schemas import SymbolicExpandResult, Term

METHOD = (
    "independent SymPy expand + algebraic zero difference "
    "+ structured coefficient reconstruction"
)


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_VERIFIABLE = "not_verifiable"


@dataclass(frozen=True)
class VerificationReport:
    status: VerificationStatus
    method: str
    detail: str
    difference: str | None = None
    independent_expansion: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "method": self.method,
            "detail": self.detail,
            "difference": self.difference,
            "independent_expansion": self.independent_expansion,
        }


def _poly_degree(expression: sympy.Expr) -> int:
    variables = sorted(expression.free_symbols, key=lambda s: s.name)
    if not variables:
        return 0
    if expression == 0:
        return 0
    return int(sympy.Poly(expression, *variables).total_degree())


def _reconstruct(terms: list[Term]) -> sympy.Expr:
    total = sympy.Integer(0)
    for term in terms:
        coefficient = sympy.Rational(term.coefficient)
        monomial = sympy.Integer(1)
        for name, exponent in term.monomial.items():
            if not isinstance(name, str) or not name:
                raise ValueError("invalid monomial variable name")
            if not isinstance(exponent, int) or exponent < 0:
                raise ValueError("invalid monomial exponent")
            monomial *= sympy.Symbol(name) ** exponent
        total += coefficient * monomial
    return sympy.expand(total)


def verify_symbolic_expand(
    expression: str,
    result: SymbolicExpandResult | dict,
) -> VerificationReport:
    """Verify a ``symbolic_expand`` result independently of the model."""

    try:
        if isinstance(result, SymbolicExpandResult):
            data = result
        else:
            data = SymbolicExpandResult.model_validate(result)
    except (ValidationError, TypeError, ValueError) as exc:
        return VerificationReport(
            status=VerificationStatus.NOT_VERIFIABLE,
            method=METHOD,
            detail=f"tool result could not be validated: {exc}",
        )

    # -- setup: parse the original and the reported expression -------------
    try:
        original = parse_expression(expression)
        independent = sympy.expand(original)
        reported = parse_expression(data.expanded)
        reconstructed = _reconstruct(data.terms)
    except (ExpressionError, ValueError, TypeError, sympy.SympifyError) as exc:
        return VerificationReport(
            status=VerificationStatus.NOT_VERIFIABLE,
            method=METHOD,
            detail=f"expression could not be parsed for verification: {exc}",
        )

    # -- independent checks -------------------------------------------------
    checks: dict[str, bool] = {}
    try:
        difference = sympy.simplify(independent - reported)
        checks["algebraic_difference_zero"] = difference == 0

        reconstruction_difference = sympy.expand(independent - reconstructed)
        checks["structured_reconstruction_matches"] = reconstruction_difference == 0

        source_difference = sympy.simplify(
            parse_expression(data.expression) - original
        )
        checks["reported_source_matches_request"] = source_difference == 0

        checks["term_count_consistent"] = data.term_count == len(data.terms)
        checks["degree_consistent"] = data.total_degree == _poly_degree(independent)
        checks["variables_consistent"] = sorted(data.variables) == sorted(
            symbol.name for symbol in original.free_symbols
        )
    except (ExpressionError, ValueError, TypeError, sympy.SympifyError) as exc:
        return VerificationReport(
            status=VerificationStatus.NOT_VERIFIABLE,
            method=METHOD,
            detail=f"verification computation failed: {exc}",
        )

    passed = all(checks.values())
    detail = "; ".join(
        f"{name}={'ok' if ok else 'FAILED'}" for name, ok in checks.items()
    )
    return VerificationReport(
        status=(
            VerificationStatus.PASSED if passed else VerificationStatus.FAILED
        ),
        method=METHOD,
        detail=detail,
        difference=str(difference),
        independent_expansion=str(independent),
    )
