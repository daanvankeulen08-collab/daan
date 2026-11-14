"""Sequential Round 3 confirmatory evaluation runner.

Only existing Block 1 components are used for inference, tool execution,
verification and logging.  Round 3 writes to new, separately named SQLite and
JSONL stores.  Round 1 and Round 2 artifacts are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.round2 import _validate_experimental
from block15.round3_tasks import (
    ANSWER_SCHEMA,
    EXPERIMENTAL_INSTRUCTION,
    EXPERIMENTAL_SCHEMA,
    RUN_ORDER,
    SYSTEM_PROMPT,
    TOOL_DECISION_SCHEMA,
    Round3Task,
)
from block15.run_benchmark import (
    DATA_DIR,
    BenchmarkRunner,
    _now,
    _validate_answer,
    free_physical_mb,
)
from mdl.config import Settings, load_settings
from mdl.errors import MdlError, ModelError, ModelOutputError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient
from mdl.orchestrator import ToolOrchestrator
from mdl.verifier import verify_symbolic_expand

CALL_LIMIT = 16
TARGET_CALLS = 14
HARD_RUNTIME_S = 420
TASK_START_CUTOFF_S = 360.0
CALL_START_CUTOFF_S = 390.0
MIN_FREE_MB = 450.0


def _number_present(text: str, value: int) -> bool:
    """Match a signed integer without treating a negative as a positive hit."""

    normalized = text.replace("\u2212", "-").replace("\u2013", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    sign = "-" if value < 0 else ""
    prefix = r"(?<![\d])" if value < 0 else r"(?<![\d-])"
    return re.search(prefix + sign + re.escape(str(abs(value))) + r"(?![\d])", normalized) is not None


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _answer_text(final: dict) -> str:
    return final["answer"] if "answer" in final else final["final_answer"]


def _derivation_text(final: dict) -> str:
    if "derivation" in final:
        return " ".join(final["derivation"])
    return final.get("reasoning", "")


def _validate_tool_decision(parsed: dict) -> dict:
    if not isinstance(parsed.get("use_tool"), bool):
        raise ValueError("tool decision use_tool must be a boolean")
    if not isinstance(parsed.get("expression"), str):
        raise ValueError("tool decision expression must be a string")
    if not isinstance(parsed.get("reason"), str):
        raise ValueError("tool decision reason must be a string")
    return {
        "use_tool": parsed["use_tool"],
        "expression": parsed["expression"],
        "reason": parsed["reason"],
    }


def _validate_direct_tool(parsed: dict) -> str:
    if parsed.get("tool") != "symbolic_expand":
        raise ValueError("direct tool request must name symbolic_expand")
    arguments = parsed.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("direct tool arguments must be an object")
    expression = arguments.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("direct tool expression must be a non-empty string")
    return expression


def _tool_prompt_record(tool: dict) -> str:
    return (
        "\n\nThe symbolic_expand record is:\n"
        + json.dumps(tool, ensure_ascii=True)
    )


def independent_check(task: Round3Task, final: dict, tool: dict | None) -> dict:
    text = _answer_text(final)
    derivation = _derivation_text(final)
    base = {
        "method": task.verification,
        "expected": task.expected,
        "observed_answer": text,
        "observed_derivation": derivation,
        "observed_confidence": final["confidence"],
        "observed_uncertainty": final["uncertainty"],
    }

    if task.id.startswith("R3A1_coefficient") or task.id.startswith(
        "R3A1_coefficient_protocol_B_repeat"
    ):
        x = sympy.Symbol("x")
        coefficient = int(sympy.expand((3 * x - 2) ** 6).coeff(x, 4))
        final_ok = _number_present(text, coefficient)
        derivation_ok = _number_present(derivation, coefficient)
        return {
            **base,
            "computed_expected": str(coefficient),
            "final_contains_expected": final_ok,
            "derivation_contains_expected": derivation_ok,
            "answer_derivation_consistency": (
                "consistent"
                if final_ok and derivation_ok
                else "derivation_only"
                if derivation_ok
                else "final_only"
                if final_ok
                else "neither"
            ),
            "status": "objective_pass" if final_ok else "objective_fail",
            "detail": "SymPy coefficient compared with final answer and derivation",
        }

    if task.id.startswith("R3A2_divisibility"):
        checked = all((k**3 - k) % 6 == 0 for k in range(-500, 501))
        compact = _compact(text + " " + derivation)
        mentions_three = (
            "threeconsecutive" in compact
            or "productofthree" in compact
            or "n(n-1)(n+1)" in compact
        )
        mentions_even = "divisibleby2" in compact or "even" in compact
        mentions_three_factor = (
            "divisibleby3" in compact or "multipleof3" in compact
        )
        return {
            **base,
            "identity": "n^3 - n = n(n-1)(n+1)",
            "exhaustive_check_n_minus_500_to_500": checked,
            "mentions_three_consecutive_product": mentions_three,
            "mentions_even_factor": mentions_even,
            "mentions_factor_divisible_by_3": mentions_three_factor,
            "status": "manual_review_required",
            "detail": "independent divisibility check plus proof-rubric review",
        }

    if task.id == "R3B_counterexample_minimality":
        values = []
        first = None
        first_value = None
        for k in range(0, 101):
            value = k * k + k + 101
            if not sympy.isprime(value):
                first = k
                first_value = value
                break
            values.append({"n": k, "value": value, "prime": True})
        factors = sympy.factorint(first_value) if first_value is not None else None
        final_n_ok = first is not None and _number_present(text, first)
        final_value_ok = first_value is not None and _number_present(text, first_value)
        final_factor_ok = (
            "11^2" in text.replace(" ", "")
            or "11**2" in text.replace(" ", "")
            or "11*11" in text.replace(" ", "")
            or (
                _number_present(text, 11)
                and ("factor" in text.lower() or "=" in text)
            )
        )
        deriv_n_ok = first is not None and _number_present(derivation, first)
        mentions_all_preceding = (
            all(_number_present(text + " " + derivation, item["value"]) for item in values)
            if values
            else False
        )
        mentions_minimality = any(
            token in (text + " " + derivation).lower()
            for token in ("minimal", "smallest", "preceding", "previous")
        )
        return {
            **base,
            "computed_expected": {
                "first_n": first,
                "value": first_value,
                "factorization": factors,
                "preceding": values,
            },
            "final_contains_first_n": final_n_ok,
            "final_contains_counterexample_value": final_value_ok,
            "final_contains_factorization": final_factor_ok,
            "derivation_contains_first_n": deriv_n_ok,
            "mentions_all_preceding_values": mentions_all_preceding,
            "mentions_minimality_language": mentions_minimality,
            "status": (
                "objective_partial"
                if final_n_ok and final_value_ok and final_factor_ok
                else "objective_fail"
            ),
            "detail": (
                "counterexample facts are independently computed; the "
                "minimality argument still requires manual rubric review"
            ),
        }

    if task.id == "R3C_hypothesis_falsification":
        values = []
        first = None
        first_value = None
        for k in range(0, 101):
            value = k * k + k + 1277
            if not sympy.isprime(value):
                first = k
                first_value = value
                break
            values.append({"n": k, "value": value, "prime": True})
        factors = sympy.factorint(first_value) if first_value is not None else None
        compact = _compact(text + " " + derivation)
        final_n_ok = first is not None and _number_present(text, first)
        final_value_ok = first_value is not None and _number_present(text, first_value)
        final_factor_ok = _number_present(text, 31) and _number_present(text, 43)
        mentions_all_preceding = (
            all(_number_present(text + " " + derivation, item["value"]) for item in values)
            if values
            else False
        )
        denies_universal = any(
            token in compact
            for token in (
                "notjustified",
                "notproved",
                "notproven",
                "doesnotprove",
                "insufficient",
                "cannotconclude",
                "notestablished",
            )
        )
        mentions_minimality = any(
            token in compact for token in ("minimal", "smallest", "preceding", "previous")
        )
        return {
            **base,
            "computed_expected": {
                "first_counterexample_n": first,
                "value": first_value,
                "factorization": factors,
                "preceding": values,
            },
            "final_contains_first_n": final_n_ok,
            "final_contains_counterexample_value": final_value_ok,
            "final_contains_factors_31_43": final_factor_ok,
            "mentions_all_preceding_values": mentions_all_preceding,
            "denies_universal_prime_claim": denies_universal,
            "mentions_minimality_language": mentions_minimality,
            "status": "manual_review_required",
            "detail": "hypothesis, falsification and minimality require rubric review",
        }

    if task.id.startswith("R3D1_tool_voluntary"):
        x = sympy.Symbol("x")
        coefficient = int(sympy.expand((3 * x - 2) ** 12).coeff(x, 7))
        final_ok = _number_present(text, coefficient)
        derivation_ok = _number_present(derivation, coefficient)
        return {
            **base,
            "computed_expected": str(coefficient),
            "final_contains_expected": final_ok,
            "derivation_contains_expected": derivation_ok,
            "answer_derivation_consistency": (
                "consistent"
                if final_ok and derivation_ok
                else "derivation_only"
                if derivation_ok
                else "final_only"
                if final_ok
                else "neither"
            ),
            "status": "objective_pass" if final_ok else "objective_fail",
            "detail": "SymPy coefficient compared with final answer and derivation",
        }

    if task.id.startswith("R3D2_tool_required"):
        x = sympy.Symbol("x")
        coefficient = int(sympy.expand((2 * x + 3) ** 7).coeff(x, 5))
        final_ok = _number_present(text, coefficient)
        derivation_ok = _number_present(derivation, coefficient)
        return {
            **base,
            "computed_expected": str(coefficient),
            "final_contains_expected": final_ok,
            "derivation_contains_expected": derivation_ok,
            "answer_derivation_consistency": (
                "consistent"
                if final_ok and derivation_ok
                else "derivation_only"
                if derivation_ok
                else "final_only"
                if final_ok
                else "neither"
            ),
            "status": "objective_pass" if final_ok else "objective_fail",
            "detail": "SymPy coefficient compared with final answer and derivation",
        }

    if task.id.startswith("R3E1_uncertainty_determinate"):
        checked = all((k * (k + 1) * (k + 2)) % 6 == 0 for k in range(-500, 501))
        compact = _compact(text + " " + derivation)
        mentions_three = (
            "threeconsecutive" in compact or "productofthree" in compact
        )
        mentions_even = "divisibleby2" in compact or "even" in compact
        mentions_three_factor = (
            "divisibleby3" in compact or "multipleof3" in compact
        )
        return {
            **base,
            "exhaustive_check_n_minus_500_to_500": checked,
            "mentions_three_consecutive_product": mentions_three,
            "mentions_even_factor": mentions_even,
            "mentions_factor_divisible_by_3": mentions_three_factor,
            "status": "manual_review_required",
            "detail": "independent divisibility check plus proof-rubric review",
        }

    if task.id.startswith("R3E2_uncertainty_underdetermined"):
        compact = _compact(text + " " + derivation)
        says_43 = _number_present(text, 43)
        derivation_says_43 = _number_present(derivation, 43)
        denies_unique = any(
            token in compact
            for token in (
                "notunique",
                "notuniquely",
                "cannotbeuniquely",
                "cannotbedetermined",
                "notdetermined",
                "underdetermined",
            )
        )
        mentions_extra_information = any(
            token in compact
            for token in ("additionalinformation", "rule", "assumption", "modelclass")
        )
        return {
            **base,
            "computed_expected": {
                "simple_continuation": 43,
                "first_differences": [4, 6, 8, 10],
                "second_differences": [2, 2, 2],
            },
            "final_contains_43": says_43,
            "derivation_contains_43": derivation_says_43,
            "denies_unique_determination": denies_unique,
            "mentions_additional_information": mentions_extra_information,
            "status": "manual_review_required",
            "detail": "plausible continuation and uniqueness require rubric review",
        }

    if task.id.startswith("R3F_numerical_trend_noise"):
        compact = _compact(text + " " + derivation)
        trend_up = any(
            token in compact for token in ("upward", "increasing", "rising", "upwardtrend")
        )
        fluctuations = any(
            token in compact for token in ("alternat", "fluctuat", "oscillat")
        )
        denies_exact_rule = any(
            token in compact
            for token in (
                "notdeterministic",
                "notanexact",
                "cannotconclude",
                "doesnotestablish",
                "notunique",
                "noexactrule",
            )
        )
        continuation_caution = any(
            token in compact for token in ("continue", "extrapolat", "future")
        )
        mentions_more_data = any(
            token in compact
            for token in ("moreobservations", "additionalobservations", "moredata", "repeated")
        )
        return {
            **base,
            "trend_upward": trend_up,
            "mentions_fluctuations": fluctuations,
            "denies_exact_deterministic_rule": denies_exact_rule,
            "mentions_continuation_caution": continuation_caution,
            "mentions_more_observations": mentions_more_data,
            "status": "manual_review_required",
            "detail": "descriptive trend and noise judgement require rubric review",
        }

    return {
        **base,
        "status": "manual_review_required",
        "detail": "no automated check registered for this task",
    }


def tool_evaluation(task: Round3Task, tool: dict | None, final: dict) -> dict:
    if tool is None:
        return {
            "tool_available": task.mode in {"tool_voluntary", "tool_required"},
            "use_tool": False,
            "note": "no tool record",
        }
    expression = tool.get("requested_expression", "")
    status = tool.get("status")
    verification = tool.get("verification") or {}
    accepted = status in {"accepted", "executed"}
    executed = status == "executed"
    uses_double_star = "**" in expression and "^" not in expression
    expected = task.expected
    interpreted = _number_present(_answer_text(final), int(expected))
    return {
        "tool_available": True,
        "use_tool": bool(tool.get("use_tool")),
        "decision_reason": tool.get("decision_reason"),
        "requested_expression": expression,
        "uses_double_star_not_caret": uses_double_star,
        "orchestrator_accepted": accepted,
        "tool_executed": executed,
        "tool_status": status,
        "tool_verification_status": verification.get("status"),
        "tool_error": tool.get("error"),
        "final_answer_correct": interpreted,
        "tool_result_interpreted": interpreted if executed else None,
    }


class Round3Runner(BenchmarkRunner):
    def __init__(
        self,
        settings: Settings,
        client: OllamaClient,
        store: ResearchStore,
        orchestrator: ToolOrchestrator,
        digest: str | None,
        model_info: dict | None,
        run_id: str,
    ) -> None:
        super().__init__(
            settings, client, store, orchestrator, digest, model_info, run_id
        )
        self.run_started = perf_counter()
        self.calls_used = 0

    @property
    def elapsed_s(self) -> float:
        return perf_counter() - self.run_started

    def _call(
        self,
        experiment_id: str,
        phase: str,
        messages: list[dict],
        schema: dict,
        num_predict: int,
        token_usage: dict,
    ) -> tuple[dict, dict]:
        if self.calls_used >= CALL_LIMIT:
            raise RuntimeError(f"hard model-call limit {CALL_LIMIT} reached")
        if self.elapsed_s > CALL_START_CUTOFF_S:
            raise RuntimeError(
                f"hard runtime cutoff {CALL_START_CUTOFF_S:.0f}s reached before call"
            )
        self.calls_used += 1
        return super()._call(
            experiment_id, phase, messages, schema, num_predict, token_usage
        )

    def _experimental_final(
        self,
        task: Round3Task,
        experiment_id: str,
        token_usage: dict,
        calls: list[dict],
        tool: dict | None = None,
    ) -> dict:
        content = task.math_question
        if tool is not None:
            content += _tool_prompt_record(tool)
        content += EXPERIMENTAL_INSTRUCTION
        parsed, call = self._call(
            experiment_id,
            "final_answer",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            EXPERIMENTAL_SCHEMA,
            1200,
            token_usage,
        )
        calls.append(call)
        return _validate_experimental(parsed)

    def run_task(self, task: Round3Task) -> dict:
        started = perf_counter()
        token_usage = {
            "prompt_eval_count": 0,
            "eval_count": 0,
            "model_calls": 0,
        }
        experiment_id = self.store.create_experiment(
            seed=task.id,
            model=self.settings.model,
            model_digest=self.digest,
            parameters={
                **self._settings_record(1200),
                "run_id": self.run_id,
                "round": 3,
                "task_id": task.id,
                "group": task.group,
                "category": task.category,
                "difficulty": task.difficulty,
                "protocol": task.protocol,
                "mode": task.mode,
                "repeat_of": task.repeat_of,
            },
            context_limit=self.settings.context_limit,
        )
        self.store.log_event(
            experiment_id,
            "round3_task_started",
            {"task": task.metadata(), "started_at": _now()},
        )
        calls: list[dict] = []
        tool_record: dict | None = None
        result = {
            "run_id": self.run_id,
            "task": task.metadata(),
            "experiment_id": experiment_id,
            "status": "running",
            "calls": calls,
            "tool": None,
            "tool_evaluation": None,
            "final_answer": None,
            "verification": None,
            "latency_ms": None,
            "tokens": token_usage,
            "error": None,
            "incomplete": False,
        }

        try:
            if task.mode == "tool_voluntary":
                parsed, call = self._call(
                    experiment_id,
                    "tool_decision",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task.prompt},
                    ],
                    TOOL_DECISION_SCHEMA,
                    300,
                    token_usage,
                )
                calls.append(call)
                decision = _validate_tool_decision(parsed)
                tool_record = self._execute_tool(
                    experiment_id,
                    {
                        "use_tool": decision["use_tool"],
                        "expression": decision["expression"],
                        "reason": decision["reason"],
                    },
                )
                final = self._experimental_final(
                    task,
                    experiment_id,
                    token_usage,
                    calls,
                    tool_record if decision["use_tool"] else None,
                )
            elif task.mode == "tool_required":
                parsed, call = self._call(
                    experiment_id,
                    "tool_request",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task.prompt},
                    ],
                    self._direct_tool_schema(),
                    300,
                    token_usage,
                )
                calls.append(call)
                expression = _validate_direct_tool(parsed)
                tool_record = self._execute_tool(
                    experiment_id,
                    {
                        "use_tool": True,
                        "expression": expression,
                        "reason": "required Round 3 tool request",
                    },
                )
                final = self._experimental_final(
                    task, experiment_id, token_usage, calls, tool_record
                )
            else:
                schema = (
                    ANSWER_SCHEMA
                    if task.protocol == "A_round1_answer_reasoning"
                    else EXPERIMENTAL_SCHEMA
                )
                parsed, call = self._call(
                    experiment_id,
                    "final_answer",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task.prompt},
                    ],
                    schema,
                    1200,
                    token_usage,
                )
                calls.append(call)
                final = (
                    _validate_answer(parsed)
                    if task.protocol == "A_round1_answer_reasoning"
                    else _validate_experimental(parsed)
                )

            verification = independent_check(task, final, tool_record)
            tool_eval = tool_evaluation(task, tool_record, final)
            result.update(
                {
                    "status": "completed",
                    "final_answer": final,
                    "tool": tool_record,
                    "tool_evaluation": tool_eval,
                    "verification": verification,
                }
            )
            self.store.log_step(
                experiment_id,
                "independent_verification",
                verification["status"],
                {
                    "verification": verification,
                    "tool_evaluation": tool_eval,
                    "answer_consistency": verification.get(
                        "answer_derivation_consistency"
                    ),
                },
            )
            self.store.set_experiment_fields(
                experiment_id,
                hypothesis_json=task.metadata(),
                interpretation_json=final,
                tool_request_json=(
                    tool_record.get("request") if tool_record else None
                ),
                tool_result_json=(
                    tool_record.get("result") if tool_record else None
                ),
                verification_json=verification,
                context_json={
                    "task": task.metadata(),
                    "final_answer": final,
                    "tool": tool_record,
                    "tool_evaluation": tool_eval,
                    "verification": verification,
                    "calls": calls,
                },
            )
            latency_ms = (perf_counter() - started) * 1000.0
            result["latency_ms"] = round(latency_ms, 2)
            self.store.finish_experiment(
                experiment_id,
                "completed",
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
        except Exception as exc:  # noqa: BLE001 - failed tasks must be recorded
            latency_ms = (perf_counter() - started) * 1000.0
            result.update(
                {
                    "status": "failed",
                    "latency_ms": round(latency_ms, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                    "incomplete": isinstance(exc, RuntimeError),
                }
            )
            self.store.log_step(
                experiment_id,
                "round3_error",
                "failed",
                {
                    "task_id": task.id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "calls_used": self.calls_used,
                    "elapsed_s": round(self.elapsed_s, 2),
                },
                latency_ms=latency_ms,
            )
            self.store.finish_experiment(
                experiment_id,
                "failed",
                error=str(exc),
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
        return result

    @staticmethod
    def _direct_tool_schema() -> dict:
        from block15.round3_tasks import DIRECT_TOOL_SCHEMA

        return DIRECT_TOOL_SCHEMA


def _safe_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _round3_store_paths() -> tuple[Path, Path]:
    """Resolve the Round 3 store paths, allowing separate stores per arm.

    Defaults are exactly ``block15_round3.sqlite3`` and
    ``block15_round3_events.jsonl`` under ``DATA_DIR``.
    ``BLOCK15_DB_PATH`` / ``BLOCK15_JSONL_PATH`` override the file names;
    relative names stay under ``DATA_DIR`` and absolute paths are honoured.
    With both variables unset the resolved paths are identical to the values
    previously hard-coded here.
    """

    db_name = os.environ.get("BLOCK15_DB_PATH", "block15_round3.sqlite3")
    jsonl_name = os.environ.get(
        "BLOCK15_JSONL_PATH", "block15_round3_events.jsonl"
    )
    db_path = Path(db_name)
    jsonl_path = Path(jsonl_name)
    return (
        db_path if db_path.is_absolute() else DATA_DIR / db_path,
        jsonl_path if jsonl_path.is_absolute() else DATA_DIR / jsonl_path,
    )


def run_round3() -> Path:
    db_path, jsonl_path = _round3_store_paths()
    settings = load_settings(db_path=db_path, jsonl_path=jsonl_path)
    settings.ensure_data_dir()
    ground_truth_path = DATA_DIR / "block15_round3_ground_truth.json"
    if not ground_truth_path.exists():
        raise SystemExit("frozen Round 3 ground truth is missing")
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))

    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    orchestrator = ToolOrchestrator(settings.tool_timeout_s)
    try:
        if not client.health():
            raise SystemExit("Ollama is not reachable")
        model_info = client.model_info()
        if model_info is None:
            raise SystemExit(f"model {settings.model!r} is not installed")
        digest = model_info.get("digest")
        if not digest:
            raise SystemExit("model digest is unavailable")

        run_id = "round3_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DATA_DIR / f"block15_round3_results_{run_id}.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

        runner = Round3Runner(
            settings, client, store, orchestrator, digest, model_info, run_id
        )
        record: dict = {
            "run_id": run_id,
            "round": 3,
            "started_at": _now(),
            "model": settings.model,
            "model_digest": digest,
            "model_info": model_info,
            "ground_truth_file": ground_truth_path.name,
            "ground_truth_sha256": _safe_hash(ground_truth_path),
            "settings": {
                "think": settings.think,
                "num_ctx": settings.context_limit,
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "repeat_penalty": settings.repeat_penalty,
                "seed": settings.seed,
                "keep_alive": settings.keep_alive,
                "num_predict_decision": 300,
                "num_predict_final": 1200,
                "single_flight": True,
                "sequential": True,
            },
            "limits": {
                "target_calls": TARGET_CALLS,
                "call_limit": CALL_LIMIT,
                "hard_runtime_s": HARD_RUNTIME_S,
                "task_start_cutoff_s": TASK_START_CUTOFF_S,
                "call_start_cutoff_s": CALL_START_CUTOFF_S,
                "min_free_mb": MIN_FREE_MB,
            },
            "free_mb_start": free_physical_mb(),
            "results": [],
            "incomplete_tasks": [],
            "free_mb_min": None,
            "free_mb_end": None,
            "stopped_early": False,
            "stop_reason": None,
        }

        for index, task in enumerate(RUN_ORDER, start=1):
            free_before = free_physical_mb()
            elapsed = runner.elapsed_s
            if record["free_mb_min"] is None or (
                free_before is not None and free_before < record["free_mb_min"]
            ):
                record["free_mb_min"] = free_before
            if runner.calls_used >= CALL_LIMIT or elapsed > TASK_START_CUTOFF_S:
                record["stopped_early"] = True
                record["stop_reason"] = (
                    f"call limit {CALL_LIMIT} or task-start cutoff "
                    f"{TASK_START_CUTOFF_S:.0f}s reached"
                )
                record["incomplete_tasks"].append(task.metadata())
                print(f"STOP: {record['stop_reason']}", flush=True)
                break
            if free_before is not None and free_before < MIN_FREE_MB:
                record["stopped_early"] = True
                record["stop_reason"] = f"free physical memory below {MIN_FREE_MB} MB"
                record["incomplete_tasks"].append(task.metadata())
                print(f"STOP: {record['stop_reason']}", flush=True)
                break

            print(
                f"[{index}/{len(RUN_ORDER)}] {task.id} "
                f"({task.group}, {task.protocol}) calls={runner.calls_used} "
                f"elapsed_s={elapsed:.1f} free_MB={free_before}",
                flush=True,
            )
            task_result = runner.run_task(task)
            record["results"].append(task_result)
            free_after = free_physical_mb()
            if free_after is not None and (
                record["free_mb_min"] is None or free_after < record["free_mb_min"]
            ):
                record["free_mb_min"] = free_after
            print(
                f"    status={task_result['status']} "
                f"calls={task_result['tokens']['model_calls']} "
                f"latency_s={(task_result['latency_ms'] or 0) / 1000:.1f} "
                f"tokens={task_result['tokens']}",
                flush=True,
            )
            output_path.write_text(
                json.dumps(record, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

        record["finished_at"] = _now()
        record["free_mb_end"] = free_physical_mb()
        record["calls_used_total"] = runner.calls_used
        record["runtime_s_total"] = round(runner.elapsed_s, 2)
        record["prompt_tokens_total"] = sum(
            item["tokens"]["prompt_eval_count"] for item in record["results"]
        )
        record["eval_tokens_total"] = sum(
            item["tokens"]["eval_count"] for item in record["results"]
        )
        record["completed_tasks"] = sum(
            item["status"] == "completed" for item in record["results"]
        )
        record["failed_tasks"] = sum(
            item["status"] == "failed" for item in record["results"]
        )
        output_path.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"results: {output_path}", flush=True)
        print(f"sqlite: {settings.db_path}", flush=True)
        print(f"jsonl: {settings.jsonl_path}", flush=True)
        print(
            f"calls_used={runner.calls_used} runtime_s={runner.elapsed_s:.1f} "
            f"completed={record['completed_tasks']} failed={record['failed_tasks']}",
            flush=True,
        )
        return output_path
    finally:
        client.close()
        store.close()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Block 1.5 Round 3 runner")
    parser.add_argument(
        "--list", action="store_true", help="list Round 3 task IDs and exit"
    )
    args = parser.parse_args(argv)
    if args.list:
        for task in RUN_ORDER:
            calls = 2 if task.mode in {"tool_voluntary", "tool_required"} else 1
            print(
                f"{task.id}\t{task.group}\t{task.category}\t"
                f"{task.protocol}\t{task.mode}\tcalls={calls}"
            )
        return 0
    run_round3()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
