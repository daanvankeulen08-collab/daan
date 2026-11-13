"""Tests for independent verification."""

from __future__ import annotations

from mdl.symbolic import expand_expression
from mdl.verifier import VerificationStatus, verify_symbolic_expand


def test_correct_result_passes():
    expression = "(x + 1)**8"
    result = expand_expression(expression)
    report = verify_symbolic_expand(expression, result)
    assert report.status is VerificationStatus.PASSED
    assert report.difference == "0"
    assert "algebraic_difference_zero=ok" in report.detail


def test_tampered_expansion_fails():
    expression = "(x + 1)**8"
    result = expand_expression(expression)
    tampered = dict(result)
    tampered["expanded"] = "x**8 + 1"
    report = verify_symbolic_expand(expression, tampered)
    assert report.status is VerificationStatus.FAILED
    assert report.difference != "0"


def test_unparseable_result_is_not_verifiable():
    expression = "(x + 1)**8"
    result = dict(expand_expression(expression))
    result["expanded"] = "sin(x)"
    report = verify_symbolic_expand(expression, result)
    assert report.status is VerificationStatus.NOT_VERIFIABLE


def test_inconsistent_metadata_fails():
    expression = "(x + 1)**8"
    result = dict(expand_expression(expression))
    result["term_count"] = 0
    report = verify_symbolic_expand(expression, result)
    assert report.status is VerificationStatus.FAILED
    assert "term_count_consistent=FAILED" in report.detail


def test_missing_fields_are_not_verifiable():
    report = verify_symbolic_expand("(x+1)**2", {"expanded": "x**2 + 2*x + 1"})
    assert report.status is VerificationStatus.NOT_VERIFIABLE
