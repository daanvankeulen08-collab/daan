"""Tests for the Research Context Engine."""

from __future__ import annotations

import json

import pytest

from mdl.context_engine import (
    Assumption,
    Concept,
    HypothesisRef,
    Provenance,
    Relation,
    ResearchContext,
    StepLink,
    Uncertainty,
    compare_token_usage,
    estimate_tokens,
)
from mdl.errors import ContextError


def _context() -> ResearchContext:
    return ResearchContext(
        concepts=(
            Concept(
                name="x",
                definition="the symbolic variable under investigation",
                notation="x",
                domain="integers",
                units="dimensionless",
            ),
        ),
        relations=(
            Relation(
                lhs="(x + 1)**8",
                operator="=",
                rhs="x**8 + 8*x**7 + 28*x**6 + 56*x**5 + 70*x**4 "
                "+ 56*x**3 + 28*x**2 + 8*x + 1",
                conditions=("x is a symbolic variable",),
                exceptions=("the identity is not a numeric equality",),
            ),
        ),
        assumptions=(
            Assumption("x is a symbolic variable", kind="assumption"),
            Assumption("coefficients must be integers", kind="condition"),
            Assumption("the hypothesis is not restricted to x > 0", kind="negation"),
            Assumption("no exception for negative x is allowed", kind="exception"),
        ),
        notation=("x", "**", "non-negative coefficient"),
        units=("dimensionless",),
        domains=("integer polynomial coefficients",),
        hypotheses=(
            HypothesisRef(
                statement="All coefficients of (x + 1)**8 are non-negative.",
                status="supported",
                experiment_id="exp_1",
            ),
        ),
        uncertainties=(
            Uncertainty(
                statement="Only degree 8 was tested.",
                reason="single experiment",
                resolved=False,
            ),
        ),
        provenance=(
            Provenance(
                experiment_id="exp_1",
                step="hypothesis",
                source="lfm3",
                reference="step:1",
                timestamp="2026-11-10T20:00:00+00:00",
            ),
            Provenance(
                experiment_id="exp_1",
                step="verification",
                source="verifier",
                reference="step:4",
                timestamp="2026-11-10T20:00:01+00:00",
            ),
        ),
        step_links=(
            StepLink("hypothesis", "plan", "refines", "plan narrows the claim"),
            StepLink("verification", "interpretation", "supports", "verified result"),
        ),
    )


def test_encoding_reconstruction_roundtrip():
    context = _context()
    encoded = context.encode()
    decoded = ResearchContext.decode(encoded)
    assert decoded == context
    assert decoded.encode() == encoded


def test_conditions_and_negations_are_preserved():
    decoded = ResearchContext.decode(_context().encode())
    kinds = {assumption.kind for assumption in decoded.assumptions}
    assert kinds == {"assumption", "condition", "negation", "exception"}
    assert any(
        assumption.statement == "the hypothesis is not restricted to x > 0"
        for assumption in decoded.assumptions
    )


def test_symbolic_relations_are_preserved_verbatim():
    decoded = ResearchContext.decode(_context().encode())
    relation = decoded.relations[0]
    assert relation.lhs == "(x + 1)**8"
    assert relation.operator == "="
    assert relation.rhs.startswith("x**8 + 8*x**7")
    assert relation.conditions == ("x is a symbolic variable",)
    assert relation.exceptions == ("the identity is not a numeric equality",)


def test_provenance_is_preserved():
    decoded = ResearchContext.decode(_context().encode())
    assert [(p.step, p.source, p.reference) for p in decoded.provenance] == [
        ("hypothesis", "lfm3", "step:1"),
        ("verification", "verifier", "step:4"),
    ]
    assert [link.relation for link in decoded.step_links] == [
        "refines",
        "supports",
    ]


def test_token_estimate_is_measured_not_claimed():
    context = _context()
    comparison = compare_token_usage(context)
    assert comparison["json_tokens"] > 0
    assert comparison["plain_tokens"] > 0
    assert comparison["json_to_plain_ratio"] is not None
    assert comparison["json_to_plain_ratio"] > 0
    assert "not a model tokenizer" in comparison["method"]
    assert estimate_tokens("a + b") == 3


def test_plain_text_contains_every_statement():
    text = _context().to_plain_text()
    assert "the hypothesis is not restricted to x > 0" in text
    assert "x**8 + 8*x**7" in text
    assert "exp_1" in text


def test_invalid_context_payloads_are_rejected():
    with pytest.raises(ContextError):
        ResearchContext.decode("not json")
    with pytest.raises(ContextError):
        ResearchContext.decode(json.dumps({"version": 99}))
    with pytest.raises(ContextError):
        ResearchContext.decode(
            json.dumps(
                {
                    "version": 1,
                    "assumptions": [{"statement": "s", "kind": "bogus"}],
                }
            )
        )
    with pytest.raises(ContextError):
        ResearchContext.decode(json.dumps({"version": 1, "concepts": "no"}))
