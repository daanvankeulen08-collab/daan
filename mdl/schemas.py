"""Pydantic models and the JSON schemas used for constrained model output.

The JSON schemas are written out explicitly (no ``$ref``/``$defs``) because
Ollama/llama.cpp constrained decoding handles inline schemas most reliably.
Pydantic remains the authority: every model response is re-validated.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Model output models
# ---------------------------------------------------------------------------


class Hypothesis(BaseModel):
    statement: str = Field(min_length=5, max_length=1200)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    variables: list[str] = Field(default_factory=list, max_length=12)


class ResearchPlan(BaseModel):
    objective: str = Field(min_length=3, max_length=600)
    steps: list[str] = Field(min_length=1, max_length=8)
    tool: Literal["symbolic_expand"]
    expected_outcome: str = Field(min_length=3, max_length=600)


class SymbolicExpandArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=200)


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["symbolic_expand"]
    arguments: SymbolicExpandArguments


class Interpretation(BaseModel):
    conclusion: str = Field(min_length=5, max_length=900)
    supports_hypothesis: bool
    observed_outcome: str = Field(min_length=3, max_length=700)
    uncertainties: list[str] = Field(default_factory=list, max_length=5)
    follow_up: list[str] = Field(default_factory=list, max_length=5)


# ---------------------------------------------------------------------------
# Tool result models (produced by our own code, still validated)
# ---------------------------------------------------------------------------


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coefficient: str
    monomial: dict[str, int]


class SymbolicExpandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str
    expanded: str
    variables: list[str]
    term_count: int = Field(ge=0)
    total_degree: int = Field(ge=0)
    terms: list[Term]


# ---------------------------------------------------------------------------
# JSON schemas for Ollama constrained output
# ---------------------------------------------------------------------------

HYPOTHESIS_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["statement", "assumptions", "variables"],
    "properties": {
        "statement": {"type": "string", "minLength": 5, "maxLength": 1200},
        "assumptions": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "maxLength": 300},
        },
        "variables": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "maxLength": 16},
        },
    },
}

PLAN_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["objective", "steps", "tool", "expected_outcome"],
    "properties": {
        "objective": {"type": "string", "minLength": 3, "maxLength": 600},
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {"type": "string", "maxLength": 300},
        },
        "tool": {"type": "string", "enum": ["symbolic_expand"]},
        "expected_outcome": {"type": "string", "minLength": 3, "maxLength": 600},
    },
}

TOOL_REQUEST_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "arguments"],
    "properties": {
        "tool": {"type": "string", "enum": ["symbolic_expand"]},
        "arguments": {
            "type": "object",
            "additionalProperties": False,
            "required": ["expression"],
            "properties": {
                "expression": {"type": "string", "minLength": 1, "maxLength": 200}
            },
        },
    },
}

INTERPRETATION_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "conclusion",
        "supports_hypothesis",
        "observed_outcome",
        "uncertainties",
        "follow_up",
    ],
    "properties": {
        "conclusion": {"type": "string", "minLength": 5, "maxLength": 900},
        "supports_hypothesis": {"type": "boolean"},
        "observed_outcome": {"type": "string", "minLength": 3, "maxLength": 700},
        "uncertainties": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string", "maxLength": 240},
        },
        "follow_up": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string", "maxLength": 240},
        },
    },
}
