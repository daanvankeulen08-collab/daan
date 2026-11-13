"""Round 2 task set.

Condition A reuses the exact Round 1 output protocol.  Condition B uses a
separate experimental output contract: concise derivation steps first, the
definitive answer last.  Mathematical prompts are identical inside each pair.
"""

from __future__ import annotations

from dataclasses import dataclass

from block15.tasks import (
    ANSWER_SCHEMA,
    OUTPUT_INSTRUCTION,
    SYSTEM_PROMPT,
)

EXPERIMENTAL_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["derivation", "final_answer", "uncertainty", "confidence"],
    "properties": {
        "derivation": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {"type": "string", "minLength": 1, "maxLength": 500},
        },
        "final_answer": {"type": "string", "minLength": 1, "maxLength": 1000},
        "uncertainty": {"type": "string", "maxLength": 500},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

VOLUNTARY_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "use_tool",
        "expression",
        "derivation",
        "final_answer",
        "uncertainty",
        "confidence",
    ],
    "properties": {
        "use_tool": {"type": "boolean"},
        "expression": {"type": "string", "maxLength": 200},
        "derivation": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {"type": "string", "minLength": 1, "maxLength": 500},
        },
        "final_answer": {"type": "string", "minLength": 1, "maxLength": 1000},
        "uncertainty": {"type": "string", "maxLength": 500},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

EXPERIMENTAL_INSTRUCTION = (
    "\n\nReturn a JSON object with exactly these fields, in this order: "
    "derivation (array of short verifiable steps), final_answer (definitive "
    "answer), uncertainty (string), confidence (number from 0 to 1). Work "
    "through the derivation first and only then state the final answer. Put "
    "every string on one line; do not include literal newline characters "
    "inside string values. Do not use markdown."
)

VOLUNTARY_INSTRUCTION = (
    "\n\nFirst decide whether to use the available symbolic_expand tool. Return "
    "a JSON object with exactly these fields: use_tool (boolean), expression "
    "(string; empty if no tool is used), derivation (array of short steps), "
    "final_answer (provisional if the tool is still pending), uncertainty "
    "(string), confidence (number from 0 to 1). The expression must use only "
    "integers, variable names, parentheses and + - * **."
)

DIRECT_TOOL_SCHEMA: dict = {
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

DIRECT_TOOL_INSTRUCTION = (
    "\n\nExplicitly request expansion of (2*x - 1)**5 through the existing "
    "symbolic_expand tool before giving a final answer. Return a JSON object "
    "with exactly these fields: tool (string, must be 'symbolic_expand') and "
    "arguments (object with expression string). Use only integers, variable "
    "names, parentheses and + - * **."
)


@dataclass(frozen=True)
class Round2Task:
    id: str
    group: str
    category: str
    difficulty: str
    protocol: str
    mode: str
    prompt: str
    math_question: str
    expected: str
    verification: str
    provenance: str = "Designed for Block 1.5 Round 2; not reused from Round 1."
    repeat_of: str | None = None

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "group": self.group,
            "category": self.category,
            "difficulty": self.difficulty,
            "protocol": self.protocol,
            "mode": self.mode,
            "prompt": self.prompt,
            "math_question": self.math_question,
            "expected": self.expected,
            "verification": self.verification,
            "provenance": self.provenance,
            "repeat_of": self.repeat_of,
        }


def _condition_pair(
    *,
    id_base: str,
    group: str,
    category: str,
    difficulty: str,
    question: str,
    expected: str,
    verification: str,
) -> tuple[Round2Task, Round2Task]:
    condition_a = Round2Task(
        id=f"{id_base}_protocol_A",
        group=group,
        category=category,
        difficulty=difficulty,
        protocol="A_round1_answer_reasoning",
        mode="answer",
        prompt=question + OUTPUT_INSTRUCTION,
        math_question=question,
        expected=expected,
        verification=verification,
    )
    condition_b = Round2Task(
        id=f"{id_base}_protocol_B",
        group=group,
        category=category,
        difficulty=difficulty,
        protocol="B_derivation_first",
        mode="answer",
        prompt=question + EXPERIMENTAL_INSTRUCTION,
        math_question=question,
        expected=expected,
        verification=verification,
    )
    return condition_a, condition_b


A1_A, A1_B = _condition_pair(
    id_base="R2A1_coefficient",
    group="A_output_contract",
    category="A_mathematical_reasoning",
    difficulty="medium",
    question="Calculate the coefficient of x^3 in (2x - 1)^5. Give the value and a short derivation.",
    expected="80",
    verification="SymPy coefficient extraction from (2*x - 1)**5.",
)

A2_A, A2_B = _condition_pair(
    id_base="R2A2_divisibility",
    group="A_output_contract",
    category="A_mathematical_reasoning",
    difficulty="medium",
    question="Prove that the product of three consecutive integers is divisible by 6. Give a complete proof.",
    expected="True; one of three consecutive integers is divisible by 3 and at least one is even.",
    verification="Independent exhaustive divisibility check over a range plus rubric review of the proof.",
)

A3_A, A3_B = _condition_pair(
    id_base="R2A3_sequence",
    group="A_output_contract",
    category="B_pattern_recognition",
    difficulty="medium",
    question=(
        "Analyse the sequence 2, 6, 12, 20, 30, 42. Give the simplest plausible "
        "rule, the next term and explain whether the rule is uniquely determined."
    ),
    expected=(
        "Simplest polynomial rule is n(n+1) with the first term at n=1; next "
        "term 56. The rule is not uniquely determined by finite observations "
        "without a simplicity assumption."
    ),
    verification="Finite differences and SymPy interpolation for the simplest polynomial; uniqueness is a logical/rubric question.",
)

A4_A, A4_B = _condition_pair(
    id_base="R2A4_composite",
    group="A_output_contract",
    category="B_pattern_recognition",
    difficulty="hard",
    question=(
        "Find the smallest non-negative integer n for which n^2 + n + 11 is "
        "composite. Demonstrate minimality."
    ),
    expected="n = 10, where n^2 + n + 11 = 121 = 11^2.",
    verification="Independent primality search over n = 0..100 with SymPy.",
)


B1 = Round2Task(
    id="R2B1_tool_voluntary",
    group="B_tool_use",
    category="E_tool_use",
    difficulty="medium",
    protocol="voluntary_tool_decision",
    mode="tool_voluntary",
    prompt=(
        "Determine the coefficient of x^2 in (x + 3)^4. You may use the "
        "available symbolic_expand tool if you judge it useful."
        + VOLUNTARY_INSTRUCTION
    ),
    math_question="Determine the coefficient of x^2 in (x + 3)^4.",
    expected="54",
    verification=(
        "SymPy coefficient extraction from (x + 3)**4; tool request separately "
        "validated by the existing orchestrator."
    ),
)

B2 = Round2Task(
    id="R2B2_tool_required",
    group="B_tool_use",
    category="E_tool_use",
    difficulty="medium",
    protocol="required_tool_request",
    mode="tool_required",
    prompt=(
        "Determine the coefficient of x^3 in (2x - 1)^5."
        + DIRECT_TOOL_INSTRUCTION
    ),
    math_question="Determine the coefficient of x^3 in (2x - 1)^5.",
    expected="80",
    verification=(
        "SymPy coefficient extraction from (2*x - 1)**5; existing "
        "verify_symbolic_expand for the tool result."
    ),
)


C1 = Round2Task(
    id="R2C1_uncertainty_determinate",
    group="C_uncertainty_calibration",
    category="F_self_correction",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Assess whether n^2 + n is even for every integer n. State your "
        "conclusion and the evidence supporting it."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question="Assess whether n^2 + n is even for every integer n.",
    expected="True; n(n+1) is the product of two consecutive integers, so one factor is even.",
    verification="Independent exhaustive parity check over a range plus rubric review.",
)

C2 = Round2Task(
    id="R2C2_uncertainty_underdetermined",
    group="C_uncertainty_calibration",
    category="F_self_correction",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Consider the sequence 1, 2, 4, 8. Can the next term be uniquely "
        "determined from these observations? Answer yes or no and explain what "
        "additional information would be needed."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question="Consider the sequence 1, 2, 4, 8. Can the next term be uniquely determined from these observations?",
    expected=(
        "No; 16 is plausible under a doubling rule, but finite observations do "
        "not uniquely determine a continuation."
    ),
    verification="Logical/rubric review; multiple valid continuations exist.",
)

D = Round2Task(
    id="R2D_hypothesis_generalization",
    group="D_hypothesis_formation",
    category="C_hypothesis_formation",
    difficulty="hard",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "The values of n^2 + n + 17 for n = 0, 1, 2, 3, 4, 5 are all prime. "
        "Formulate a plausible hypothesis, state the limits of the available "
        "evidence, propose a concrete falsification test, and search for the "
        "smallest non-negative counterexample if one exists."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "The values of n^2 + n + 17 for n = 0 through 5 are all prime. "
        "Formulate a plausible hypothesis, state the limits of the available "
        "evidence, propose a concrete falsification test, and search for the "
        "smallest non-negative counterexample if one exists."
    ),
    expected=(
        "Prime-producing for the observed small range; finite evidence does "
        "not justify a universal claim. Smallest counterexample is n = 16, "
        "where n^2 + n + 17 = 289 = 17^2."
    ),
    verification="Independent primality search over n = 0..100 with SymPy.",
)

E = Round2Task(
    id="R2E_self_correction",
    group="E_self_correction",
    category="F_self_correction",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "A student claims (x + 2)^2 = x^2 + 4. Evaluate the claim, identify "
        "the error, correct the expression and verify the correction."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question="A student claims (x + 2)^2 = x^2 + 4. Evaluate the claim, identify the error, correct the expression and verify the correction.",
    expected="Incorrect; (x + 2)^2 = x^2 + 4x + 4. The missing term is 4x.",
    verification="SymPy expansion of (x + 2)^2.",
)

A1_B_REPEAT = Round2Task(
    id="R2A1_coefficient_protocol_B_repeat",
    group="F_repeatability",
    category="A_mathematical_reasoning",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="repeat",
    prompt=A1_B.prompt,
    math_question=A1_B.math_question,
    expected=A1_B.expected,
    verification=A1_B.verification,
    repeat_of=A1_B.id,
)

A2_B_REPEAT = Round2Task(
    id="R2A2_divisibility_protocol_B_repeat",
    group="F_repeatability",
    category="A_mathematical_reasoning",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="repeat",
    prompt=A2_B.prompt,
    math_question=A2_B.math_question,
    expected=A2_B.expected,
    verification=A2_B.verification,
    repeat_of=A2_B.id,
)


RUN_ORDER: tuple[Round2Task, ...] = (
    A1_A,
    A1_B,
    A2_A,
    A2_B,
    A3_A,
    A3_B,
    A4_A,
    A4_B,
    B1,
    B2,
    C1,
    C2,
    D,
    E,
    A1_B_REPEAT,
    A2_B_REPEAT,
)

__all__ = [
    "ANSWER_SCHEMA",
    "DIRECT_TOOL_INSTRUCTION",
    "DIRECT_TOOL_SCHEMA",
    "EXPERIMENTAL_INSTRUCTION",
    "EXPERIMENTAL_SCHEMA",
    "RUN_ORDER",
    "Round2Task",
    "SYSTEM_PROMPT",
    "VOLUNTARY_INSTRUCTION",
    "VOLUNTARY_SCHEMA",
]
