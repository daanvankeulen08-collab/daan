"""Fixed Block 1.5 task set.

Design constraints:
* 12 primary tasks across categories A-F.
* Baseline and tool-assisted variants are explicit.
* Prompts contain only the information needed to solve the task.
* Expected answers are stored outside the prompt for independent checking.
* Two representative tasks are repeated with exactly the same prompt/settings.
"""

from __future__ import annotations

from dataclasses import dataclass

SYSTEM_PROMPT = (
    "You are LFM3, a local mathematical reasoning model. Solve the task "
    "independently from the information given. Do not claim to have used a "
    "tool unless its result is provided to you. Return exactly one JSON object "
    "matching the required schema. Use concise reasoning (at most 120 words). "
    "Every string value must be on one line: do not put literal newline "
    "characters inside a string. Do not use markdown or code fences."
)

ANSWER_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "reasoning", "confidence", "uncertainty"],
    "properties": {
        "answer": {"type": "string", "minLength": 1, "maxLength": 1200},
        "reasoning": {"type": "string", "minLength": 1, "maxLength": 3000},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "string", "maxLength": 1000},
    },
}

TOOL_DECISION_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["use_tool", "expression", "reason"],
    "properties": {
        "use_tool": {"type": "boolean"},
        "expression": {"type": "string", "maxLength": 200},
        "reason": {"type": "string", "maxLength": 1000},
    },
}

TOOL_CLAUSE = (
    " You may use the available symbolic_expand tool if you judge it useful. "
    "If you use it, request exactly one polynomial expression to expand; "
    "otherwise answer directly."
)

OUTPUT_INSTRUCTION = (
    "\n\nReturn a JSON object with exactly these fields: answer (string), "
    "reasoning (string), confidence (number from 0 to 1), and uncertainty "
    "(string). Keep the whole response concise. Put every string on one line; "
    "do not include literal newline characters inside string values. Do not "
    "use markdown or code fences."
)

TOOL_DECISION_INSTRUCTION = (
    "\n\nFirst decide whether to use symbolic_expand. Return a JSON object with "
    "exactly these fields: use_tool (boolean), expression (string; empty if no "
    "tool is used), and reason (string). The expression must use only integers, "
    "variable names, parentheses and + - * **."
)


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    difficulty: str
    mode: str  # "baseline" or "tool"
    prompt: str
    expected: str
    verification: str
    provenance: str
    repeat_of: str | None = None
    variant_of: str | None = None

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "difficulty": self.difficulty,
            "mode": self.mode,
            "prompt": self.prompt,
            "expected": self.expected,
            "verification": self.verification,
            "provenance": self.provenance,
            "repeat_of": self.repeat_of,
            "variant_of": self.variant_of,
        }


TASKS: tuple[Task, ...] = (
    Task(
        id="A1_coefficient_baseline",
        category="A_mathematical_reasoning",
        difficulty="medium",
        mode="baseline",
        prompt=(
            "Find the coefficient of x^5 in the polynomial "
            "(x^2 + 3x + 2)(x + 1)^6. Give the coefficient and a short "
            "derivation."
        ),
        expected="77",
        verification=(
            "SymPy coefficient extraction from the exact polynomial "
            "(x**2 + 3*x + 2)*(x + 1)**6."
        ),
        provenance="Designed for Block 1.5; standard polynomial exercise.",
    ),
    Task(
        id="A1_coefficient_tool",
        category="A_mathematical_reasoning",
        difficulty="medium",
        mode="tool",
        prompt=(
            "Find the coefficient of x^5 in the polynomial "
            "(x^2 + 3x + 2)(x + 1)^6. Give the coefficient and a short "
            "derivation." + TOOL_CLAUSE
        ),
        expected="77",
        verification=(
            "Same independent SymPy coefficient check; additionally inspect "
            "whether the requested tool expression is valid and appropriate."
        ),
        provenance="Tool-assisted pair for A1; only tool availability changes.",
        variant_of="A1_coefficient_baseline",
    ),
    Task(
        id="A2_difference_terms",
        category="A_mathematical_reasoning",
        difficulty="hard",
        mode="baseline",
        prompt=(
            "Let f(x) = (x + 1)^6 - (x - 1)^6. Determine the number of nonzero "
            "terms in the expanded form of f(x), and compute the sum of all "
            "coefficients of f(x). Explain briefly."
        ),
        expected="3 nonzero terms; coefficient sum 64",
        verification=(
            "SymPy exact expansion; count nonzero terms and evaluate f(1)."
        ),
        provenance="Designed for Block 1.5; multi-step algebraic reasoning.",
    ),
    Task(
        id="B1_counterexample",
        category="B_pattern_recognition",
        difficulty="medium",
        mode="baseline",
        prompt=(
            "Consider the sequence a_n = n^2 + n + 17 for n = 0, 1, 2, ... . "
            "A student claims every term is prime. Find the smallest n for "
            "which this claim fails, or state that no such n exists. Show "
            "enough work to support your answer."
        ),
        expected="n = 16, where a_16 = 289 = 17^2",
        verification=(
            "Independent primality search over n = 0..1000 with SymPy."
        ),
        provenance=(
            "Novel variant of the Euler polynomial idea; does not rely on "
            "recalling the standard n^2+n+41 example."
        ),
    ),
    Task(
        id="B2_sequence_rule",
        category="B_pattern_recognition",
        difficulty="hard",
        mode="baseline",
        prompt=(
            "The first five terms of a sequence are 1, 5, 13, 25, 41. "
            "Assuming the simplest polynomial pattern, give the next two terms "
            "and a formula for the n-th term (take the first term as n = 1). "
            "Explain how you obtained the formula."
        ),
        expected="next terms 61 and 85; formula 2n^2 - 2n + 1",
        verification=(
            "Finite differences and SymPy polynomial interpolation; check that "
            "the stated formula matches all five terms and the next two."
        ),
        provenance="Designed for Block 1.5; quadratic rather than linear pattern.",
    ),
    Task(
        id="C1_hypothesis_primality",
        category="C_hypothesis_formation",
        difficulty="medium",
        mode="baseline",
        prompt=(
            "The first five values of P(n) = n^2 - n + 41 for n = 1,2,3,4,5 "
            "are prime. Formulate one precise, testable hypothesis that "
            "explains these observations, and propose a concrete independent "
            "test that could falsify it. Do not assume the hypothesis is true."
        ),
        expected=(
            "A falsifiable hypothesis (e.g. P(n) is prime for every positive "
            "integer n) plus a concrete search for a composite value; the "
            "known failure is P(41) = 41^2 = 1681."
        ),
        verification=(
            "Rubric review for precision and falsifiability, plus independent "
            "computation of P(n) over a range that includes n = 41."
        ),
        provenance=(
            "Designed for Block 1.5; tests whether finite evidence is treated "
            "as a hypothesis rather than a proof."
        ),
    ),
    Task(
        id="C2_hypothesis_last_digit",
        category="C_hypothesis_formation",
        difficulty="hard",
        mode="baseline",
        prompt=(
            "For n = 0,1,2,3,4,5, the last decimal digit of n^5 - n is always "
            "0. Formulate a precise hypothesis about the last digit of n^5 - n "
            "for every integer n, and describe an independent test. Do not "
            "assume the hypothesis is true."
        ),
        expected=(
            "Hypothesis: the last digit is always 0 (equivalently 10 divides "
            "n^5 - n). Independent test: check all residues modulo 10 or factor "
            "n^5 - n."
        ),
        verification=(
            "Exhaustive residue check modulo 10 with SymPy/Python; the "
            "hypothesis is true because 30 divides n^5 - n."
        ),
        provenance=(
            "Designed for Block 1.5; a pattern that is true but should still be "
            "stated as a testable claim."
        ),
    ),
    Task(
        id="D1_even_proof",
        category="D_proof",
        difficulty="medium",
        mode="baseline",
        prompt=(
            "Prove or disprove: for every integer n, n^2 + n is even. Give a "
            "complete proof or a counterexample."
        ),
        expected=(
            "True. n^2 + n = n(n+1), the product of two consecutive integers, "
            "so one factor is even; alternatively split into n even and n odd."
        ),
        verification=(
            "Logical rubric review; independent exhaustive parity check for a "
            "range of integers."
        ),
        provenance="Standard theorem, rewritten as a proof task.",
    ),
    Task(
        id="D2_false_primality_proof",
        category="D_proof",
        difficulty="hard",
        mode="baseline",
        prompt=(
            "Prove or disprove: for every positive integer n, n^2 + n + 41 is "
            "prime. Give a complete proof or a counterexample."
        ),
        expected=(
            "False. n = 40 gives 1681 = 41^2; n = 41 gives 1763 = 41*43. A "
            "single valid counterexample disproves the universal claim."
        ),
        verification=(
            "SymPy primality search for a counterexample over n = 1..100."
        ),
        provenance=(
            "Standard false claim, used to test whether the model challenges a "
            "plausible-looking universal statement."
        ),
    ),
    Task(
        id="E1_tool_coefficient",
        category="E_tool_use",
        difficulty="medium",
        mode="tool",
        prompt=(
            "Compute the coefficient of x^7 in (2x - 3)^9. You may use the "
            "available symbolic_expand tool if you judge it useful. If you use "
            "it, request exactly one polynomial expression to expand; otherwise "
            "answer directly."
        ),
        expected="41472",
        verification=(
            "SymPy coefficient extraction: binomial(9,7) * 2^7 * (-3)^2."
        ),
        provenance=(
            "Designed for Block 1.5; tests tool decision, request formulation "
            "and interpretation."
        ),
    ),
    Task(
        id="E2_tool_divisibility",
        category="E_tool_use",
        difficulty="hard",
        mode="tool",
        prompt=(
            "Determine whether the polynomial (x + y)^5 - (x^5 + y^5) is "
            "divisible by 5xy(x + y). You may use the available "
            "symbolic_expand tool if you judge it useful. If you use it, "
            "request exactly one polynomial expression to expand; otherwise "
            "answer directly."
        ),
        expected=(
            "Yes. The difference equals 5xy(x + y)(x^2 + xy + y^2), so the "
            "quotient is x^2 + xy + y^2."
        ),
        verification=(
            "SymPy expansion and exact polynomial division; check a zero "
            "remainder."
        ),
        provenance=(
            "Designed for Block 1.5; requires interpreting an expansion rather "
            "than only copying it."
        ),
    ),
    Task(
        id="F1_error_correction",
        category="F_self_correction",
        difficulty="medium",
        mode="baseline",
        prompt=(
            "A student writes: '(x + 1)^2 = x^2 + 1, because squaring applies "
            "to each term.' Is the statement correct? If not, identify the "
            "error and give the correct expansion."
        ),
        expected=(
            "Incorrect. Squaring is not distributive over addition: "
            "(x + 1)^2 = x^2 + 2x + 1."
        ),
        verification="SymPy expansion of (x + 1)^2.",
        provenance="Designed for Block 1.5; explicit misconception correction.",
    ),
    Task(
        id="F2_revise_conclusion",
        category="F_self_correction",
        difficulty="hard",
        mode="baseline",
        prompt=(
            "After checking n = 0,1,2,3,4,5, a student concluded: 'n^2 + n + "
            "41 is prime for every non-negative integer n.' A counterexample is "
            "n = 40, where the value is 1681 = 41^2. Revise the conclusion. "
            "State precisely what the counterexample proves and what it does "
            "not prove."
        ),
        expected=(
            "The universal claim is false. The counterexample disproves 'for "
            "every n'; it does not prove that all other values are composite, "
            "nor does it establish the exact set of prime-producing n."
        ),
        verification=(
            "Logical rubric review; independent verification that 1681 = 41^2 "
            "and that n = 40 is a valid counterexample."
        ),
        provenance=(
            "Designed for Block 1.5; tests revision of a conclusion and the "
            "scope of a counterexample."
        ),
    ),
)

REPEATS: tuple[Task, ...] = (
    Task(
        id="A1_coefficient_repeat",
        category="A_mathematical_reasoning",
        difficulty="medium",
        mode="baseline",
        prompt=TASKS[0].prompt,
        expected=TASKS[0].expected,
        verification=TASKS[0].verification,
        provenance="Exact repeat of A1 with identical prompt and settings.",
        repeat_of="A1_coefficient_baseline",
    ),
    Task(
        id="D1_even_proof_repeat",
        category="D_proof",
        difficulty="medium",
        mode="baseline",
        prompt=TASKS[7].prompt,
        expected=TASKS[7].expected,
        verification=TASKS[7].verification,
        provenance="Exact repeat of D1 with identical prompt and settings.",
        repeat_of="D1_even_proof",
    ),
)

RUN_ORDER: tuple[Task, ...] = TASKS + REPEATS
