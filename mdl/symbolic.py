"""The single allowlisted tool: exact polynomial expansion via SymPy."""

from __future__ import annotations

import sympy

from .errors import ToolExecutionError, ToolValidationError
from .expr_parser import parse_expression, validate_expression

MAX_TERMS = 2000
MAX_OPS = 20000


def expand_expression(expression: str) -> dict:
    """Expand a restricted polynomial expression exactly.

    The result is a plain ``dict`` so it can cross a process boundary.  The
    caller re-validates it with :class:`mdl.schemas.SymbolicExpandResult`.
    """

    expr = parse_expression(expression)
    expanded = sympy.expand(expr)
    validate_expression(expanded)

    terms = list(sympy.Add.make_args(expanded))
    if len(terms) > MAX_TERMS:
        raise ToolValidationError(
            f"expansion has more than {MAX_TERMS} terms"
        )
    operation_count = int(sympy.count_ops(expanded))
    if operation_count > MAX_OPS:
        raise ToolValidationError(
            f"expansion exceeds {MAX_OPS} operations"
        )

    variables = sorted(symbol.name for symbol in expr.free_symbols)

    if variables:
        try:
            total_degree = int(
                sympy.Poly(expanded, *[sympy.Symbol(v) for v in variables]).total_degree()
            )
        except sympy.PolynomialError as exc:  # pragma: no cover - defensive
            raise ToolExecutionError(f"result is not a polynomial: {exc}") from exc
    else:
        total_degree = 0

    structured_terms: list[dict] = []
    for term in terms:
        coefficient, remainder = term.as_coeff_Mul()
        if not coefficient.is_Integer:
            raise ToolExecutionError("non-integer coefficient encountered")
        monomial: dict[str, int] = {}
        if remainder != 1:
            for factor in sympy.Mul.make_args(remainder):
                if isinstance(factor, sympy.Symbol):
                    monomial[factor.name] = monomial.get(factor.name, 0) + 1
                elif (
                    isinstance(factor, sympy.Pow)
                    and isinstance(factor.base, sympy.Symbol)
                    and isinstance(factor.exp, sympy.Integer)
                ):
                    exponent = int(factor.exp)
                    if exponent <= 0:
                        raise ToolExecutionError("invalid monomial exponent")
                    monomial[factor.base.name] = (
                        monomial.get(factor.base.name, 0) + exponent
                    )
                else:  # pragma: no cover - defensive
                    raise ToolExecutionError(
                        f"unexpected monomial factor {factor!r}"
                    )
        structured_terms.append(
            {"coefficient": str(int(coefficient)), "monomial": monomial}
        )

    return {
        "expression": str(expr),
        "expanded": str(expanded),
        "variables": variables,
        "term_count": len(terms),
        "total_degree": total_degree,
        "terms": structured_terms,
    }
