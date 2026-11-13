"""Frozen Round 3 task set for the confirmatory LFM3 evaluation.

The mathematical questions are fixed before any model call.  Condition A uses
the original Round 1 output protocol; Condition B uses the derivation-first
protocol.  Prompts, expected results and verification methods are stored outside
the prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass

from block15.tasks import (
    ANSWER_SCHEMA,
    OUTPUT_INSTRUCTION,
    SYSTEM_PROMPT,
    TOOL_DECISION_SCHEMA,
)

EXPERIMENTAL_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["derivation", "final_answer", "uncertainty", "confidence"],
    "properties": {
        "derivation": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1, "maxLength": 500},
        },
        "final_answer": {"type": "string", "minLength": 1, "maxLength": 1400},
        "uncertainty": {"type": "string", "maxLength": 700},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

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

EXPERIMENTAL_INSTRUCTION = (
    "\n\nReturn a JSON object with exactly these fields, in this order: "
    "derivation (array of short, independently checkable steps), final_answer "
    "(definitive answer), uncertainty (string), confidence (number from 0 to "
    "1). Work through the derivation first and only then state the final "
    "answer. Put every string on one line; do not include literal newline "
    "characters inside string values. Do not use markdown or code fences."
)

VOLUNTARY_DECISION_INSTRUCTION = (
    "\n\nFirst decide whether to use the available symbolic_expand tool. "
    "Return a JSON object with exactly these fields: use_tool (boolean), "
    "expression (string; empty if no tool is used), reason (string explaining "
    "the decision). The expression must use only integers, variable names, "
    "parentheses and + - * **. Do not give the final answer in this step."
)

DIRECT_TOOL_INSTRUCTION = (
    "\n\nExplicitly request expansion of (2*x + 3)**7 through the existing "
    "symbolic_expand tool before giving a final answer. Return a JSON object "
    "with exactly these fields: tool (string, must be 'symbolic_expand') and "
    "arguments (object with expression string). Use only integers, variable "
    "names, parentheses and + - * **. Do not give the final answer in this "
    "step."
)


@dataclass(frozen=True)
class Round3Task:
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
    provenance: str = (
        "Designed for Block 1.5 Round 3; not copied from an earlier evaluation."
    )
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
) -> tuple[Round3Task, Round3Task]:
    condition_a = Round3Task(
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
    condition_b = Round3Task(
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
    id_base="R3A1_coefficient",
    group="A_output_contract",
    category="A_mathematical_reasoning",
    difficulty="medium",
    question=(
        "Find the coefficient of x^4 in (3x - 2)^6. Give the value and a "
        "short derivation."
    ),
    expected="4860",
    verification="SymPy coefficient extraction from (3*x - 2)**6.",
)

A2_A, A2_B = _condition_pair(
    id_base="R3A2_divisibility",
    group="A_output_contract",
    category="A_mathematical_reasoning",
    difficulty="medium",
    question=(
        "Prove that n^3 - n is divisible by 6 for every integer n. Give a "
        "complete proof."
    ),
    expected=(
        "True; n^3 - n = n(n-1)(n+1) is a product of three consecutive "
        "integers, hence divisible by 2 and by 3."
    ),
    verification=(
        "Independent exhaustive divisibility check over integer n plus "
        "rubric review of the proof."
    ),
)

B = Round3Task(
    id="R3B_counterexample_minimality",
    group="B_counterexample_search",
    category="B_pattern_recognition",
    difficulty="hard",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Find the smallest non-negative integer n for which "
        "f(n) = n^2 + n + 101 is composite. Report the proposed smallest "
        "value, its factorization, verify that every preceding non-negative "
        "integer value is prime, and explain how minimality was established. "
        "Distinguish checking a few examples from establishing minimality."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "Find the smallest non-negative integer n for which "
        "f(n) = n^2 + n + 101 is composite. Report the proposed smallest "
        "value, its factorization, verify that every preceding non-negative "
        "integer value is prime, and explain how minimality was established. "
        "Distinguish checking a few examples from establishing minimality."
    ),
    expected=(
        "n = 4; f(4) = 121 = 11^2. The preceding values are f(0)=101, "
        "f(1)=103, f(2)=107 and f(3)=113, all prime."
    ),
    verification=(
        "Independent SymPy primality search and factorization for n=0..100."
    ),
)

C = Round3Task(
    id="R3C_hypothesis_falsification",
    group="C_hypothesis_falsification",
    category="C_hypothesis_formation",
    difficulty="hard",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "For f(n) = n^2 + n + 1277, the observed values for n = 0, 1, 2, 3, "
        "4, 5 are 1277, 1279, 1283, 1289, 1297, 1307. Answer all of the "
        "following: (1) State a plausible pattern or hypothesis. (2) State "
        "precisely what the observed data establish. (3) State whether it is "
        "justified to conclude that f(n) is prime for every non-negative "
        "integer n. (4) Design a concrete falsification procedure. (5) Search "
        "for a counterexample. (6) If a counterexample is found, establish "
        "whether it is the smallest one."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "For f(n) = n^2 + n + 1277, the observed values for n = 0, 1, 2, 3, "
        "4, 5 are 1277, 1279, 1283, 1289, 1297, 1307. Answer all of the "
        "following: (1) State a plausible pattern or hypothesis. (2) State "
        "precisely what the observed data establish. (3) State whether it is "
        "justified to conclude that f(n) is prime for every non-negative "
        "integer n. (4) Design a concrete falsification procedure. (5) Search "
        "for a counterexample. (6) If a counterexample is found, establish "
        "whether it is the smallest one."
    ),
    expected=(
        "The observations suggest a prime-producing quadratic but do not "
        "prove it. The first counterexample is n=7: f(7)=1333=31*43; "
        "n=0..6 are prime, so n=7 is the smallest."
    ),
    verification=(
        "Independent SymPy primality search and factorization for n=0..100."
    ),
)

D1 = Round3Task(
    id="R3D1_tool_voluntary",
    group="D_tool_use",
    category="E_tool_use",
    difficulty="hard",
    protocol="voluntary_tool_decision",
    mode="tool_voluntary",
    prompt=(
        "Determine the coefficient of x^7 in (3x - 2)^12. You may use the "
        "available symbolic_expand tool if you judge it useful."
        + VOLUNTARY_DECISION_INSTRUCTION
    ),
    math_question="Determine the coefficient of x^7 in (3x - 2)^12.",
    expected="-55427328",
    verification=(
        "SymPy coefficient extraction from (3*x - 2)**12; tool request, if "
        "any, is validated by the existing orchestrator and verifier."
    ),
)

D2 = Round3Task(
    id="R3D2_tool_required",
    group="D_tool_use",
    category="E_tool_use",
    difficulty="medium",
    protocol="required_tool_request",
    mode="tool_required",
    prompt=(
        "Determine the coefficient of x^5 in (2x + 3)^7."
        + DIRECT_TOOL_INSTRUCTION
    ),
    math_question="Determine the coefficient of x^5 in (2x + 3)^7.",
    expected="6048",
    verification=(
        "SymPy coefficient extraction from (2*x + 3)**7; existing "
        "verify_symbolic_expand for the tool result."
    ),
)

E1 = Round3Task(
    id="R3E1_uncertainty_determinate",
    group="E_uncertainty_calibration",
    category="F_uncertainty_calibration",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Determine whether n(n+1)(n+2) is divisible by 6 for every integer n. "
        "Give a proof or a counterexample."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "Determine whether n(n+1)(n+2) is divisible by 6 for every integer n."
    ),
    expected=(
        "True; one of the three consecutive factors is divisible by 3 and at "
        "least one is even."
    ),
    verification=(
        "Independent exhaustive divisibility check over integer n plus "
        "rubric review of the proof."
    ),
)

E2 = Round3Task(
    id="R3E2_uncertainty_underdetermined",
    group="E_uncertainty_calibration",
    category="F_uncertainty_calibration",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Consider the sequence 3, 7, 13, 21, 31. Determine the next term and "
        "state whether it is uniquely determined by the given observations. "
        "Explain your reasoning and what additional information would be "
        "needed for a unique conclusion."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "Consider the sequence 3, 7, 13, 21, 31. Determine the next term and "
        "state whether it is uniquely determined by the given observations."
    ),
    expected=(
        "A simple pattern has first differences 4, 6, 8, 10 and next "
        "difference 12, giving 43. The continuation is plausible, not "
        "mathematically unique without an additional rule."
    ),
    verification=(
        "Finite differences and SymPy interpolation; uniqueness is a logical "
        "rubric question."
    ),
)

F = Round3Task(
    id="R3F_numerical_trend_noise",
    group="F_numerical_trend_noise",
    category="G_noise_awareness",
    difficulty="medium",
    protocol="B_derivation_first",
    mode="answer",
    prompt=(
        "Consider the observations 100, 102, 101, 103, 102, 104, 103, 105. "
        "Answer all of the following: (1) Describe the general numerical "
        "trend. (2) Identify the fluctuations. (3) Distinguish a plausible "
        "underlying trend from an exact deterministic rule. (4) Propose a "
        "cautious next-value estimate or range. (5) Explain why the "
        "observations do not establish that the trend will continue. "
        "(6) Identify what additional observations or tests would help "
        "distinguish signal from noise."
        + EXPERIMENTAL_INSTRUCTION
    ),
    math_question=(
        "Consider the observations 100, 102, 101, 103, 102, 104, 103, 105. "
        "Describe the trend, fluctuations, uncertainty and what additional "
        "observations would help."
    ),
    expected=(
        "An upward trend of about one unit per two observations with "
        "alternating +2/-1 fluctuations. The next value is not uniquely "
        "determined; 104 is a plausible estimate, and more observations or "
        "repeated trials are needed."
    ),
    verification=(
        "Descriptive numerical analysis plus rubric review; no unique next "
        "value is treated as ground truth."
    ),
)

G = Round3Task(
    id="R3A1_coefficient_protocol_B_repeat",
    group="G_repeatability",
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


RUN_ORDER: tuple[Round3Task, ...] = (
    A1_A,
    A1_B,
    A2_A,
    A2_B,
    B,
    C,
    D1,
    D2,
    E1,
    E2,
    F,
    G,
)

# D1 and D2 each require a decision/request call plus a final-answer call.
PLANNED_CALLS = sum(2 if task.mode in {"tool_voluntary", "tool_required"} else 1 for task in RUN_ORDER)

__all__ = [
    "ANSWER_SCHEMA",
    "DIRECT_TOOL_INSTRUCTION",
    "DIRECT_TOOL_SCHEMA",
    "EXPERIMENTAL_INSTRUCTION",
    "EXPERIMENTAL_SCHEMA",
    "PLANNED_CALLS",
    "RUN_ORDER",
    "Round3Task",
    "SYSTEM_PROMPT",
    "TOOL_DECISION_SCHEMA",
    "VOLUNTARY_DECISION_INSTRUCTION",
]
