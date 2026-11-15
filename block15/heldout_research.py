"""Held-out bounded-math study with one-axis interventions.

The study is deliberately narrow:

* five fresh bounded-math tasks, independent of the Round 3 prompts;
* SymPy-computed ground truth, verified against frozen expected values;
* a strict answer-field audit that never changes the stored raw output;
* four conditions (baseline plus three one-axis interventions);
* one model call per task and condition, no retries or repairs;
* hard cumulative call, runtime and free-memory guards.

No existing Round 3/4, QAD, memory or ``mdl`` logic is modified.  The new
stores and result files use a dedicated ``block15_heldout_*`` prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
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
BASE_TEMPERATURE = 0.1

CALL_BUDGET_TOTAL = 80
RUNTIME_BUDGET_TOTAL_S = 3600.0
PHASE_RUNTIME_S = 900.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 20

STORE_DB_NAME = "block15_heldout.sqlite3"
STORE_JSONL_NAME = "block15_heldout_events.jsonl"
RESULTS_PREFIX = "block15_heldout_results_"

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
        id="H1_coeff_2x_minus_3_pow7",
        kind="coefficient",
        question=(
            "Expand (2x - 3)^7 and report the coefficient of x^5. "
            "Give the exact integer coefficient."
        ),
        expected_display="6048",
        expression="(2*x - 3)**7",
        power=5,
        expected_coefficient=6048,
    ),
    _task(
        id="H2_coeff_4_minus_x_pow8",
        kind="coefficient",
        question=(
            "Expand (4 - x)^8 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-57344",
        expression="(4 - x)**8",
        power=3,
        expected_coefficient=-57344,
    ),
    _task(
        id="H3_coeff_x_plus_5_pow9",
        kind="coefficient",
        question=(
            "Expand (x + 5)^9 and report the coefficient of x^6. "
            "Give the exact integer coefficient."
        ),
        expected_display="10500",
        expression="(x + 5)**9",
        power=6,
        expected_coefficient=10500,
    ),
    _task(
        id="H4_minimal_n2_plus_n_plus_1301",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + n + 1301. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1313 = 13 * 101",
        a=1,
        b=1,
        c=1301,
        expected_n=3,
        expected_value=1313,
        expected_primes=(13, 101),
    ),
    _task(
        id="H5_minimal_2n2_plus_2n_plus_1279",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 2n + 1279. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 5, f(n) = 1339 = 13 * 103",
        a=2,
        b=2,
        c=1279,
        expected_n=5,
        expected_value=1339,
        expected_primes=(13, 103),
    ),
)


# ---------------------------------------------------------------------------
# Frozen schemas and one-axis conditions
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
    axis: str
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
    "baseline": Condition(
        key="baseline",
        axis="reference",
        baseline_value="-",
        intervention_value="-",
        schema_order="answer_first",
        num_predict=BASE_NUM_PREDICT,
        temperature=BASE_TEMPERATURE,
    ),
    "schema": Condition(
        key="schema",
        axis="schema field order",
        baseline_value="answer, derivation, confidence, uncertainty",
        intervention_value="derivation, answer, confidence, uncertainty",
        schema_order="derivation_first",
        num_predict=BASE_NUM_PREDICT,
        temperature=BASE_TEMPERATURE,
    ),
    "numpredict": Condition(
        key="numpredict",
        axis="num_predict",
        baseline_value=str(BASE_NUM_PREDICT),
        intervention_value="2400",
        schema_order="answer_first",
        num_predict=2400,
        temperature=BASE_TEMPERATURE,
    ),
    "temperature": Condition(
        key="temperature",
        axis="temperature",
        baseline_value=str(BASE_TEMPERATURE),
        intervention_value="0.0",
        schema_order="answer_first",
        num_predict=BASE_NUM_PREDICT,
        temperature=0.0,
    ),
}

# Populated from the manifest, then re-verified before every run.  The study
# refuses to start if the prompts, schemas or SymPy ground truth drift.
FROZEN_PROMPT_SHA256: dict[str, str] = {
    "H1_coeff_2x_minus_3_pow7": (
        "a75ddc7ceac90289989f90cbbf4d931581e576b83d1fd6631ef49b950250bf4e"
    ),
    "H2_coeff_4_minus_x_pow8": (
        "b3379468517e0c89f7500338bf9e78a965057b30c1eb1b1583df454b6b6de797"
    ),
    "H3_coeff_x_plus_5_pow9": (
        "20408f2a45b306a26f6714eb6b38004bcf90ac8d6361791612b7f067ad012fb9"
    ),
    "H4_minimal_n2_plus_n_plus_1301": (
        "14fa8c1b7ff1e704e3b2ca6b41acee834f003688721bc6f3a9b98186fff1797b"
    ),
    "H5_minimal_2n2_plus_2n_plus_1279": (
        "b33479d9bf5ff743c1cf4ba7db913194cd1a8dad38b014a94d63b4abc289f9d8"
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
    "211f37c5fa9c73fa662608aab2380c2aea99f5bd86552c2578b1d62ca0734646"
)


# ---------------------------------------------------------------------------
# Hashing, extraction and independent SymPy audit
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
    """Extract distinct standalone integers from the answer field.

    Thousands separators are removed first.  A decimal such as ``6048.0`` is
    not split into two integers.  The result is sorted for deterministic
    storage.
    """

    normalized = text.replace("\u2212", "-").replace("\u2013", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    return sorted({int(match.group(0)) for match in _INT_RE.finditer(normalized)})


def _is_composite(value: int) -> bool:
    return value > 1 and not sympy.isprime(value)


def ground_truth(task: HeldoutTask) -> dict:
    """Compute and verify the task's ground truth from SymPy directly."""

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
        raise SystemExit(
            f"minimality task {task.id} is not squarefree: {factor}"
        )
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
    """Strict answer-field audit, independent of the frozen expected values.

    Coefficient tasks: the answer field must resolve to exactly one distinct
    integer, equal to the SymPy coefficient.

    Minimality tasks: the set of distinct integers in the answer field must be
    exactly ``{n, f(n), p1, ..., pk}``, and SymPy must independently verify the
    squarefree factorization of ``f(n)``.
    """

    values = extract_answer_ints(answer_text)
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

    No memory or previous attempt is ever injected in this study, so this
    check is the complete copy surface.  All held-out prompts are constructed
    to avoid the expected tokens; the result is recorded per task anyway.
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
# Frozen-manifest and protected-artifact checks
# ---------------------------------------------------------------------------


def _manifest() -> dict:
    truth = ground_truth_manifest()
    return {
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "quantization": QUANTIZATION,
        "tasks": [
            {
                **task.metadata(),
                "ground_truth": truth[task.id],
            }
            for task in TASKS
        ],
        "ground_truth_manifest_sha256": _sha256_json(truth),
        "schemas": {
            "answer_first": {
                "sha256": _sha256_json(
                    ANSWER_FIRST_SCHEMA, sort_keys=False
                ),
                "schema": ANSWER_FIRST_SCHEMA,
            },
            "derivation_first": {
                "sha256": _sha256_json(
                    DERIVATION_FIRST_SCHEMA, sort_keys=False
                ),
                "schema": DERIVATION_FIRST_SCHEMA,
            },
        },
        "conditions": [condition.metadata() for condition in CONDITIONS.values()],
        "planned_calls": PLANNED_CALLS,
        "guards": {
            "call_budget_total": CALL_BUDGET_TOTAL,
            "runtime_budget_total_s": RUNTIME_BUDGET_TOTAL_S,
            "phase_runtime_s": PHASE_RUNTIME_S,
            "min_free_mb": MIN_FREE_MB,
        },
    }


def _verify_frozen() -> dict[str, str]:
    computed_prompts = {
        task.id: _sha256_text(task.prompt) for task in TASKS
    }
    computed_schemas = {
        "answer_first": _sha256_json(
            ANSWER_FIRST_SCHEMA, sort_keys=False
        ),
        "derivation_first": _sha256_json(
            DERIVATION_FIRST_SCHEMA, sort_keys=False
        ),
    }
    computed_truth = _sha256_json(ground_truth_manifest())
    if computed_prompts != FROZEN_PROMPT_SHA256:
        raise SystemExit(
            "frozen prompt hashes are not populated or do not match; "
            "run --manifest and update FROZEN_PROMPT_SHA256"
        )
    if computed_schemas != FROZEN_SCHEMA_SHA256:
        raise SystemExit(
            "frozen schema hashes do not match; "
            "run --manifest and update FROZEN_SCHEMA_SHA256"
        )
    if computed_truth != FROZEN_GROUND_TRUTH_SHA256:
        raise SystemExit(
            "frozen ground-truth manifest hash does not match; "
            "run --manifest and update FROZEN_GROUND_TRUTH_SHA256"
        )
    return {
        "prompts": computed_prompts,
        "schemas": computed_schemas,
        "ground_truth_manifest": computed_truth,
    }


_PROTECTED_PATHS: tuple[str, ...] = (
    "data/block15_round3.sqlite3",
    "data/block15_round3_events.jsonl",
    "data/block15_round3_ground_truth.json",
    "data/block15_round3_assessments.json",
    "data/block15_round3_results_round3_20261111T143825Z.json",
    "BLOCK15_ROUND3_REPORT.md",
    "data/block15_round4_arm_a.sqlite3",
    "data/block15_round4_arm_a_events.jsonl",
    "data/block15_round4_arm_b.sqlite3",
    "data/block15_round4_arm_b_events.jsonl",
    "data/block15_round4_arm_a_results_round3_20261114T215552Z.json",
    "data/block15_round4_arm_b_results_round3_20261114T220133Z.json",
    "PREREG_QAD.md",
    "REPORT_QAD.md",
    "PREREG_MEMORY.md",
    "REPORT_MEMORY.md",
    "block15/round3.py",
    "block15/round3_tasks.py",
    "block15/round3_report.py",
)


def _protected_hashes() -> dict[str, str | None]:
    root = DATA_DIR.parent
    names = list(_PROTECTED_PATHS)
    names.extend(
        str(path.relative_to(root))
        for path in sorted((root / "mdl").glob("*.py"))
    )
    return {name: _sha256_file(root / name) for name in names}


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


class HeldoutRunner:
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
        if final is not None:
            audit = audit_answer(task, truth, final["answer"])
        else:
            audit = {
                "method": "not_run",
                "audit_passed": False,
                "note": "attempt produced no validated final",
            }
        copied = copy_possible(task, truth)
        row = {
            "call_index": call_index,
            "task_id": task.id,
            "task_kind": task.kind,
            "condition": self.condition.key,
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
            "done_reason": done_reason,
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
            "confidence": final["confidence"] if final is not None else None,
            "final": final,
            "answer_text": final["answer"] if final is not None else None,
            "derivation_text": (
                final["derivation"] if final is not None else None
            ),
            "audit": audit,
            "audit_passed": bool(audit["audit_passed"]),
            "copy": copied,
            "copy_possible": bool(copied["copy_possible"]),
            "latency_ms": round(latency_ms, 2),
        }
        self.store.log_step(
            self.experiment_id,
            "heldout_attempt",
            status,
            row,
            latency_ms=latency_ms,
        )
        print(
            f"    task={task.id:<42} status={status:<12} "
            f"audit={row['audit_passed']} "
            f"copy={row['copy_possible']} "
            f"confidence={row['confidence']} eval={eval_count} "
            f"done={done_reason} latency_s={latency_ms / 1000:.1f}",
            flush=True,
        )
        return row


def _phase_paths(condition_key: str, ts: str) -> Path:
    return DATA_DIR / f"{RESULTS_PREFIX}{condition_key}_{ts}.json"


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

    frozen = _verify_frozen()
    truth_manifest = ground_truth_manifest()
    prior = _prior_totals()
    if int(prior["calls"]) + 5 > CALL_BUDGET_TOTAL:
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
        "run_id": f"heldout_{condition.key}_{ts}",
        "kind": "heldout_bounded_math",
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
                "round": "heldout_bounded_math",
                "condition": condition.key,
                "axis": condition.axis,
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
        runner = HeldoutRunner(
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
            "heldout_phase_started",
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
        summary = {
            "condition": condition.key,
            "completed_tasks": len(rows),
            "audit_passes": sum(1 for row in rows if row["audit_passed"]),
            "copy_possible_passes": sum(
                1
                for row in rows
                if row["audit_passed"] and row["copy_possible"]
            ),
            "tasks": {
                row["task_id"]: {
                    "audit_passed": row["audit_passed"],
                    "copy_possible": row["copy_possible"],
                    "status": row["status"],
                    "done_reason": row["done_reason"],
                }
                for row in rows
            },
        }
        record["summary"] = summary
        store.set_experiment_fields(
            experiment_id,
            hypothesis_json={
                "condition": condition.key,
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
        record["protected_artifacts_unchanged"] = (
            record["protected_artifacts_sha256_start"]
            == record["protected_artifacts_sha256_end"]
        )
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
# Read-only summarizer
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


def _row_view(row: dict) -> dict:
    return {
        "task_id": row["task_id"],
        "audit_passed": row["audit_passed"],
        "copy_possible": row["copy_possible"],
        "answer_text": row["answer_text"],
        "derivation_text": row["derivation_text"],
        "audit": row["audit"],
        "confidence": row["confidence"],
        "eval_count": row["eval_count"],
        "prompt_eval_count": row["prompt_eval_count"],
        "done_reason": row["done_reason"],
        "status": row["status"],
        "error": row["error"],
        "raw_content_sha256": row["raw_content_sha256"],
        "latency_ms": row["latency_ms"],
    }


def summarize() -> dict:
    records = _load_phase_records()
    baseline = records.get("baseline")
    baseline_rows = (
        {row["task_id"]: row for row in baseline["results"]}
        if baseline is not None
        else {}
    )
    baseline_fail_tasks = [
        task.id
        for task in TASKS
        if task.id in baseline_rows
        and not baseline_rows[task.id]["audit_passed"]
    ]
    missing_baseline = [
        task.id for task in TASKS if task.id not in baseline_rows
    ]

    condition_summaries: dict[str, dict] = {}
    for condition_key in ("schema", "numpredict", "temperature"):
        record = records.get(condition_key)
        if record is None:
            condition_summaries[condition_key] = {
                "present": False,
                "survives": False,
                "passes_on_baseline_failures": [],
                "descriptive_passes_on_baseline_passes": [],
            }
            continue
        rows = {row["task_id"]: row for row in record["results"]}
        passes = [
            task_id
            for task_id in baseline_fail_tasks
            if task_id in rows
            and rows[task_id]["audit_passed"]
            and not rows[task_id]["copy_possible"]
        ]
        descriptive = [
            task_id
            for task_id in TASKS
            if task_id in rows
            and task_id not in baseline_fail_tasks
            and rows[task_id]["audit_passed"]
            and not rows[task_id]["copy_possible"]
        ]
        condition_summaries[condition_key] = {
            "present": True,
            "axis": record["condition_definition"]["axis"],
            "baseline_value": record["condition_definition"][
                "baseline_value"
            ],
            "intervention_value": record["condition_definition"][
                "intervention_value"
            ],
            "completed_tasks": len(record["results"]),
            "stopped_early": record["stopped_early"],
            "calls_used_total": record["calls_used_total"],
            "runtime_s_total": record["runtime_s_total"],
            "passes_on_baseline_failures": passes,
            "descriptive_passes_on_baseline_passes": descriptive,
            "survives": bool(passes),
            "rows": {
                task_id: _row_view(row) for task_id, row in rows.items()
            },
        }

    any_survives = any(
        item["survives"] for item in condition_summaries.values()
    )
    artifact_hashes = {
        "results": {
            name: _sha256_file(DATA_DIR / name)
            for name in sorted(
                record["_path"] for record in records.values()
            )
        },
        "store_db": _sha256_file(DATA_DIR / STORE_DB_NAME),
        "store_jsonl": _sha256_file(DATA_DIR / STORE_JSONL_NAME),
        "module": _sha256_file(Path(__file__)),
        "prereg": {
            name: _sha256_file(DATA_DIR.parent / name)
            for name in (
                "PREREG_HELDOUT_BASELINE.md",
                "PREREG_HELDOUT_SCHEMA.md",
                "PREREG_HELDOUT_NUMPREDICT.md",
                "PREREG_HELDOUT_TEMPERATURE.md",
            )
        },
    }
    return {
        "baseline_present": baseline is not None,
        "baseline_missing_tasks": missing_baseline,
        "baseline_fail_tasks": baseline_fail_tasks,
        "baseline_rows": {
            task_id: _row_view(row) for task_id, row in baseline_rows.items()
        },
        "conditions": condition_summaries,
        "overall_noncopy_audit_pass_on_baseline_failure": bool(any_survives),
        "verdict": "SIGNAL" if any_survives else "NO SIGNAL",
        "artifact_hashes": artifact_hashes,
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


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(
        description="Held-out bounded-math study (local Ollama only)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="print the frozen task, schema and condition manifest; no calls",
    )
    parser.add_argument(
        "--condition",
        choices=sorted(CONDITIONS),
        help="run one pre-registered condition; one call per task",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="read results and apply the pre-registered criterion; no calls",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        print(json.dumps(_manifest(), ensure_ascii=True, indent=2))
        return 0
    if args.summarize:
        print(json.dumps(summarize(), ensure_ascii=True, indent=2))
        return 0
    if args.condition:
        run_phase(args.condition)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
