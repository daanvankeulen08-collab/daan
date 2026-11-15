"""Memory-retry pilot for two frozen Round 3 tasks.

This module is deliberately narrow and self-contained:

* a deterministic, model-free compressor with levels ``N, 0, 1, 2, 3, 4``;
* a fixed ``k = 3`` retry loop (the first attempt is shared by all six
  conditions, so a task costs 13 calls in total);
* per-attempt logging of the raw model output and generation metadata;
* a binary reward fixed before generation;
* a stricter, independent audit that is stored separately and never
  overwrites the binary reward.

Only the frozen Round 3 task text, schemas, validators and pure helpers are
reused.  ``block15.round3.independent_check`` and every other existing
function are imported read-only and never modified here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.round2 import _validate_experimental
from block15.round3 import (
    _answer_text,
    _derivation_text,
    _number_present,
    independent_check,
)
from block15.round3_tasks import (
    ANSWER_SCHEMA,
    EXPERIMENTAL_SCHEMA,
    RUN_ORDER,
    SYSTEM_PROMPT,
    Round3Task,
)
from block15.run_benchmark import (
    DATA_DIR,
    _now,
    _validate_answer,
    free_physical_mb,
)
from mdl.config import Settings, load_settings
from mdl.errors import ModelOutputError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import ModelResponse, OllamaClient

A1A_TASK_ID = "R3A1_coefficient_protocol_A"
C_TASK_ID = "R3C_hypothesis_falsification"
TASK_IDS: tuple[str, ...] = (A1A_TASK_ID, C_TASK_ID)

CONDITION_N = "N"
CONDITIONS: tuple[str, ...] = ("N", "0", "1", "2", "3", "4")
RETRY_LEVELS: tuple[str, ...] = ("0", "1", "2", "3", "4")
MEMORY_LEVELS: tuple[str, ...] = ("1", "2", "3", "4")

ATTEMPTS_PER_CONDITION = 3
PLANNED_CALLS = len(TASK_IDS) * (1 + len(CONDITIONS) * 2)
CALL_BUDGET = 30
HARD_RUNTIME_S = 2400.0
MIN_FREE_MB = 450.0
NUM_PREDICT = 1200

MODEL = "lfm3base:latest"
MODEL_DIGEST = "b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d"
GROUND_TRUTH_PATH = DATA_DIR / "block15_round3_ground_truth.json"
GROUND_TRUTH_SHA256 = (
    "4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd"
)
GROUND_TRUTH_TOKENS = {A1A_TASK_ID: 4860, C_TASK_ID: 1333}

NO_MEMORY_LABEL = "Your previous attempt was judged incorrect."
NO_INFORMATION = (
    "Your previous attempt was judged incorrect. "
    "No further information is available."
)
BLOCK_OPEN = "<previous_attempt>"
BLOCK_CLOSE = "</previous_attempt>"
RETRY_INSTRUCTION = "Attempt the task again."

SUCCESS_CRITERION = (
    "Signal exists iff at least one compression level yields a C composite "
    "pass with audit_passed=true while condition N fails all 3 attempts."
)

# The only files this pilot may write.  None of them collides with a Round 3
# results file name or with an existing Round 3/4 artifact.
STORE_DB_NAME = "block15_pilot_memory.sqlite3"
STORE_JSONL_NAME = "block15_pilot_memory_events.jsonl"
RESULTS_PREFIX = "block15_pilot_memory_results_"


# ---------------------------------------------------------------------------
# Deterministic compressor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemorySource:
    """The three pieces of a previous response the compressor may use."""

    final: str
    derivation: str
    raw_content: str


def memory_source(response: ModelResponse) -> MemorySource:
    """Build a compressor source from a parsed model response."""

    return MemorySource(
        final=_answer_text(response.parsed),
        derivation=_derivation_text(response.parsed),
        raw_content=response.content,
    )


def compress_memory(level: str, source: MemorySource | None) -> str:
    """Return the deterministic memory string for one compression level.

    ``N`` and ``0`` carry no memory block and therefore return ``""``.
    Levels ``1``-``4`` return the previous answer, its tail, the full
    derivation, or the previous raw content, respectively.
    """

    if level not in CONDITIONS:
        raise ValueError(f"unknown compression level: {level!r}")
    if level in {CONDITION_N, "0"}:
        return ""
    if source is None:
        return ""
    if level == "1":
        return source.final
    if level == "2":
        return source.final + "\n" + source.derivation[-200:]
    if level == "3":
        return source.final + "\n" + source.derivation
    return source.raw_content


def build_retry_prompt(task_prompt: str, level: str, memory: str) -> str:
    """Append the fixed injection block to the original task prompt.

    Level ``N`` appends nothing, so its prompt is byte-identical to the first
    attempt.  Level ``0`` appends only the label sentence.  Levels ``1``-``4``
    append the identical wrapper around ``memory``.
    """

    if level not in CONDITIONS:
        raise ValueError(f"unknown compression level: {level!r}")
    if level == CONDITION_N:
        return task_prompt
    if level == "0":
        return task_prompt + "\n\n" + NO_MEMORY_LABEL
    block = (
        NO_INFORMATION
        + "\n"
        + BLOCK_OPEN
        + "\n"
        + memory
        + "\n"
        + BLOCK_CLOSE
        + "\n"
        + RETRY_INSTRUCTION
    )
    return task_prompt + "\n\n" + block


def answer_present_in_memory(level: str, memory: str, token: int) -> bool:
    """Whether the exact ground-truth integer occurs in the injected memory.

    Only levels ``1``-``4`` inject memory; ``N`` and ``0`` never do.  The
    check uses the existing ``_number_present`` helper so that e.g. ``13330``
    is not mistaken for ``1333``.
    """

    if level not in MEMORY_LEVELS:
        return False
    return _number_present(memory, token)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Pre-registered scoring
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"(?<![\d.])-?\d+(?!\d|\.\d)")


def extract_answer_ints(text: str) -> list[int]:
    """Extract standalone integers from the answer field.

    Thousands separators are removed first.  A decimal such as ``4860.0`` is
    not split into two integers.
    """

    normalized = text.replace("\u2212", "-").replace("\u2013", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    return [int(match.group(0)) for match in _INT_RE.finditer(normalized)]


def strict_audit_a1a(final: dict) -> dict:
    """Stricter A1A audit: the answer field must resolve to one integer.

    The single distinct integer extracted from the answer field must equal the
    independently computed coefficient exactly.  Prose is allowed; ambiguity
    (more than one distinct integer) fails the audit.
    """

    x = sympy.Symbol("x")
    expected = int(sympy.expand((3 * x - 2) ** 6).coeff(x, 4))
    values = sorted(set(extract_answer_ints(_answer_text(final))))
    return {
        "expected_coefficient": expected,
        "extracted_answer_ints": values,
        "unique_value_equals_expected": values == [expected],
        "audit_passed": values == [expected],
    }


def strict_audit_c(final: dict) -> dict:
    """Stricter C audit: all four facts in the answer, factorization verified."""

    text = _answer_text(final)
    present = {
        str(value): _number_present(text, value)
        for value in (7, 1333, 31, 43)
    }
    factorization = sympy.factorint(1333)
    product_ok = int(sympy.Integer(31) * sympy.Integer(43)) == 1333
    factorization_ok = factorization == {31: 1, 43: 1} and product_ok
    return {
        "answer_contains": present,
        "factorint_1333": {str(k): int(v) for k, v in factorization.items()},
        "product_31_43_verified": bool(product_ok),
        "sympy_factorization_verified": bool(factorization_ok),
        "audit_passed": all(present.values()) and factorization_ok,
    }


def score_attempt(task: Round3Task, final: dict, verification: dict) -> dict:
    """Return binary reward, stored status and the stricter audit.

    A1A reward: the stored ``independent_check`` status is
    ``objective_pass``.
    C reward: the new pre-registered composite over the stored flags.  The
    stored status (always ``manual_review_required`` for C) is reported but is
    not the reward.
    """

    if task.id == A1A_TASK_ID:
        reward = verification.get("status") == "objective_pass"
        composite = None
        audit = strict_audit_a1a(final)
    elif task.id == C_TASK_ID:
        composite = {
            "final_contains_first_n": bool(
                verification.get("final_contains_first_n")
            ),
            "final_contains_counterexample_value": bool(
                verification.get("final_contains_counterexample_value")
            ),
            "final_contains_factors_31_43": bool(
                verification.get("final_contains_factors_31_43")
            ),
        }
        reward = all(composite.values())
        audit = strict_audit_c(final)
    else:
        raise ValueError(f"pilot is not registered for task {task.id!r}")

    return {
        "binary_reward": bool(reward),
        "stored_status": verification.get("status"),
        "composite": composite,
        "audit": audit,
        "audit_passed": bool(audit["audit_passed"]),
    }


def evaluate_success_criterion(task_results: dict[str, dict]) -> dict:
    """Apply the pre-registered C success criterion.

    Levels 1-4 are the compression levels.  Level 0 (label only) and N (no
    injection) are controls and cannot create the signal.  A sensitivity
    reading that also counts level 0 is reported without changing the verdict.
    """

    c_result = task_results[C_TASK_ID]
    n_condition = c_result["conditions"][CONDITION_N]
    n_rewards = list(n_condition["rewards"])
    n_fails_all = n_rewards == [False, False, False]
    passing_levels = [
        level
        for level in MEMORY_LEVELS
        if c_result["conditions"][level]["audit_success_at_3"]
    ]
    level_zero_passes = bool(
        c_result["conditions"]["0"]["audit_success_at_3"]
    )
    return {
        "criterion": SUCCESS_CRITERION,
        "condition_N_rewards": n_rewards,
        "condition_N_fails_all_3": n_fails_all,
        "compression_levels_with_composite_and_audit": passing_levels,
        "signal": bool(n_fails_all and passing_levels),
        "sensitivity_level_0_composite_and_audit": level_zero_passes,
        "sensitivity_signal_including_level_0": bool(
            n_fails_all and (passing_levels or level_zero_passes)
        ),
        "scope_note": (
            "Primary verdict counts levels 1-4 only; level 0 and N are "
            "controls. The level-0 sensitivity is reported separately."
        ),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class PilotGuardStop(RuntimeError):
    """A hard pre-registered guard (calls, runtime or memory) stopped the run."""


@dataclass(frozen=True)
class PilotPaths:
    db: Path
    jsonl: Path
    results: Path


def _select_tasks() -> list[Round3Task]:
    by_id = {task.id: task for task in RUN_ORDER}
    missing = [task_id for task_id in TASK_IDS if task_id not in by_id]
    if missing:
        raise SystemExit(f"frozen Round 3 tasks are missing: {missing}")
    return [by_id[task_id] for task_id in TASK_IDS]


def _schema_for(task: Round3Task) -> dict:
    return (
        ANSWER_SCHEMA
        if task.protocol == "A_round1_answer_reasoning"
        else EXPERIMENTAL_SCHEMA
    )


def _validator_for(task: Round3Task):
    if task.protocol == "A_round1_answer_reasoning":
        return _validate_answer
    return _validate_experimental


def _report_view(record: dict, condition: str) -> dict:
    """Copy only report-facing fields for a duplicated shared attempt."""

    return {
        "attempt": record["attempt"],
        "condition": condition,
        "shared_call": True,
        "status": record["status"],
        "binary_reward": record["binary_reward"],
        "audit_passed": record["audit_passed"],
        "answer_present_in_memory": record["answer_present_in_memory"],
        "copy_possible": record["copy_possible"],
        "confidence": record["confidence"],
        "prompt_eval_count": record["prompt_eval_count"],
        "eval_count": record["eval_count"],
        "done_reason": record["done_reason"],
        "latency_ms": record["latency_ms"],
        "stored_status": record["stored_status"],
        "raw_content_ref": "shared_attempt_1",
    }


class MemoryPilotRunner:
    def __init__(
        self,
        settings: Settings,
        client: OllamaClient,
        store: ResearchStore,
        digest: str,
        model_info: dict,
        run_id: str,
    ) -> None:
        self.settings = settings
        self.client = client
        self.store = store
        self.digest = digest
        self.model_info = model_info
        self.run_id = run_id
        self.run_started = perf_counter()
        self.calls_used = 0

    @property
    def elapsed_s(self) -> float:
        return perf_counter() - self.run_started

    def _guard(self) -> None:
        if self.calls_used >= CALL_BUDGET:
            raise PilotGuardStop(f"hard model-call limit {CALL_BUDGET} reached")
        if self.elapsed_s >= HARD_RUNTIME_S:
            raise PilotGuardStop(
                f"hard runtime limit {HARD_RUNTIME_S:.0f}s reached"
            )
        free_mb = free_physical_mb()
        if free_mb is not None and free_mb < MIN_FREE_MB:
            raise PilotGuardStop(
                f"free physical memory {free_mb:.1f} MB below {MIN_FREE_MB:.0f} MB"
            )

    def _attempt(
        self,
        task: Round3Task,
        experiment_id: str,
        condition: str,
        attempt: int,
        prompt: str,
        memory: str | None,
        memory_sha: str | None,
        memory_token_present: bool,
        *,
        shared: bool,
    ) -> dict:
        self._guard()
        self.calls_used += 1
        call_index = self.calls_used
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        schema = _schema_for(task)
        validate = _validator_for(task)
        started = perf_counter()
        response: ModelResponse | None = None
        raw_content: str | None = None
        done_reason: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None
        final: dict | None = None
        verification: dict | None = None
        error: str | None = None
        status = "failed"

        try:
            response = self.client.chat_json(
                messages, schema, num_predict=NUM_PREDICT
            )
            raw_content = response.content
            done_reason = response.done_reason
            prompt_eval_count = response.prompt_eval_count
            eval_count = response.eval_count
            try:
                final = validate(response.parsed)
            except Exception as exc:  # noqa: BLE001 - invalid output is recorded
                error = f"{type(exc).__name__}: {exc}"
            else:
                verification = independent_check(task, final, None)
                status = "truncated" if done_reason == "length" else "ok"
        except ModelOutputError as exc:
            raw_content = exc.raw_content
            done_reason = exc.done_reason
            prompt_eval_count = exc.prompt_eval_count
            eval_count = exc.eval_count
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001 - transport/guard failures recorded
            error = f"{type(exc).__name__}: {exc}"

        latency_ms = (perf_counter() - started) * 1000.0
        confidence = final.get("confidence") if final is not None else None
        scored = (
            score_attempt(task, final, verification)
            if final is not None and verification is not None
            else {
                "binary_reward": False,
                "stored_status": None,
                "composite": None,
                "audit": {
                    "audit_passed": False,
                    "note": "attempt produced no validated final",
                },
                "audit_passed": False,
            }
        )
        copy_possible = bool(
            scored["binary_reward"] and memory_token_present
        )
        record = {
            "call_index": call_index,
            "task_id": task.id,
            "condition": condition,
            "attempt": attempt,
            "shared_call": shared,
            "level": condition if not shared else None,
            "prompt_sha256": _sha256_text(prompt),
            "prompt_characters": len(prompt),
            "expected_prompt_sha256": (
                _sha256_text(task.prompt) if condition == CONDITION_N else None
            ),
            "injected_memory": memory,
            "injected_memory_sha256": memory_sha,
            "injected_memory_characters": (
                len(memory) if memory is not None else 0
            ),
            "answer_present_in_memory": bool(memory_token_present),
            "raw_content": raw_content,
            "done_reason": done_reason,
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
            "confidence": confidence,
            "latency_ms": round(latency_ms, 2),
            "status": status,
            "error": error,
            "final": final,
            "verification": verification,
            "binary_reward": scored["binary_reward"],
            "stored_status": scored["stored_status"],
            "composite": scored["composite"],
            "audit": scored["audit"],
            "audit_passed": scored["audit_passed"],
            "copy_possible": copy_possible,
        }
        self.store.log_step(
            experiment_id,
            "pilot_attempt",
            status,
            record,
            latency_ms=latency_ms,
        )
        print(
            f"    condition={condition:<4} attempt={attempt} "
            f"status={status} reward={record['binary_reward']} "
            f"audit={record['audit_passed']} "
            f"copy_possible={copy_possible} "
            f"confidence={confidence} eval={eval_count} "
            f"done={done_reason} latency_s={latency_ms / 1000:.1f}",
            flush=True,
        )
        return record

    @staticmethod
    def _source_from_record(record: dict) -> MemorySource | None:
        if record["final"] is not None:
            return MemorySource(
                final=_answer_text(record["final"]),
                derivation=_derivation_text(record["final"]),
                raw_content=record["raw_content"] or "",
            )
        if record["raw_content"]:
            return MemorySource(
                final="", derivation="", raw_content=record["raw_content"]
            )
        return None

    def run_task(self, task: Round3Task) -> dict:
        token = GROUND_TRUTH_TOKENS[task.id]
        experiment_id = self.store.create_experiment(
            seed=task.id,
            model=self.settings.model,
            model_digest=self.digest,
            parameters={
                "run_id": self.run_id,
                "round": "memory_pilot",
                "task_id": task.id,
                "protocol": task.protocol,
                "mode": task.mode,
                "conditions": list(CONDITIONS),
                "attempts_per_condition": ATTEMPTS_PER_CONDITION,
                "num_ctx": self.settings.context_limit,
                "num_predict": NUM_PREDICT,
                "temperature": self.settings.temperature,
                "top_p": self.settings.top_p,
                "repeat_penalty": self.settings.repeat_penalty,
                "seed": self.settings.seed,
                "think": self.settings.think,
                "keep_alive": self.settings.keep_alive,
            },
            context_limit=self.settings.context_limit,
        )
        self.store.log_event(
            experiment_id,
            "memory_pilot_task_started",
            {"task": task.metadata(), "started_at": _now()},
        )

        print(f"[task] {task.id} calls_used={self.calls_used}", flush=True)
        shared = self._attempt(
            task,
            experiment_id,
            condition="shared",
            attempt=1,
            prompt=task.prompt,
            memory=None,
            memory_sha=None,
            memory_token_present=False,
            shared=True,
        )

        conditions: dict[str, dict] = {}
        for condition in CONDITIONS:
            retries: list[dict] = []
            last_validated = self._source_from_record(shared)
            immediate = self._source_from_record(shared)
            for attempt in (2, 3):
                if condition == CONDITION_N:
                    memory = ""
                    memory_sha = None
                    present = False
                    prompt = build_retry_prompt(task.prompt, condition, memory)
                elif condition == "0":
                    memory = ""
                    memory_sha = None
                    present = False
                    prompt = build_retry_prompt(task.prompt, condition, memory)
                else:
                    if condition == "4":
                        source = immediate or last_validated
                    else:
                        source = last_validated
                    memory = compress_memory(condition, source)
                    memory_sha = _sha256_text(memory)
                    present = answer_present_in_memory(
                        condition, memory, token
                    )
                    prompt = build_retry_prompt(task.prompt, condition, memory)
                record = self._attempt(
                    task,
                    experiment_id,
                    condition=condition,
                    attempt=attempt,
                    prompt=prompt,
                    memory=memory if condition in MEMORY_LEVELS else None,
                    memory_sha=memory_sha,
                    memory_token_present=present,
                    shared=False,
                )
                retries.append(record)
                immediate = self._source_from_record(record)
                if record["final"] is not None:
                    last_validated = self._source_from_record(record)

            attempts = [_report_view(shared, condition)] + retries
            rewards = [item["binary_reward"] for item in attempts]
            combined = [
                bool(item["binary_reward"] and item["audit_passed"])
                for item in attempts
            ]
            conditions[condition] = {
                "level": condition,
                "attempts": attempts,
                "rewards": rewards,
                "success_at_3": any(rewards),
                "audit_passes": sum(
                    1 for item in attempts if item["audit_passed"]
                ),
                "audit_success_at_3": any(combined),
                "copy_possible_passes": sum(
                    1 for item in attempts if item["copy_possible"]
                ),
            }

        n_identity = [shared["prompt_sha256"]] + [
            item["prompt_sha256"]
            for item in conditions[CONDITION_N]["attempts"]
            if not item.get("shared_call")
        ]
        identity = {
            "prompt_sha256": n_identity,
            "expected_prompt_sha256": _sha256_text(task.prompt),
            "byte_identical": len(set(n_identity)) == 1
            and n_identity[0] == _sha256_text(task.prompt),
        }

        result = {
            "task_id": task.id,
            "task_metadata": task.metadata(),
            "experiment_id": experiment_id,
            "ground_truth_token": token,
            "shared_attempt_1": shared,
            "conditions": conditions,
            "condition_n_prompt_byte_identity": identity,
        }
        summary = {
            "task_id": task.id,
            "success_at_3": {
                condition: conditions[condition]["success_at_3"]
                for condition in CONDITIONS
            },
            "audit_success_at_3": {
                condition: conditions[condition]["audit_success_at_3"]
                for condition in CONDITIONS
            },
            "condition_n_byte_identical": identity["byte_identical"],
        }
        self.store.set_experiment_fields(
            experiment_id,
            hypothesis_json=task.metadata(),
            interpretation_json=result,
            verification_json=summary,
            context_json={
                "run_id": self.run_id,
                "task_id": task.id,
                "conditions": list(CONDITIONS),
                "attempts_per_condition": ATTEMPTS_PER_CONDITION,
                "shared_attempt_1": True,
            },
        )
        self.store.finish_experiment(
            experiment_id,
            "completed",
            latency_ms=round(self.elapsed_s * 1000.0, 2),
            token_usage={
                "prompt_eval_count": sum(
                    int(item["prompt_eval_count"] or 0)
                    for item in [shared] + [
                        r
                        for condition in CONDITIONS
                        for r in conditions[condition]["attempts"]
                        if not r.get("shared_call")
                    ]
                ),
                "eval_count": sum(
                    int(item["eval_count"] or 0)
                    for item in [shared] + [
                        r
                        for condition in CONDITIONS
                        for r in conditions[condition]["attempts"]
                        if not r.get("shared_call")
                    ]
                ),
                "model_calls": 1 + len(CONDITIONS) * 2,
            },
        )
        return result


def _pilot_paths(ts: str) -> PilotPaths:
    return PilotPaths(
        db=DATA_DIR / STORE_DB_NAME,
        jsonl=DATA_DIR / STORE_JSONL_NAME,
        results=DATA_DIR / f"{RESULTS_PREFIX}{ts}.json",
    )


def _settings() -> Settings:
    return load_settings(
        model=MODEL,
        db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=8192,
        think=False,
        temperature=0.1,
        top_p=1.0,
        repeat_penalty=1.1,
        seed=42,
        keep_alive="10m",
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
    if quantization != "Q4_K_M":
        raise SystemExit(
            f"model quantization mismatch: expected Q4_K_M, got {quantization}"
        )
    return digest, model_info


def _verify_ground_truth(tasks: list[Round3Task]) -> dict:
    if not GROUND_TRUTH_PATH.exists():
        raise SystemExit("frozen Round 3 ground truth is missing")
    digest = _sha256_file(GROUND_TRUTH_PATH)
    if digest != GROUND_TRUTH_SHA256:
        raise SystemExit(
            f"ground truth SHA-256 mismatch: expected "
            f"{GROUND_TRUTH_SHA256}, got {digest}"
        )
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    stored = {item["id"]: item for item in ground_truth.get("tasks", [])}
    for task in tasks:
        if stored[task.id].get("prompt_sha256") != _sha256_text(task.prompt):
            raise SystemExit(
                f"prompt SHA-256 mismatch against frozen ground truth: {task.id}"
            )
    return {
        "path": str(GROUND_TRUTH_PATH.name),
        "sha256": digest,
        "prompt_sha256_verified_for": [task.id for task in tasks],
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
)


def _protected_hashes() -> dict[str, str | None]:
    root = DATA_DIR.parent
    return {
        name: _sha256_file(root / name) for name in _PROTECTED_PATHS
    }


def run_memory_pilot() -> Path:
    settings = _settings()
    settings.ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = _pilot_paths(ts)
    for path in (paths.db, paths.jsonl, paths.results):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    tasks = _select_tasks()
    ground_truth_check = _verify_ground_truth(tasks)
    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    try:
        digest, model_info = _verify_model(client)
        run_id = f"memory_{ts}"
        runner = MemoryPilotRunner(
            settings, client, store, digest, model_info, run_id
        )
        record: dict = {
            "run_id": run_id,
            "kind": "memory_retry_pilot",
            "started_at": _now(),
            "model": settings.model,
            "model_digest": digest,
            "model_info": model_info,
            "ground_truth_check": ground_truth_check,
            "settings": {
                "think": settings.think,
                "num_ctx": settings.context_limit,
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "repeat_penalty": settings.repeat_penalty,
                "seed": settings.seed,
                "keep_alive": settings.keep_alive,
                "num_predict": NUM_PREDICT,
                "single_flight": True,
                "sequential": True,
            },
            "design": {
                "tasks": list(TASK_IDS),
                "conditions": list(CONDITIONS),
                "attempts_per_condition": ATTEMPTS_PER_CONDITION,
                "shared_attempt_1": True,
                "planned_calls": PLANNED_CALLS,
                "compressors": {
                    "N": "no injection; prompt byte-identical to attempt 1",
                    "0": "label only; no memory block",
                    "1": "previous answer field",
                    "2": "previous answer field + last 200 characters of derivation",
                    "3": "previous answer field + full derivation",
                    "4": "previous raw response content",
                },
                "injection_wording": (
                    NO_INFORMATION
                    + "\n"
                    + BLOCK_OPEN
                    + "\n{memory}\n"
                    + BLOCK_CLOSE
                    + "\n"
                    + RETRY_INSTRUCTION
                ),
            },
            "guards": {
                "call_budget": CALL_BUDGET,
                "hard_runtime_s": HARD_RUNTIME_S,
                "min_free_mb": MIN_FREE_MB,
            },
            "protected_artifacts_sha256_start": _protected_hashes(),
            "free_mb_start": free_physical_mb(),
            "free_mb_min": None,
            "free_mb_end": None,
            "results": [],
            "task_summaries": {},
            "stopped_early": False,
            "stop_reason": None,
        }

        for index, task in enumerate(tasks, start=1):
            free_before = free_physical_mb()
            if free_before is not None and (
                record["free_mb_min"] is None
                or free_before < record["free_mb_min"]
            ):
                record["free_mb_min"] = free_before
            if free_before is not None and free_before < MIN_FREE_MB:
                record["stopped_early"] = True
                record["stop_reason"] = (
                    f"free physical memory below {MIN_FREE_MB:.0f} MB"
                )
                break
            print(
                f"[{index}/{len(tasks)}] {task.id} "
                f"calls_used={runner.calls_used} "
                f"elapsed_s={runner.elapsed_s:.1f} free_MB={free_before}",
                flush=True,
            )
            try:
                task_result = runner.run_task(task)
            except PilotGuardStop as exc:
                record["stopped_early"] = True
                record["stop_reason"] = str(exc)
                print(f"STOP: {exc}", flush=True)
                break
            record["results"].append(task_result)
            record["task_summaries"][task.id] = {
                "success_at_3": {
                    condition: condition_result["success_at_3"]
                    for condition, condition_result in task_result[
                        "conditions"
                    ].items()
                },
                "audit_success_at_3": {
                    condition: condition_result["audit_success_at_3"]
                    for condition, condition_result in task_result[
                        "conditions"
                    ].items()
                },
                "condition_n_prompt_byte_identity": task_result[
                    "condition_n_prompt_byte_identity"
                ],
            }
            free_after = free_physical_mb()
            if free_after is not None and (
                record["free_mb_min"] is None
                or free_after < record["free_mb_min"]
            ):
                record["free_mb_min"] = free_after
            paths.results.write_text(
                json.dumps(record, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

        task_map = {item["task_id"]: item for item in record["results"]}
        if C_TASK_ID in task_map and all(
            condition in task_map[C_TASK_ID]["conditions"]
            for condition in CONDITIONS
        ):
            record["success_criterion"] = evaluate_success_criterion(task_map)
        else:
            record["success_criterion"] = {
                "criterion": SUCCESS_CRITERION,
                "signal": False,
                "note": "run stopped before all C conditions completed",
            }

        record["finished_at"] = _now()
        record["free_mb_end"] = free_physical_mb()
        record["calls_used_total"] = runner.calls_used
        record["runtime_s_total"] = round(runner.elapsed_s, 2)
        record["completed_tasks"] = len(record["results"])
        record["protected_artifacts_sha256_end"] = _protected_hashes()
        record["protected_artifacts_unchanged"] = (
            record["protected_artifacts_sha256_start"]
            == record["protected_artifacts_sha256_end"]
        )
        paths.results.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"results: {paths.results}", flush=True)
        print(f"sqlite: {paths.db}", flush=True)
        print(f"jsonl: {paths.jsonl}", flush=True)
        print(
            f"calls_used={runner.calls_used} "
            f"runtime_s={runner.elapsed_s:.1f} "
            f"completed={record['completed_tasks']} "
            f"stopped_early={record['stopped_early']}",
            flush=True,
        )
        print(
            "signal="
            f"{record['success_criterion'].get('signal')} "
            f"levels={record['success_criterion'].get('compression_levels_with_composite_and_audit')}",
            flush=True,
        )
        return paths.results
    finally:
        client.close()
        store.close()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description="Memory-retry pilot (local Ollama only)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the frozen tasks, conditions and call plan",
    )
    args = parser.parse_args(argv)
    if args.list:
        for task_id in TASK_IDS:
            print(f"{task_id}\tconditions={','.join(CONDITIONS)}\tcalls=13")
        print(f"planned_calls={PLANNED_CALLS}")
        return 0
    run_memory_pilot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
