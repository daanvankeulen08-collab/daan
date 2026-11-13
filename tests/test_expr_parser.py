"""Tests for the closed symbolic parser."""

from __future__ import annotations

import pytest
import sympy

from mdl.expr_parser import ExpressionError, parse_expression


def test_parses_and_expands_simple_polynomial():
    parsed = parse_expression("(x + 1)**8")
    assert str(sympy.expand(parsed)) == (
        "x**8 + 8*x**7 + 28*x**6 + 56*x**5 + 70*x**4 "
        "+ 56*x**3 + 28*x**2 + 8*x + 1"
    )


def test_operator_precedence_and_unary_minus():
    assert sympy.expand(parse_expression("2 + 3 * 4")) == 14
    assert str(parse_expression("-x**2")) == "-x**2"
    assert sympy.expand(parse_expression("2**3**2")) == 512


def test_whitespace_and_multiple_variables():
    expression = parse_expression("( x + y ) ** 2")
    assert sympy.expand(expression) == sympy.expand(
        sympy.Symbol("x") ** 2
        + 2 * sympy.Symbol("x") * sympy.Symbol("y")
        + sympy.Symbol("y") ** 2
    )


@pytest.mark.parametrize(
    "text",
    [
        "x/y",
        "sin(x)",
        "2.5*x",
        "x**-1",
        "x**33",
        "2**100",
        "__import__('os')",
        "x" * 201,
        "x y",
        "x^2",
        "(x+1",
        "x +",
        "",
    ],
)
def test_rejects_invalid_or_unsafe_expressions(text):
    with pytest.raises(ExpressionError):
        parse_expression(text)


def test_rejects_too_many_variables():
    with pytest.raises(ExpressionError):
        parse_expression("a+b+c+d+e+f+g+h+i+j+k")


def test_rejects_oversized_integer_literal():
    with pytest.raises(ExpressionError):
        parse_expression("1234567890123 * x")
