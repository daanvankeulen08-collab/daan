"""Ceiling study: schema field order replication plus a sequential budget test.

This module is a new, additive harness.  It does not modify the Round 3/4,
QAD, memory or ``block15/heldout_research.py`` logic.  It writes only new
``block15_ceiling_*`` stores and ``block15_ceiling_results_*`` result files.

Design:

* 20 fresh bounded-math tasks (12 coefficient, 8 bounded-minimality), all
  independent of the Round 3 prompts and of H1-H5 from the prior held-out
  study.  Ground truth is computed by SymPy at run time and checked against
  frozen values.
* Experiment 1: answer-first versus derivation-first JSON Schema order, one
  call per task per condition, ``num_predict=1200``.
* Experiment 2: derivation-first at ``num_predict=1200`` (the Experiment 1
  intervention, reused, not rerun) versus derivation-first at
  ``num_predict=2400``, one call per task.
* A strict answer-field audit, a non-copy check against the fixed prompt, and
  hard cumulative call, runtime and free-memory guards.
* No retry, no repair, no memory injection, no sampling change other than the
  single pre-registered axis of each experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.round3 import _number_present
from block15.run_benchmark import DATA_DIR, _now, free_physical_mb
from mdl.config import Settings, load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL = "lfm3base:latest"
MODEL_DIGEST = "b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d"
QUANTIZATION = "Q4_K_M"

NUM_CTX = 8192
TOP_P = 1.0
REPEAT_PENALTY = 1.1
SEED = 42
KEEP_ALIVE = "10m"
BASE_NUM_PREDICT = 1200
HIGH_NUM_PREDICT = 2400
BASE_TEMPERATURE = 0.1

CALL_BUDGET_TOTAL = 80
RUNTIME_BUDGET_TOTAL_S = 3600.0
PHASE_RUNTIME_S = 1800.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 60

STORE_DB_NAME = "block15_ceiling.sqlite3"
STORE_JSONL_NAME = "block15_ceiling_events.jsonl"
RESULTS_PREFIX = "block15_ceiling_results_"
SUMMARY_PREFIX = "block15_ceiling_summary_"

SYSTEM_PROMPT = (
    "You are a local mathematical reasoning model. Solve each task "
    "independently from the information given. Return exactly one JSON object "
    "matching the required schema. Be concise and exact. Do not use markdown "
    "or code fences."
)

OUTPUT_INSTRUCTION = (
    "\n\nReturn a JSON object with exactly these fields: answer, confidence, "
    "derivation, uncertainty. The answer field must contain only the final "
    "answer; put all intermediate steps in derivation. Put every string on "
    "one line; do not use markdown or code fences."
)


# ---------------------------------------------------------------------------
# Frozen held-out tasks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldoutTask:
    id: str
    kind: str  # "coefficient" or "minimality"
    question: str
    prompt: str
    expected_display: str
    expression: str | None = None
    power: int | None = None
    expected_coefficient: int | None = None
    a: int | None = None
    b: int | None = None
    c: int | None = None
    expected_n: int | None = None
    expected_value: int | None = None
    expected_primes: tuple[int, ...] | None = None

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "question": self.question,
            "prompt": self.prompt,
            "prompt_sha256": _sha256_text(self.prompt),
            "expected_display": self.expected_display,
            "expression": self.expression,
            "power": self.power,
            "coefficient": self.expected_coefficient,
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "n": self.expected_n,
            "value": self.expected_value,
            "primes": list(self.expected_primes)
            if self.expected_primes is not None
            else None,
        }


def _task(
    *,
    id: str,
    kind: str,
    question: str,
    expected_display: str,
    **kwargs: object,
) -> HeldoutTask:
    return HeldoutTask(
        id=id,
        kind=kind,
        question=question,
        prompt=question + OUTPUT_INSTRUCTION,
        expected_display=expected_display,
        **kwargs,
    )


TASKS: tuple[HeldoutTask, ...] = (
    _task(
        id="C01_coeff_3x_minus_4_pow7_x3",
        kind="coefficient",
        question=(
            "Expand (3x - 4)^7 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="241920",
        expression="(3*x - 4)**7",
        power=3,
        expected_coefficient=241920,
    ),
    _task(
        id="M01_minimal_n2_plus_5n_plus_1187",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 5n + 1187. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1211 = 7 * 173",
        a=1,
        b=5,
        c=1187,
        expected_n=3,
        expected_value=1211,
        expected_primes=(7, 173),
    ),
    _task(
        id="C02_coeff_5x_plus_2_pow8_x3",
        kind="coefficient",
        question=(
            "Expand (5x + 2)^8 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="224000",
        expression="(5*x + 2)**8",
        power=3,
        expected_coefficient=224000,
    ),
    _task(
        id="M02_minimal_n2_plus_n_plus_1091",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + n + 1091. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1111 = 11 * 101",
        a=1,
        b=1,
        c=1091,
        expected_n=4,
        expected_value=1111,
        expected_primes=(11, 101),
    ),
    _task(
        id="C03_coeff_2x_plus_5_pow9_x4",
        kind="coefficient",
        question=(
            "Expand (2x + 5)^9 and report the coefficient of x^4. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="6300000",
        expression="(2*x + 5)**9",
        power=4,
        expected_coefficient=6300000,
    ),
    _task(
        id="M03_minimal_n2_plus_3n_plus_1213",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 3n + 1213. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1241 = 17 * 73",
        a=1,
        b=3,
        c=1213,
        expected_n=4,
        expected_value=1241,
        expected_primes=(17, 73),
    ),
    _task(
        id="C04_coeff_4x_minus_3_pow6_x2",
        kind="coefficient",
        question=(
            "Expand (4x - 3)^6 and report the coefficient of x^2. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="19440",
        expression="(4*x - 3)**6",
        power=2,
        expected_coefficient=19440,
    ),
    _task(
        id="M04_minimal_3n2_plus_3n_plus_1013",
        kind="minimality",
        question=(
            "Let f(n) = 3n^2 + 3n + 1013. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1073 = 29 * 37",
        a=3,
        b=3,
        c=1013,
        expected_n=4,
        expected_value=1073,
        expected_primes=(29, 37),
    ),
    _task(
        id="C05_coeff_3x_plus_2_pow10_x6",
        kind="coefficient",
        question=(
            "Expand (3x + 2)^10 and report the coefficient of x^6. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="2449440",
        expression="(3*x + 2)**10",
        power=6,
        expected_coefficient=2449440,
    ),
    _task(
        id="M05_minimal_n2_plus_n_plus_1427",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + n + 1427. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 5, f(n) = 1457 = 31 * 47",
        a=1,
        b=1,
        c=1427,
        expected_n=5,
        expected_value=1457,
        expected_primes=(31, 47),
    ),
    _task(
        id="C06_coeff_6x_minus_1_pow7_x4",
        kind="coefficient",
        question=(
            "Expand (6x - 1)^7 and report the coefficient of x^4. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-45360",
        expression="(6*x - 1)**7",
        power=4,
        expected_coefficient=-45360,
    ),
    _task(
        id="M06_minimal_2n2_plus_2n_plus_1447",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 2n + 1447. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 5, f(n) = 1507 = 11 * 137",
        a=2,
        b=2,
        c=1447,
        expected_n=5,
        expected_value=1507,
        expected_primes=(11, 137),
    ),
    _task(
        id="C07_coeff_2x_minus_5_pow8_x3",
        kind="coefficient",
        question=(
            "Expand (2x - 5)^8 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-1400000",
        expression="(2*x - 5)**8",
        power=3,
        expected_coefficient=-1400000,
    ),
    _task(
        id="M07_minimal_n2_plus_3n_plus_1279",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 3n + 1279. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 6, f(n) = 1333 = 31 * 43",
        a=1,
        b=3,
        c=1279,
        expected_n=6,
        expected_value=1333,
        expected_primes=(31, 43),
    ),
    _task(
        id="C08_coeff_5x_minus_3_pow7_x2",
        kind="coefficient",
        question=(
            "Expand (5x - 3)^7 and report the coefficient of x^2. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-127575",
        expression="(5*x - 3)**7",
        power=2,
        expected_coefficient=-127575,
    ),
    _task(
        id="M08_minimal_2n2_plus_2n_plus_1009",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 2n + 1009. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 7, f(n) = 1121 = 19 * 59",
        a=2,
        b=2,
        c=1009,
        expected_n=7,
        expected_value=1121,
        expected_primes=(19, 59),
    ),
    _task(
        id="C09_coeff_4x_plus_1_pow9_x5",
        kind="coefficient",
        question=(
            "Expand (4x + 1)^9 and report the coefficient of x^5. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="129024",
        expression="(4*x + 1)**9",
        power=5,
        expected_coefficient=129024,
    ),
    _task(
        id="C10_coeff_3x_plus_5_pow8_x4",
        kind="coefficient",
        question=(
            "Expand (3x + 5)^8 and report the coefficient of x^4. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="3543750",
        expression="(3*x + 5)**8",
        power=4,
        expected_coefficient=3543750,
    ),
    _task(
        id="C11_coeff_6x_minus_5_pow6_x3",
        kind="coefficient",
        question=(
            "Expand (6x - 5)^6 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-540000",
        expression="(6*x - 5)**6",
        power=3,
        expected_coefficient=-540000,
    ),
    _task(
        id="C12_coeff_2x_plus_7_pow9_x6",
        kind="coefficient",
        question=(
            "Expand (2x + 7)^9 and report the coefficient of x^6. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="1843968",
        expression="(2*x + 7)**9",
        power=6,
        expected_coefficient=1843968,
    ),
)


# ---------------------------------------------------------------------------
# Frozen schemas and conditions
# ---------------------------------------------------------------------------


def _schema(answer_first: bool) -> dict:
    definitions = {
        "answer": {
            "type": "string",
            "minLength": 1,
            "maxLength": 400,
        },
        "derivation": {
            "type": "string",
            "minLength": 1,
            "maxLength": 3000,
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "uncertainty": {"type": "string", "maxLength": 600},
    }
    order = (
        ("answer", "derivation", "confidence", "uncertainty")
        if answer_first
        else ("derivation", "answer", "confidence", "uncertainty")
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(order),
        "properties": {name: definitions[name] for name in order},
    }


ANSWER_FIRST_SCHEMA = _schema(True)
DERIVATION_FIRST_SCHEMA = _schema(False)


@dataclass(frozen=True)
class Condition:
    key: str
    experiment: str
    axis: str
    role: str
    baseline_value: str
    intervention_value: str
    schema_order: str
    num_predict: int
    temperature: float

    @property
    def schema(self) -> dict:
        return (
            ANSWER_FIRST_SCHEMA
            if self.schema_order == "answer_first"
            else DERIVATION_FIRST_SCHEMA
        )

    def metadata(self) -> dict:
        return {
            **asdict(self),
            "schema_sha256": _sha256_json(self.schema, sort_keys=False),
            "schema": self.schema,
        }


CONDITIONS: dict[str, Condition] = {
    "answer_first_1200": Condition(
        key="answer_first_1200",
        experiment="experiment_1",
        axis="schema field order",
        role="baseline",
        baseline_value="answer_first",
        intervention_value="-",
        schema_order="answer_first",
        num_predict=BASE_NUM_PREDICT,
        temperature=BASE_TEMPERATURE,
    ),
    "derivation_first_1200": Condition(
        key="derivation_first_1200",
        experiment="experiment_1",
        axis="schema field order",
        role="intervention",
        baseline_value="answer_first",
        intervention_value="derivation_first",
        schema_order="derivation_first",
        num_predict=BASE_NUM_PREDICT,
        temperature=BASE_TEMPERATURE,
    ),
    "derivation_first_2400": Condition(
        key="derivation_first_2400",
        experiment="experiment_2",
        axis="num_predict",
        role="intervention",
        baseline_value="1200",
        intervention_value="2400",
        schema_order="derivation_first",
        num_predict=HIGH_NUM_PREDICT,
        temperature=BASE_TEMPERATURE,
    ),
}

CONDITION_ORDER: tuple[str, ...] = (
    "answer_first_1200",
    "derivation_first_1200",
    "derivation_first_2400",
)

# Populated after the no-call manifest run and committed before generation.
FROZEN_PROMPT_SHA256: dict[str, str] = {
    "C01_coeff_3x_minus_4_pow7_x3": (
        "41d7bec91e6ebc17c9cb78c0dcb360f2d367e8e3b123a5ab8c2d67ca6409d1f4"
    ),
    "M01_minimal_n2_plus_5n_plus_1187": (
        "e8f45591bb0e035027dea9cae9e8d0166850135b70491be1e8ea568b843bebf1"
    ),
    "C02_coeff_5x_plus_2_pow8_x3": (
        "679986ac81decf4666c775b76d7d064f96784ec73768eab2d1c0f11b7256eff9"
    ),
    "M02_minimal_n2_plus_n_plus_1091": (
        "c4e03ca7bd46f4b24c775f2f9d1acc5841fada0fd90d1d26749eaff9c9f1de9e"
    ),
    "C03_coeff_2x_plus_5_pow9_x4": (
        "52a91b07834694aba3ab7e70fa204a963b97931f1c2c6d05524d2f96206dcefd"
    ),
    "M03_minimal_n2_plus_3n_plus_1213": (
        "3e7c502c5b405bbd77f07820e1116172b9246c1e46b700b605cff86d2021e150"
    ),
    "C04_coeff_4x_minus_3_pow6_x2": (
        "8b7fd00732cfcd04130d6cd5945073c5d04d1ca8a553e25d3d120a9bfa6545a3"
    ),
    "M04_minimal_3n2_plus_3n_plus_1013": (
        "5fd82398b598a7b4e4595b553012d32ef2b5b0273bb27de765b55666fe0fa8ea"
    ),
    "C05_coeff_3x_plus_2_pow10_x6": (
        "1ba593aa6297358e1af2ea53c8392779b2c2aabd9a5f3e4069685ac3ae057097"
    ),
    "M05_minimal_n2_plus_n_plus_1427": (
        "d7dc4766c85f8234c62647bb718469086b8ce32d4105facff72535708edfa492"
    ),
    "C06_coeff_6x_minus_1_pow7_x4": (
        "1696cf2a1647b71b775e2af254535075a393cd8d70e67e0dfff5b40ca102d432"
    ),
    "M06_minimal_2n2_plus_2n_plus_1447": (
        "1b11c935af364ed06b2599de55b88e5fef2e93da15ae9498a9a8066641ec220f"
    ),
    "C07_coeff_2x_minus_5_pow8_x3": (
        "274a2857b90d9efe4dbec1ba6501d5e6f5f6529d60e657f5f8c96dc454f1921f"
    ),
    "M07_minimal_n2_plus_3n_plus_1279": (
        "331b9f41ff6cc2278dfa100106ef4c89aeedb5aee84a5fe4e1b3cd6c55242dff"
    ),
    "C08_coeff_5x_minus_3_pow7_x2": (
        "aa34a4a3db18876ff31e6216c8e2fd2882a79a37df9ad3eba2ad70d953d83550"
    ),
    "M08_minimal_2n2_plus_2n_plus_1009": (
        "321fa214a6f2a55362ae75a9857f1182459d5c31f2f2a58e79725846cf18a758"
    ),
    "C09_coeff_4x_plus_1_pow9_x5": (
        "b21757007d0630c4fd93debd74fe9a2a760d080e5a2de362d9d07e0b2d39b923"
    ),
    "C10_coeff_3x_plus_5_pow8_x4": (
        "e2fbde95b267207aaef1951adc9840e228a9fc83ef4bf7e359b754ed497a2cd6"
    ),
    "C11_coeff_6x_minus_5_pow6_x3": (
        "f5c67a01560543a2f6b049cc50c6b80e502dca15be000136910dcb6f4c134035"
    ),
    "C12_coeff_2x_plus_7_pow9_x6": (
        "d5e7c35632d374f8eadfab161e7b44874c1c7f5d2d8d1797cd7a92695eb27f30"
    ),
}
FROZEN_SCHEMA_SHA256: dict[str, str] = {
    "answer_first": (
        "9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7"
    ),
    "derivation_first": (
        "841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c"
    ),
}
FROZEN_GROUND_TRUTH_SHA256 = (
    "53fd2a8b1fa5e2368b881081c67635bb284a0d04d84a7983a9abd04f5b866f46"
)


# ---------------------------------------------------------------------------
# Hashing, extraction and strict SymPy audit
# ---------------------------------------------------------------------------


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object, *, sort_keys: bool) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=sort_keys,
        separators=(",", ":"),
    )


def _sha256_json(value: object, *, sort_keys: bool = True) -> str:
    return _sha256_text(_canonical_json(value, sort_keys=sort_keys))


_INT_RE = re.compile(r"(?<![\d.])-?\d+(?!\d|\.\d)")


def extract_answer_ints(text: str) -> list[int]:
    """Extract distinct standalone integers from an answer field.

    Thousands separators and unicode minus signs are normalized first.  A
    decimal such as ``6048.0`` is not split into two integers.
    """

    normalized = text.replace("\u2212", "-").replace("\u2013", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    return sorted({int(match.group(0)) for match in _INT_RE.finditer(normalized)})


def _normalize_minimality_answer(text: str) -> str:
    """Remove exponent-one notation before integer extraction.

    ``7^1 * 173^1`` and ``7**1 * 173**1`` are the same factorization as
    ``7 * 173``.  The exponent ``1`` is notation, not an extra answer value.
    Exponents other than one are left in place and therefore fail the strict
    set-equality check.
    """

    normalized = re.sub(r"\^\s*\{?1\}?(?!\d)", "", text)
    normalized = re.sub(r"\*\*\s*1(?!\d)", "", normalized)
    return normalized


def _is_composite(value: int) -> bool:
    return value > 1 and not sympy.isprime(value)


def ground_truth(task: HeldoutTask) -> dict:
    """Compute and verify a task's ground truth directly with SymPy."""

    if task.kind == "coefficient":
        if task.expression is None or task.power is None:
            raise ValueError(f"incomplete coefficient task: {task.id}")
        x = sympy.Symbol("x")
        coefficient = int(
            sympy.expand(sympy.sympify(task.expression)).coeff(x, task.power)
        )
        if coefficient != task.expected_coefficient:
            raise SystemExit(
                f"SymPy coefficient mismatch for {task.id}: "
                f"{coefficient} != {task.expected_coefficient}"
            )
        return {
            "kind": "coefficient",
            "expression": task.expression,
            "power": task.power,
            "coefficient": coefficient,
            "answer_tokens": [coefficient],
        }

    if any(value is None for value in (task.a, task.b, task.c)):
        raise ValueError(f"incomplete minimality task: {task.id}")
    first: tuple[int, int, dict[int, int]] | None = None
    for n in range(0, 201):
        value = int(task.a) * n * n + int(task.b) * n + int(task.c)
        if _is_composite(value):
            first = (n, value, sympy.factorint(value))
            break
    if first is None:
        raise SystemExit(f"no composite found for {task.id} within 0..200")
    n, value, factor = first
    primes = tuple(sorted(int(prime) for prime in factor))
    if any(int(exponent) != 1 for exponent in factor.values()):
        raise SystemExit(f"minimality task {task.id} is not squarefree: {factor}")
    if (
        n != task.expected_n
        or value != task.expected_value
        or primes != task.expected_primes
    ):
        raise SystemExit(
            f"SymPy minimality mismatch for {task.id}: "
            f"{(n, value, primes)} != "
            f"{(task.expected_n, task.expected_value, task.expected_primes)}"
        )
    return {
        "kind": "minimality",
        "a": task.a,
        "b": task.b,
        "c": task.c,
        "n": n,
        "value": value,
        "factorization": {
            str(prime): int(exponent) for prime, exponent in sorted(factor.items())
        },
        "primes": list(primes),
        "answer_tokens": [n, value, *primes],
    }


def ground_truth_manifest() -> dict[str, dict]:
    return {task.id: ground_truth(task) for task in TASKS}


def audit_answer(task: HeldoutTask, truth: dict, answer_text: str) -> dict:
    """Strict answer-field audit, independent of frozen expected values.

    Coefficient tasks: exactly one distinct integer in the answer field, equal
    to the SymPy coefficient.

    Minimality tasks: exactly the integer set ``{n, f(n), p1, ..., pk}``,
    after removing exponent-one notation, and SymPy must independently verify
    the squarefree factorization.
    """

    normalized_text = (
        _normalize_minimality_answer(answer_text)
        if truth["kind"] == "minimality"
        else answer_text
    )
    values = extract_answer_ints(normalized_text)
    if truth["kind"] == "coefficient":
        expected = int(truth["coefficient"])
        text_ok = values == [expected]
        return {
            "method": "sympy_expand_coeff",
            "expected_coefficient": expected,
            "extracted_ints": values,
            "text_set_equals_expected": text_ok,
            "audit_passed": bool(text_ok),
        }

    expected_set = {
        int(truth["n"]),
        int(truth["value"]),
        *(int(prime) for prime in truth["primes"]),
    }
    text_ok = set(values) == expected_set
    factor = sympy.factorint(int(truth["value"]))
    primes = sorted(int(prime) for prime in factor)
    exponents_one = all(int(exponent) == 1 for exponent in factor.values())
    product_ok = int(
        sympy.prod(
            int(prime) ** int(exponent)
            for prime, exponent in factor.items()
        )
    ) == int(truth["value"])
    factorization_ok = (
        primes == sorted(int(prime) for prime in truth["primes"])
        and exponents_one
        and product_ok
    )
    return {
        "method": "sympy_first_composite_and_factorint",
        "expected_set": sorted(expected_set),
        "expected_n": int(truth["n"]),
        "expected_value": int(truth["value"]),
        "expected_primes": [int(prime) for prime in truth["primes"]],
        "extracted_ints": values,
        "text_set_equals_expected": text_ok,
        "factorint": {
            str(prime): int(exponent)
            for prime, exponent in sorted(factor.items())
        },
        "product_verified": bool(product_ok),
        "sympy_factorization_verified": bool(factorization_ok),
        "audit_passed": bool(text_ok and factorization_ok),
    }


def copy_possible(task: HeldoutTask, truth: dict) -> dict:
    """Whether any expected answer token occurs in the fixed prompt.

    No memory or previous attempt is injected, so the fixed prompt is the
    complete copy surface.  All prompts are constructed to avoid the expected
    tokens; the check is recorded per task anyway and is a hard pre-run guard.
    """

    hits = {
        str(token): bool(_number_present(task.prompt, int(token)))
        for token in truth["answer_tokens"]
    }
    return {
        "tokens_checked": list(hits),
        "token_present_in_prompt": hits,
        "copy_possible": bool(any(hits.values())),
    }


# ---------------------------------------------------------------------------
# Frozen manifest and protected artifacts
# ---------------------------------------------------------------------------


def _manifest() -> dict:
    truth = ground_truth_manifest()
    return {
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "quantization": QUANTIZATION,
        "task_count": len(TASKS),
        "tasks": [
            {
                **task.metadata(),
                "ground_truth": truth[task.id],
                "copy": copy_possible(task, truth[task.id]),
            }
            for task in TASKS
        ],
        "ground_truth_manifest_sha256": _sha256_json(truth),
        "task_freeze_sha256": _sha256_json(
            [
                {
                    "id": task.id,
                    "prompt_sha256": _sha256_text(task.prompt),
                    "ground_truth": truth[task.id],
                }
                for task in TASKS
            ]
        ),
        "schemas": {
            "answer_first": {
                "sha256": _sha256_json(ANSWER_FIRST_SCHEMA, sort_keys=False),
                "schema": ANSWER_FIRST_SCHEMA,
            },
            "derivation_first": {
                "sha256": _sha256_json(
                    DERIVATION_FIRST_SCHEMA, sort_keys=False
                ),
                "schema": DERIVATION_FIRST_SCHEMA,
            },
        },
        "conditions": [
            CONDITIONS[key].metadata() for key in CONDITION_ORDER
        ],
        "planned_calls": PLANNED_CALLS,
        "guards": {
            "call_budget_total": CALL_BUDGET_TOTAL,
            "runtime_budget_total_s": RUNTIME_BUDGET_TOTAL_S,
            "phase_runtime_s": PHASE_RUNTIME_S,
            "min_free_mb": MIN_FREE_MB,
        },
    }


def _verify_frozen() -> dict:
    computed_prompts = {task.id: _sha256_text(task.prompt) for task in TASKS}
    computed_schemas = {
        "answer_first": _sha256_json(ANSWER_FIRST_SCHEMA, sort_keys=False),
        "derivation_first": _sha256_json(
            DERIVATION_FIRST_SCHEMA, sort_keys=False
        ),
    }
    computed_truth = _sha256_json(ground_truth_manifest())
    if not FROZEN_PROMPT_SHA256:
        raise SystemExit(
            "frozen prompt hashes are not populated; run --manifest and "
            "commit the hashes before generation"
        )
    if computed_prompts != FROZEN_PROMPT_SHA256:
        raise SystemExit("frozen prompt hashes do not match")
    if computed_schemas != FROZEN_SCHEMA_SHA256:
        raise SystemExit("frozen schema hashes do not match")
    if not FROZEN_GROUND_TRUTH_SHA256:
        raise SystemExit(
            "frozen ground-truth hash is not populated; run --manifest and "
            "commit the hash before generation"
        )
    if computed_truth != FROZEN_GROUND_TRUTH_SHA256:
        raise SystemExit("frozen ground-truth manifest hash does not match")
    truth = ground_truth_manifest()
    copy_hits = [
        task.id for task in TASKS if copy_possible(task, truth[task.id])[
            "copy_possible"
        ]
    ]
    if copy_hits:
        raise SystemExit(f"copy-possible tasks are not allowed: {copy_hits}")
    return {
        "prompts": computed_prompts,
        "schemas": computed_schemas,
        "ground_truth_manifest": computed_truth,
    }


_PROTECTED_GLOBS: tuple[str, ...] = (
    "BLOCK15_*.md",
    "PREREG_*.md",
    "REPORT_*.md",
    "README_BLOCK*.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "block15/*.py",
    "mdl/*.py",
    "qresearch/*.py",
    "qbacktest/*.py",
)

_PROTECTED_EXPLICIT: tuple[str, ...] = (
    "data/block15_round3.sqlite3",
    "data/block15_round3_events.jsonl",
    "data/block15_round3_ground_truth.json",
    "data/block15_round3_assessments.json",
    "data/block15_round3_results_round3_20261111T143825Z.json",
    "data/block15_round4_arm_a.sqlite3",
    "data/block15_round4_arm_a_events.jsonl",
    "data/block15_round4_arm_b.sqlite3",
    "data/block15_round4_arm_b_events.jsonl",
    "data/block15_round4_arm_a_results_round3_20261114T215552Z.json",
    "data/block15_round4_arm_b_results_round3_20261114T220133Z.json",
    "data/block15_pilot_memory.sqlite3",
    "data/block15_pilot_memory_events.jsonl",
    "data/block15_pilot_memory_results_20261115T174655Z.json",
    "data/block15_heldout.sqlite3",
    "data/block15_heldout_events.jsonl",
    "data/block15_heldout_results_baseline_20261115T185523Z.json",
    "data/block15_heldout_results_schema_20261115T190224Z.json",
    "data/block15_heldout_results_numpredict_20261115T190551Z.json",
    "data/block15_heldout_results_temperature_20261115T191207Z.json",
)


def _protected_paths() -> list[str]:
    root = DATA_DIR.parent
    names: set[str] = set(_PROTECTED_EXPLICIT)
    for pattern in _PROTECTED_GLOBS:
        for path in root.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                names.add(str(path.relative_to(root)))
    return sorted(names)


def _protected_hashes() -> dict[str, str | None]:
    root = DATA_DIR.parent
    return {name: _sha256_file(root / name) for name in _protected_paths()}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class GuardStop(RuntimeError):
    """A pre-registered call, runtime or memory guard stopped the run."""


def _settings(condition: Condition) -> Settings:
    return load_settings(
        model=MODEL,
        db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=NUM_CTX,
        think=False,
        temperature=condition.temperature,
        top_p=TOP_P,
        repeat_penalty=REPEAT_PENALTY,
        seed=SEED,
        keep_alive=KEEP_ALIVE,
    )


def _verify_model(client: OllamaClient) -> tuple[str, dict]:
    if not client.health():
        raise SystemExit("Ollama is not reachable")
    model_info = client.model_info()
    if model_info is None:
        raise SystemExit(f"model {MODEL!r} is not installed")
    digest = model_info.get("digest")
    if digest != MODEL_DIGEST:
        raise SystemExit(
            f"model digest mismatch: expected {MODEL_DIGEST}, got {digest}"
        )
    details = model_info.get("details") or {}
    quantization = details.get("quantization_level")
    if quantization != QUANTIZATION:
        raise SystemExit(
            f"model quantization mismatch: expected {QUANTIZATION}, "
            f"got {quantization}"
        )
    return str(digest), model_info


def _prior_totals() -> dict:
    calls = 0
    runtime_s = 0.0
    files: list[str] = []
    for path in sorted(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"cannot read prior result file {path}: {exc}")
        calls += int(record.get("calls_used_total", 0))
        runtime_s += float(record.get("runtime_s_total", 0.0))
        files.append(path.name)
    return {"calls": calls, "runtime_s": round(runtime_s, 2), "files": files}


def _validate_final(parsed: dict) -> dict:
    required = ("answer", "derivation", "confidence", "uncertainty")
    missing = [name for name in required if name not in parsed]
    if missing:
        raise ValueError(f"answer JSON is missing fields: {missing}")
    answer = parsed["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be a non-empty string")
    derivation = parsed["derivation"]
    if not isinstance(derivation, str):
        raise ValueError("derivation must be a string")
    uncertainty = parsed["uncertainty"]
    if not isinstance(uncertainty, str):
        raise ValueError("uncertainty must be a string")
    confidence = parsed["confidence"]
    if isinstance(confidence, bool) or not isinstance(
        confidence, (int, float)
    ):
        raise ValueError("confidence must be a number")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return {
        "answer": answer,
        "derivation": derivation,
        "confidence": confidence,
        "uncertainty": uncertainty,
    }


def _json_object_or_none(content: str | None) -> dict | None:
    """Mirror the client's JSON extraction without raising.

    This is used for two descriptive purposes only: identifying invalid-JSON
    failures and re-auditing the answer field of a JSON object that failed
    schema validation.  The primary audit still requires a validated final.
    """

    if not isinstance(content, str) or not content.strip():
        return None
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class CeilingRunner:
    def __init__(
        self,
        condition: Condition,
        settings: Settings,
        client: OllamaClient,
        store: ResearchStore,
        digest: str,
        model_info: dict,
        run_id: str,
        experiment_id: str,
        prior: dict,
    ) -> None:
        self.condition = condition
        self.settings = settings
        self.client = client
        self.store = store
        self.digest = digest
        self.model_info = model_info
        self.run_id = run_id
        self.experiment_id = experiment_id
        self.prior = prior
        self.run_started = perf_counter()
        self.calls_used = 0
        self.free_mb_min: float | None = None

    @property
    def elapsed_s(self) -> float:
        return perf_counter() - self.run_started

    def _guard(self) -> None:
        total_calls = int(self.prior["calls"]) + self.calls_used
        if total_calls + 1 > CALL_BUDGET_TOTAL:
            raise GuardStop(
                f"cumulative model-call budget {CALL_BUDGET_TOTAL} reached"
            )
        total_runtime = float(self.prior["runtime_s"]) + self.elapsed_s
        if total_runtime >= RUNTIME_BUDGET_TOTAL_S:
            raise GuardStop(
                f"cumulative runtime budget {RUNTIME_BUDGET_TOTAL_S:.0f}s "
                "reached"
            )
        if self.elapsed_s >= PHASE_RUNTIME_S:
            raise GuardStop(
                f"phase runtime limit {PHASE_RUNTIME_S:.0f}s reached"
            )
        free_mb = free_physical_mb()
        if free_mb is not None:
            if self.free_mb_min is None or free_mb < self.free_mb_min:
                self.free_mb_min = free_mb
            if free_mb < MIN_FREE_MB:
                raise GuardStop(
                    f"free physical memory {free_mb:.1f} MB below "
                    f"{MIN_FREE_MB:.0f} MB"
                )

    def run_task(self, task: HeldoutTask, truth: dict) -> dict:
        self._guard()
        self.calls_used += 1
        call_index = self.calls_used
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task.prompt},
        ]
        schema = self.condition.schema
        started = perf_counter()
        response = None
        raw_content: str | None = None
        done_reason: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None
        final: dict | None = None
        error: str | None = None
        status = "error"

        try:
            response = self.client.chat_json(
                messages, schema, num_predict=self.condition.num_predict
            )
            raw_content = response.content
            done_reason = response.done_reason
            prompt_eval_count = response.prompt_eval_count
            eval_count = response.eval_count
            try:
                final = _validate_final(response.parsed)
            except Exception as exc:  # noqa: BLE001 - invalid output is data
                error = f"{type(exc).__name__}: {exc}"
                status = "invalid"
            else:
                status = "truncated" if done_reason == "length" else "ok"
        except ModelOutputError as exc:
            raw_content = exc.raw_content
            done_reason = exc.done_reason
            prompt_eval_count = exc.prompt_eval_count
            eval_count = exc.eval_count
            error = f"{type(exc).__name__}: {exc}"
            status = "output_error"
        except ModelTimeoutError as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "timeout"
        except ModelError as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "model_error"
        except Exception as exc:  # noqa: BLE001 - transport failures are data
            error = f"{type(exc).__name__}: {exc}"
            status = "error"

        latency_ms = (perf_counter() - started) * 1000.0
        parsed_raw = _json_object_or_none(raw_content)
        json_valid = parsed_raw is not None

        if final is not None:
            audit = audit_answer(task, truth, final["answer"])
        else:
            audit = {
                "method": "not_run",
                "audit_passed": False,
                "note": "attempt produced no validated final",
            }

        math_only_audit = None
        math_only_answer_text = None
        if parsed_raw is not None:
            raw_answer = parsed_raw.get("answer")
            if isinstance(raw_answer, str):
                math_only_answer_text = raw_answer
                math_only_audit = audit_answer(task, truth, raw_answer)

        copied = copy_possible(task, truth)
        row = {
            "call_index": call_index,
            "task_id": task.id,
            "task_kind": task.kind,
            "condition": self.condition.key,
            "experiment": self.condition.experiment,
            "axis": self.condition.axis,
            "role": self.condition.role,
            "prompt_sha256": _sha256_text(task.prompt),
            "schema_sha256": _sha256_json(schema),
            "num_predict": self.condition.num_predict,
            "temperature": self.condition.temperature,
            "status": status,
            "error": error,
            "raw_content": raw_content,
            "raw_content_sha256": (
                _sha256_text(raw_content) if raw_content is not None else None
            ),
            "json_valid": json_valid,
            "invalid_json": not json_valid,
            "schema_valid": final is not None,
            "length_truncated": done_reason == "length",
            "done_reason": done_reason,
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
            "confidence": final["confidence"] if final is not None else None,
            "final": final,
            "answer_text": final["answer"] if final is not None else None,
            "derivation_text": (
                final["derivation"] if final is not None else None
            ),
            "math_only_answer_text": math_only_answer_text,
            "math_only_audit": math_only_audit,
            "math_only_audit_passed": bool(
                math_only_audit is not None
                and math_only_audit["audit_passed"]
            ),
            "audit": audit,
            "audit_passed": bool(audit["audit_passed"]),
            "copy": copied,
            "copy_possible": bool(copied["copy_possible"]),
            "latency_ms": round(latency_ms, 2),
        }
        self.store.log_step(
            self.experiment_id,
            "ceiling_attempt",
            status,
            row,
            latency_ms=latency_ms,
        )
        print(
            f"    task={task.id:<44} status={status:<12} "
            f"audit={row['audit_passed']} "
            f"copy={row['copy_possible']} "
            f"confidence={row['confidence']} eval={eval_count} "
            f"done={done_reason} latency_s={latency_ms / 1000:.1f}",
            flush=True,
        )
        return row


def _phase_paths(condition_key: str, ts: str) -> Path:
    return DATA_DIR / f"{RESULTS_PREFIX}{condition_key}_{ts}.json"


def _condition_summary(rows: list[dict]) -> dict:
    passes = [
        row["task_id"]
        for row in rows
        if row["audit_passed"] and not row["copy_possible"]
    ]
    return {
        "completed_tasks": len(rows),
        "noncopy_pass_count": len(passes),
        "noncopy_passes": passes,
        "invalid_json_count": sum(1 for row in rows if row["invalid_json"]),
        "schema_invalid_count": sum(
            1 for row in rows if row["status"] == "invalid"
        ),
        "output_error_count": sum(
            1 for row in rows if row["status"] == "output_error"
        ),
        "length_truncated_count": sum(
            1 for row in rows if row["length_truncated"]
        ),
        "done_reasons": dict(Counter(row["done_reason"] for row in rows)),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "prompt_tokens_total": sum(
            int(row["prompt_eval_count"] or 0) for row in rows
        ),
        "eval_tokens_total": sum(
            int(row["eval_count"] or 0) for row in rows
        ),
        "eval_tokens_mean": (
            round(
                sum(int(row["eval_count"] or 0) for row in rows) / len(rows),
                2,
            )
            if rows
            else None
        ),
        "mean_latency_s": (
            round(sum(row["latency_ms"] for row in rows) / len(rows) / 1000, 2)
            if rows
            else None
        ),
    }


def run_phase(condition_key: str) -> Path:
    if condition_key not in CONDITIONS:
        raise SystemExit(
            f"unknown condition {condition_key!r}; "
            f"choose from {sorted(CONDITIONS)}"
        )
    condition = CONDITIONS[condition_key]
    existing = sorted(
        DATA_DIR.glob(f"{RESULTS_PREFIX}{condition_key}_*.json")
    )
    if existing:
        raise SystemExit(
            "refusing to rerun a pre-registered condition; existing file: "
            f"{existing[0]}"
        )

    prerequisites = {
        "derivation_first_1200": ("answer_first_1200", "Experiment 1 baseline"),
        "derivation_first_2400": (
            "derivation_first_1200",
            "Experiment 1 derivation-first condition",
        ),
    }
    if condition_key in prerequisites:
        prerequisite_key, prerequisite_label = prerequisites[condition_key]
        prerequisite_files = sorted(
            DATA_DIR.glob(f"{RESULTS_PREFIX}{prerequisite_key}_*.json")
        )
        if not prerequisite_files:
            raise SystemExit(
                f"{prerequisite_label} must be run first: no "
                f"{RESULTS_PREFIX}{prerequisite_key}_*.json result file"
            )
        if len(prerequisite_files) > 1:
            raise SystemExit(
                f"multiple prerequisite result files for {prerequisite_key}"
            )
        prerequisite = json.loads(
            prerequisite_files[0].read_text(encoding="utf-8")
        )
        if prerequisite.get("stopped_early") or len(
            prerequisite.get("results", [])
        ) != len(TASKS):
            raise SystemExit(
                f"{prerequisite_label} is incomplete; refusing to run "
                f"{condition_key} on a partial baseline"
            )

    frozen = _verify_frozen()
    truth_manifest = ground_truth_manifest()
    prior = _prior_totals()
    if int(prior["calls"]) + len(TASKS) > CALL_BUDGET_TOTAL:
        raise SystemExit(
            f"cumulative call budget would be exceeded: {prior['calls']} used"
        )
    if float(prior["runtime_s"]) >= RUNTIME_BUDGET_TOTAL_S:
        raise SystemExit(
            f"cumulative runtime budget already used: {prior['runtime_s']}s"
        )

    settings = _settings(condition)
    settings.ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_path = _phase_paths(condition.key, ts)
    if results_path.exists():
        raise SystemExit(f"refusing to overwrite {results_path}")

    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    record: dict = {
        "run_id": f"ceiling_{condition.key}_{ts}",
        "kind": "ceiling_bounded_math",
        "condition": condition.key,
        "condition_definition": condition.metadata(),
        "started_at": _now(),
        "model": MODEL,
        "model_digest": None,
        "model_info": None,
        "settings": {
            "think": settings.think,
            "num_ctx": settings.context_limit,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "repeat_penalty": settings.repeat_penalty,
            "seed": settings.seed,
            "keep_alive": settings.keep_alive,
            "num_predict": condition.num_predict,
        },
        "frozen_manifest": frozen,
        "ground_truth_manifest": truth_manifest,
        "guards": {
            "call_budget_total": CALL_BUDGET_TOTAL,
            "runtime_budget_total_s": RUNTIME_BUDGET_TOTAL_S,
            "phase_runtime_s": PHASE_RUNTIME_S,
            "min_free_mb": MIN_FREE_MB,
        },
        "prior_totals": prior,
        "planned_calls": len(TASKS),
        "protected_artifacts_sha256_start": _protected_hashes(),
        "free_mb_start": free_physical_mb(),
        "free_mb_min": None,
        "free_mb_end": None,
        "results": [],
        "stopped_early": False,
        "stop_reason": None,
    }

    try:
        digest, model_info = _verify_model(client)
        record["model_digest"] = digest
        record["model_info"] = model_info
        experiment_id = store.create_experiment(
            seed=condition.key,
            model=MODEL,
            model_digest=digest,
            parameters={
                "run_id": record["run_id"],
                "round": "ceiling_bounded_math",
                "condition": condition.key,
                "experiment": condition.experiment,
                "axis": condition.axis,
                "role": condition.role,
                "baseline_value": condition.baseline_value,
                "intervention_value": condition.intervention_value,
                "num_ctx": settings.context_limit,
                "num_predict": condition.num_predict,
                "temperature": condition.temperature,
                "top_p": settings.top_p,
                "repeat_penalty": settings.repeat_penalty,
                "seed": settings.seed,
                "think": settings.think,
                "keep_alive": settings.keep_alive,
            },
            context_limit=settings.context_limit,
        )
        runner = CeilingRunner(
            condition,
            settings,
            client,
            store,
            digest,
            model_info,
            record["run_id"],
            experiment_id,
            prior,
        )
        store.log_event(
            experiment_id,
            "ceiling_phase_started",
            {
                "condition": condition.key,
                "tasks": [task.id for task in TASKS],
                "started_at": _now(),
            },
        )

        for index, task in enumerate(TASKS, start=1):
            print(
                f"[{index}/{len(TASKS)}] {task.id} "
                f"calls_used={runner.calls_used} "
                f"elapsed_s={runner.elapsed_s:.1f}",
                flush=True,
            )
            try:
                row = runner.run_task(task, truth_manifest[task.id])
            except GuardStop as exc:
                record["stopped_early"] = True
                record["stop_reason"] = str(exc)
                print(f"STOP: {exc}", flush=True)
                break
            record["results"].append(row)
            record["free_mb_min"] = runner.free_mb_min
            results_path.write_text(
                json.dumps(record, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

        rows = record["results"]
        summary = _condition_summary(rows)
        record["summary"] = summary
        store.set_experiment_fields(
            experiment_id,
            hypothesis_json={
                "condition": condition.key,
                "experiment": condition.experiment,
                "axis": condition.axis,
                "baseline_value": condition.baseline_value,
                "intervention_value": condition.intervention_value,
            },
            interpretation_json={"summary": summary, "results": rows},
            verification_json=summary,
            context_json={
                "run_id": record["run_id"],
                "condition": condition.key,
                "tasks": [task.id for task in TASKS],
            },
        )
        store.finish_experiment(
            experiment_id,
            "completed" if not record["stopped_early"] else "stopped",
            latency_ms=round(runner.elapsed_s * 1000.0, 2),
            error=record["stop_reason"],
            token_usage={
                "prompt_eval_count": sum(
                    int(row["prompt_eval_count"] or 0) for row in rows
                ),
                "eval_count": sum(
                    int(row["eval_count"] or 0) for row in rows
                ),
                "model_calls": runner.calls_used,
            },
        )
        record["finished_at"] = _now()
        record["free_mb_end"] = free_physical_mb()
        record["free_mb_min"] = runner.free_mb_min
        record["calls_used_total"] = runner.calls_used
        record["runtime_s_total"] = round(runner.elapsed_s, 2)
        record["protected_artifacts_sha256_end"] = _protected_hashes()
        record["protected_manifest_sha256"] = _sha256_json(
            record["protected_artifacts_sha256_end"]
        )
        record["protected_artifacts_unchanged"] = (
            record["protected_artifacts_sha256_start"]
            == record["protected_artifacts_sha256_end"]
        )
        record["jsonl_chain"] = store.verify_jsonl()
        record["module_sha256"] = _sha256_file(Path(__file__))
        results_path.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"results: {results_path}", flush=True)
        print(
            f"calls_used={runner.calls_used} "
            f"runtime_s={runner.elapsed_s:.1f} "
            f"completed={len(rows)} "
            f"stopped_early={record['stopped_early']}",
            flush=True,
        )
        return results_path
    finally:
        client.close()
        store.close()


# ---------------------------------------------------------------------------
# Read-only summaries
# ---------------------------------------------------------------------------


def _load_phase_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"cannot read result file {path}: {exc}")
        condition = record.get("condition")
        if condition in records:
            raise SystemExit(
                f"multiple result files for condition {condition!r}: "
                f"{records[condition].get('_path')} and {path.name}"
            )
        record["_path"] = path.name
        records[str(condition)] = record
    return records


def _row_by_task(record: dict | None) -> dict[str, dict]:
    if record is None:
        return {}
    return {row["task_id"]: row for row in record.get("results", [])}


def _noncopy_pass(row: dict | None) -> bool:
    return bool(
        row is not None
        and row.get("audit_passed")
        and not row.get("copy_possible")
    )


def _mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for discordant counts b and c."""

    total = b + c
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2**total))


def _bootstrap_risk_difference_ci(
    baseline_passes: list[bool],
    intervention_passes: list[bool],
    *,
    seed: int = 42,
    iterations: int = 10000,
) -> list[float] | None:
    if not baseline_passes or len(baseline_passes) != len(intervention_passes):
        return None
    rng = random.Random(seed)
    n = len(baseline_passes)
    differences = [
        int(intervention_passes[i]) - int(baseline_passes[i])
        for i in range(n)
    ]
    estimates: list[float] = []
    for _ in range(iterations):
        total = 0
        for _ in range(n):
            total += differences[rng.randrange(n)]
        estimates.append(total / n)
    estimates.sort()
    low = estimates[int(0.025 * (iterations - 1))]
    high = estimates[int(0.975 * (iterations - 1))]
    return [round(low, 4), round(high, 4)]


def _paired_effect(
    baseline_rows: dict[str, dict],
    intervention_rows: dict[str, dict],
    *,
    complete: bool,
) -> dict:
    task_ids = [task.id for task in TASKS]
    baseline_flags = [_noncopy_pass(baseline_rows.get(task_id)) for task_id in task_ids]
    intervention_flags = [
        _noncopy_pass(intervention_rows.get(task_id)) for task_id in task_ids
    ]
    baseline_pass = sum(baseline_flags)
    intervention_pass = sum(intervention_flags)
    b = sum(
        1
        for base, inter in zip(baseline_flags, intervention_flags)
        if base and not inter
    )
    c = sum(
        1
        for base, inter in zip(baseline_flags, intervention_flags)
        if not base and inter
    )
    n = len(task_ids)
    risk_difference = round((intervention_pass - baseline_pass) / n, 4)
    return {
        "complete": complete,
        "tasks": n,
        "baseline_noncopy_passes": baseline_pass,
        "intervention_noncopy_passes": intervention_pass,
        "difference": intervention_pass - baseline_pass,
        "risk_difference": risk_difference,
        "risk_difference_ci95": _bootstrap_risk_difference_ci(
            baseline_flags, intervention_flags
        ),
        "discordant_baseline_pass_intervention_fail": b,
        "discordant_baseline_fail_intervention_pass": c,
        "mcnemar_exact_two_sided_p": round(_mcnemar_exact(b, c), 6),
        "odds_ratio_descriptive": (
            None
            if b == 0 and c == 0
            else "inf"
            if b == 0
            else 0.0
            if c == 0
            else round(c / b, 4)
        ),
    }


def _per_task_rows(
    baseline_rows: dict[str, dict],
    intervention_rows: dict[str, dict],
    *,
    experiment: str,
) -> list[dict]:
    output: list[dict] = []
    for task in TASKS:
        base = baseline_rows.get(task.id)
        inter = intervention_rows.get(task.id)
        base_pass = _noncopy_pass(base)
        inter_pass = _noncopy_pass(inter)
        item = {
            "task_id": task.id,
            "task_kind": task.kind,
            "baseline_present": base is not None,
            "baseline_status": base.get("status") if base else None,
            "baseline_done_reason": base.get("done_reason") if base else None,
            "baseline_audit_passed": bool(base.get("audit_passed")) if base else None,
            "baseline_copy_possible": bool(base.get("copy_possible")) if base else None,
            "baseline_noncopy_pass": base_pass,
            "baseline_answer_text": base.get("answer_text") if base else None,
            "baseline_eval_count": base.get("eval_count") if base else None,
            "baseline_length_truncated": bool(base.get("length_truncated")) if base else None,
            "intervention_present": inter is not None,
            "intervention_status": inter.get("status") if inter else None,
            "intervention_done_reason": inter.get("done_reason") if inter else None,
            "intervention_audit_passed": bool(inter.get("audit_passed")) if inter else None,
            "intervention_copy_possible": bool(inter.get("copy_possible")) if inter else None,
            "intervention_noncopy_pass": inter_pass,
            "intervention_answer_text": inter.get("answer_text") if inter else None,
            "intervention_eval_count": inter.get("eval_count") if inter else None,
            "delta_pass": int(inter_pass) - int(base_pass),
        }
        if experiment == "experiment_2":
            item["additional_pass_on_truncated_baseline"] = bool(
                base is not None
                and inter is not None
                and base.get("length_truncated")
                and not base_pass
                and inter_pass
            )
            item["lost_existing_pass"] = bool(base_pass and not inter_pass)
        output.append(item)
    return output


def summarize() -> dict:
    records = _load_phase_records()

    condition_summaries: dict[str, dict] = {}
    for key in CONDITION_ORDER:
        record = records.get(key)
        if record is None:
            condition_summaries[key] = {
                "present": False,
                "completed_tasks": 0,
                "noncopy_passes": [],
                "invalid_json_count": None,
                "length_truncated_count": None,
            }
            continue
        rows = record.get("results", [])
        condition_summaries[key] = {
            "present": True,
            "axis": record["condition_definition"]["axis"],
            "role": record["condition_definition"]["role"],
            "baseline_value": record["condition_definition"]["baseline_value"],
            "intervention_value": record["condition_definition"][
                "intervention_value"
            ],
            "stopped_early": bool(record.get("stopped_early")),
            "stop_reason": record.get("stop_reason"),
            "calls_used_total": record.get("calls_used_total"),
            "runtime_s_total": record.get("runtime_s_total"),
            "free_mb_min": record.get("free_mb_min"),
            "protected_artifacts_unchanged": record.get(
                "protected_artifacts_unchanged"
            ),
            **_condition_summary(rows),
        }

    base1 = _row_by_task(records.get("answer_first_1200"))
    inter1 = _row_by_task(records.get("derivation_first_1200"))
    base2 = inter1
    inter2 = _row_by_task(records.get("derivation_first_2400"))

    complete1 = (
        records.get("answer_first_1200") is not None
        and records.get("derivation_first_1200") is not None
        and not records["answer_first_1200"].get("stopped_early")
        and not records["derivation_first_1200"].get("stopped_early")
        and len(base1) == len(TASKS)
        and len(inter1) == len(TASKS)
    )
    effect1 = _paired_effect(base1, inter1, complete=complete1)
    invalid_base1 = sum(
        1 for row in base1.values() if row.get("invalid_json")
    )
    invalid_inter1 = sum(
        1 for row in inter1.values() if row.get("invalid_json")
    )
    success1 = bool(
        complete1
        and effect1["intervention_noncopy_passes"]
        > effect1["baseline_noncopy_passes"]
        and invalid_inter1 <= invalid_base1
    )
    experiment_1 = {
        "prereg": "PREREG_CEILING_SCHEMA.md",
        "baseline_condition": "answer_first_1200",
        "intervention_condition": "derivation_first_1200",
        "criterion": (
            "derivation-first audited non-copy passes > answer-first audited "
            "non-copy passes, and derivation-first invalid-JSON failures <= "
            "answer-first invalid-JSON failures; complete 20-task run required"
        ),
        "invalid_json_baseline": invalid_base1,
        "invalid_json_intervention": invalid_inter1,
        "success": success1,
        "verdict": (
            "SURVIVES"
            if success1
            else "INCOMPLETE"
            if not complete1
            else "DIES"
        ),
        **effect1,
        "per_task": _per_task_rows(base1, inter1, experiment="experiment_1"),
    }

    complete2 = (
        records.get("derivation_first_1200") is not None
        and records.get("derivation_first_2400") is not None
        and not records["derivation_first_1200"].get("stopped_early")
        and not records["derivation_first_2400"].get("stopped_early")
        and len(base2) == len(TASKS)
        and len(inter2) == len(TASKS)
    )
    effect2 = _paired_effect(base2, inter2, complete=complete2)
    truncated_tasks = [
        task.id
        for task in TASKS
        if task.id in base2 and base2[task.id].get("length_truncated")
    ]
    additional_passes = [
        task.id
        for task in TASKS
        if task.id in truncated_tasks
        and not _noncopy_pass(base2.get(task.id))
        and _noncopy_pass(inter2.get(task.id))
    ]
    lost_passes = [
        task.id
        for task in TASKS
        if _noncopy_pass(base2.get(task.id))
        and not _noncopy_pass(inter2.get(task.id))
    ]
    invalid_base2 = sum(
        1 for row in base2.values() if row.get("invalid_json")
    )
    invalid_inter2 = sum(
        1 for row in inter2.values() if row.get("invalid_json")
    )
    success2 = bool(
        complete2
        and bool(truncated_tasks)
        and bool(additional_passes)
        and not lost_passes
    )
    experiment_2 = {
        "prereg": "PREREG_CEILING_BUDGET.md",
        "baseline_condition": "derivation_first_1200",
        "intervention_condition": "derivation_first_2400",
        "criterion": (
            "at least one additional audited non-copy pass on a task whose "
            "derivation-first 1200 run was length-truncated, with no loss of "
            "existing non-copy passes; complete 20-task run required"
        ),
        "invalid_json_baseline": invalid_base2,
        "invalid_json_intervention": invalid_inter2,
        "length_truncated_baseline_tasks": truncated_tasks,
        "additional_passes_on_truncated_baseline": additional_passes,
        "lost_existing_passes": lost_passes,
        "success": success2,
        "verdict": (
            "SURVIVES"
            if success2
            else "INCOMPLETE"
            if not complete2
            else "DIES_NO_LENGTH_TRUNCATED_TASK"
            if not truncated_tasks
            else "DIES"
        ),
        **effect2,
        "per_task": _per_task_rows(base2, inter2, experiment="experiment_2"),
    }

    protected_manifests = []
    for key in CONDITION_ORDER:
        record = records.get(key)
        if record is None:
            continue
        protected_manifests.append(
            {
                "condition": key,
                "start_sha256": _sha256_json(
                    record.get("protected_artifacts_sha256_start", {})
                ),
                "end_sha256": _sha256_json(
                    record.get("protected_artifacts_sha256_end", {})
                ),
                "unchanged": record.get("protected_artifacts_unchanged"),
            }
        )

    artifact_hashes = {
        "results": {
            key: _sha256_file(DATA_DIR / record["_path"])
            for key, record in records.items()
        },
        "store_db": _sha256_file(DATA_DIR / STORE_DB_NAME),
        "store_jsonl": _sha256_file(DATA_DIR / STORE_JSONL_NAME),
        "module": _sha256_file(Path(__file__)),
        "prereg": {
            "PREREG_CEILING_SCHEMA.md": _sha256_file(
                DATA_DIR.parent / "PREREG_CEILING_SCHEMA.md"
            ),
            "PREREG_CEILING_BUDGET.md": _sha256_file(
                DATA_DIR.parent / "PREREG_CEILING_BUDGET.md"
            ),
        },
    }

    return {
        "study": "ceiling_schema_then_budget",
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "task_count": len(TASKS),
        "task_freeze_sha256": _manifest()["task_freeze_sha256"],
        "ground_truth_manifest_sha256": _sha256_json(
            ground_truth_manifest()
        ),
        "conditions": condition_summaries,
        "experiment_1": experiment_1,
        "experiment_2": experiment_2,
        "protected_manifests": protected_manifests,
        "artifact_hashes": artifact_hashes,
        "limits": {
            "single_seed": SEED,
            "one_call_per_task_per_condition": True,
            "n_tasks": len(TASKS),
            "capability_ranking": False,
            "weight_adaptation_claim": False,
        },
    }


def recheck() -> dict:
    """Read-only internal consistency check over every stored row."""

    records = _load_phase_records()
    truth = ground_truth_manifest()
    tasks_by_id = {task.id: task for task in TASKS}
    rows_checked = 0
    stored_passes: list[str] = []
    math_only_passes: list[str] = []
    mismatches: list[dict] = []
    raw_hash_mismatches: list[dict] = []
    prompt_hash_mismatches: list[dict] = []
    copy_mismatches: list[dict] = []
    audit_false_positives: list[dict] = []
    protected_failures: list[str] = []

    for condition, record in records.items():
        if not record.get("protected_artifacts_unchanged"):
            protected_failures.append(condition)
        for row in record.get("results", []):
            rows_checked += 1
            task = tasks_by_id.get(row["task_id"])
            if task is None:
                mismatches.append(
                    {"condition": condition, "task_id": row["task_id"],
                     "reason": "unknown task"}
                )
                continue
            expected_prompt_sha = _sha256_text(task.prompt)
            if row.get("prompt_sha256") != expected_prompt_sha:
                prompt_hash_mismatches.append(
                    {"condition": condition, "task_id": task.id}
                )
            if row.get("raw_content") is not None:
                expected_raw_sha = _sha256_text(row["raw_content"])
            else:
                expected_raw_sha = None
            if row.get("raw_content_sha256") != expected_raw_sha:
                raw_hash_mismatches.append(
                    {"condition": condition, "task_id": task.id}
                )
            copied = copy_possible(task, truth[task.id])
            if bool(row.get("copy_possible")) != bool(copied["copy_possible"]):
                copy_mismatches.append(
                    {"condition": condition, "task_id": task.id}
                )
            if row.get("audit_passed"):
                stored_passes.append(f"{condition}:{task.id}")
            parsed_raw = _json_object_or_none(row.get("raw_content"))
            math_only = None
            if parsed_raw is not None and isinstance(
                parsed_raw.get("answer"), str
            ):
                math_only = audit_answer(
                    task, truth[task.id], parsed_raw["answer"]
                )
            if math_only is not None and math_only["audit_passed"]:
                math_only_passes.append(f"{condition}:{task.id}")
            if row.get("math_only_audit_passed") != bool(
                math_only is not None and math_only["audit_passed"]
            ):
                mismatches.append(
                    {
                        "condition": condition,
                        "task_id": task.id,
                        "reason": "math-only audit flag mismatch",
                    }
                )
            if row.get("audit_passed") and not (
                math_only is not None and math_only["audit_passed"]
            ):
                audit_false_positives.append(
                    {"condition": condition, "task_id": task.id}
                )
            if row.get("audit_passed") and row.get("math_only_answer_text") != row.get("answer_text"):
                mismatches.append(
                    {
                        "condition": condition,
                        "task_id": task.id,
                        "reason": "audited answer text differs from validated answer",
                    }
                )

    jsonl_chain = None
    if (DATA_DIR / STORE_JSONL_NAME).exists():
        store = ResearchStore(
            DATA_DIR / STORE_DB_NAME, DATA_DIR / STORE_JSONL_NAME
        )
        try:
            jsonl_chain = store.verify_jsonl()
        finally:
            store.close()

    return {
        "rows_checked": rows_checked,
        "stored_audit_passes": stored_passes,
        "stored_audit_pass_count": len(stored_passes),
        "recomputed_math_only_passes": math_only_passes,
        "recomputed_math_only_pass_count": len(math_only_passes),
        "audit_false_positives": audit_false_positives,
        "raw_hash_mismatches": raw_hash_mismatches,
        "prompt_hash_mismatches": prompt_hash_mismatches,
        "copy_mismatches": copy_mismatches,
        "row_mismatches": mismatches,
        "protected_manifest_failures": protected_failures,
        "jsonl_chain": jsonl_chain,
        "ok": bool(
            not audit_false_positives
            and not raw_hash_mismatches
            and not prompt_hash_mismatches
            and not copy_mismatches
            and not mismatches
            and not protected_failures
            and jsonl_chain is not None
            and jsonl_chain.get("valid")
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def selfcheck() -> dict:
    frozen = _verify_frozen()
    truth = ground_truth_manifest()
    copies = {
        task.id: copy_possible(task, truth[task.id])["copy_possible"]
        for task in TASKS
    }
    manifest = _manifest()
    return {
        "ok": not any(copies.values()),
        "task_count": len(TASKS),
        "coefficient_tasks": sum(1 for task in TASKS if task.kind == "coefficient"),
        "minimality_tasks": sum(1 for task in TASKS if task.kind == "minimality"),
        "copy_possible": copies,
        "frozen": frozen,
        "task_freeze_sha256": manifest["task_freeze_sha256"],
        "ground_truth_manifest_sha256": manifest[
            "ground_truth_manifest_sha256"
        ],
        "planned_calls": PLANNED_CALLS,
        "guards": manifest["guards"],
        "results_prefix": RESULTS_PREFIX,
        "store_db": STORE_DB_NAME,
        "store_jsonl": STORE_JSONL_NAME,
        "planned_calls_within_budget": PLANNED_CALLS <= CALL_BUDGET_TOTAL,
        "results_prefix_is_not_round3": not RESULTS_PREFIX.startswith(
            "block15_round3_results_"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(
        description="Ceiling study: schema order then num_predict (local Ollama only)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="print the frozen task, schema and condition manifest; no calls",
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="verify frozen hashes, SymPy truth and copy guard; no calls",
    )
    parser.add_argument(
        "--condition",
        choices=sorted(CONDITIONS),
        help="run one pre-registered condition; one call per task",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="apply the pre-registered criteria; no calls",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        help="optional path for the summarize JSON",
    )
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="read-only internal consistency check; no calls",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        print(json.dumps(_manifest(), ensure_ascii=True, indent=2))
        return 0
    if args.selfcheck:
        result = selfcheck()
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["ok"] else 1
    if args.summarize:
        result = summarize()
        text = json.dumps(result, ensure_ascii=True, indent=2)
        if args.summary_out is not None:
            args.summary_out.write_text(text, encoding="utf-8")
        print(text)
        return 0
    if args.recheck:
        result = recheck()
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["ok"] else 1
    if args.condition:
        run_phase(args.condition)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
