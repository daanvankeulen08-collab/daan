"""Round 2 controlled evaluation runner.

This module adds a new, separately logged experiment.  It never writes to the
Round 1 SQLite/JSONL files and never modifies Block 1.

The model is still LFM3.  All tool requests go through the existing
``mdl.ToolOrchestrator``; no model-generated code is executed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.round2_tasks import (
    ANSWER_SCHEMA,
    DIRECT_TOOL_INSTRUCTION,
    DIRECT_TOOL_SCHEMA,
    EXPERIMENTAL_INSTRUCTION,
    EXPERIMENTAL_SCHEMA,
    RUN_ORDER,
    SYSTEM_PROMPT,
    VOLUNTARY_INSTRUCTION,
    VOLUNTARY_SCHEMA,
    Round2Task,
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

CALL_LIMIT = 20
TARGET_CALLS = 16
HARD_RUNTIME_S = 450
TASK_START_CUTOFF_S = 400.0
CALL_START_CUTOFF_S = 405.0
MIN_FREE_MB = 450.0


def _contains_int(text: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", text) is not None


def _validate_experimental(parsed: dict) -> dict:
    required = ("derivation", "final_answer", "uncertainty", "confidence")
    missing = [name for name in required if name not in parsed]
    if missing:
        raise ValueError(f"experimental JSON is missing fields: {missing}")
    derivation = parsed["derivation"]
    if not isinstance(derivation, list) or not derivation:
        raise ValueError("derivation must be a non-empty array")
    if not all(isinstance(step, str) and step.strip() for step in derivation):
        raise ValueError("every derivation step must be a non-empty string")
    if not isinstance(parsed["final_answer"], str) or not parsed["final_answer"].strip():
        raise ValueError("final_answer must be a non-empty string")
    if not isinstance(parsed["uncertainty"], str):
        raise ValueError("uncertainty must be a string")
    confidence = parsed["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return {
        "derivation": list(derivation),
        "final_answer": parsed["final_answer"],
        "uncertainty": parsed["uncertainty"],
        "confidence": confidence,
    }


def _validate_voluntary(parsed: dict) -> dict:
    required = (
        "use_tool",
        "expression",
        "derivation",
        "final_answer",
        "uncertainty",
        "confidence",
    )
    missing = [name for name in required if name not in parsed]
    if missing:
        raise ValueError(f"voluntary JSON is missing fields: {missing}")
    if not isinstance(parsed["use_tool"], bool):
        raise ValueError("use_tool must be a boolean")
    if not isinstance(parsed["expression"], str):
        raise ValueError("expression must be a string")
    validated = _validate_experimental(parsed)
    validated["use_tool"] = parsed["use_tool"]
    validated["expression"] = parsed["expression"]
    if parsed["use_tool"] and not parsed["expression"].strip():
        raise ValueError("use_tool was true but expression was empty")
    return validated


def _answer_text(final: dict) -> str:
    return final["answer"] if "answer" in final else final["final_answer"]


def _derivation_text(final: dict) -> str:
    if "derivation" in final:
        return " ".join(final["derivation"])
    return final.get("reasoning", "")


def independent_check(task: Round2Task, final: dict, tool: dict | None) -> dict:
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

    if task.id.startswith("R2A1_coefficient") or task.id.startswith("R2B2_tool_required"):
        x = sympy.Symbol("x")
        coefficient = sympy.expand((2 * x - 1) ** 5).coeff(x, 3)
        passed = _contains_int(text, int(coefficient))
        derivation_confirms = _contains_int(derivation, int(coefficient))
        return {
            **base,
            "computed_expected": str(coefficient),
            "status": "objective_pass" if passed else "objective_fail",
            "answer_derivation_consistency": (
                "consistent" if passed and derivation_confirms else "unconfirmed"
            ),
            "detail": (
                "independent coefficient matches final answer and derivation"
                if passed and derivation_confirms
                else "independent coefficient is present; check raw answer/derivation scope"
            ),
        }

    if task.id.startswith("R2B1_tool_voluntary"):
        x = sympy.Symbol("x")
        coefficient = sympy.expand((x + 3) ** 4).coeff(x, 2)
        passed = _contains_int(text, int(coefficient))
        derivation_confirms = _contains_int(derivation, int(coefficient))
        return {
            **base,
            "computed_expected": str(coefficient),
            "status": "objective_pass" if passed else "objective_fail",
            "answer_derivation_consistency": (
                "consistent" if passed and derivation_confirms else "unconfirmed"
            ),
            "tool": tool,
        }

    if task.id.startswith("R2A2_divisibility"):
        parity_ok = all(
            (n * (n + 1) * (n + 2)) % 6 == 0 for n in range(-100, 101)
        )
        compact = (text + " " + derivation).lower().replace(" ", "")
        mentions_divisible_by_3 = "divisibleby3" in compact
        mentions_even_factor = (
            "onefactoriseven" in compact
            or "atleastoneiseven" in compact
            or "twofactor" in compact
        )
        status = (
            "manual_review_required"
            if parity_ok and mentions_divisible_by_3 and mentions_even_factor
            else "manual_review_required_with_flags"
        )
        return {
            **base,
            "exhaustive_check_divisible_by_6": parity_ok,
            "proof_flag_divisible_by_3": mentions_divisible_by_3,
            "proof_flag_even_factor": mentions_even_factor,
            "status": status,
            "detail": "independent numerical check plus logical rubric review required",
        }

    if task.id.startswith("R2A3_sequence"):
        n = sympy.Symbol("n")
        data = [(i + 1, term) for i, term in enumerate([2, 6, 12, 20, 30, 42])]
        poly = sympy.interpolate(data, n)
        next_term = int(poly.subs(n, 7))
        compact = (text + " " + derivation).lower().replace(" ", "")
        formula_ok = (
            "n(n+1)" in compact
            or "n*(n+1)" in compact
            or "n^2+n" in compact
            or "n²+n" in compact
        )
        uniqueness_ok = (
            "notuniquelydetermined" in compact
            or "notunique" in compact
            or "notuniquely" in compact
            or "cannotbeuniquely" in compact
        )
        return {
            **base,
            "computed_expected": {
                "simplest_polynomial": str(sympy.expand(poly)),
                "next_term": next_term,
                "rule_form": "n(n+1) if first term is n=1",
            },
            "status": (
                "objective_pass"
                if _contains_int(text, next_term) and formula_ok and uniqueness_ok
                else "objective_fail"
            ),
            "answer_derivation_consistency": (
                "consistent" if _contains_int(text, next_term) else "unconfirmed"
            ),
            "uniqueness_stated": uniqueness_ok,
        }

    if task.id.startswith("R2A4_composite"):
        first = None
        first_value = None
        for n in range(0, 101):
            value = n * n + n + 11
            if not sympy.isprime(value):
                first = n
                first_value = value
                break
        passed = first is not None and _contains_int(text, first)
        derivation_confirms = first is not None and (
            _contains_int(derivation, first) or _contains_int(derivation, first_value or -1)
        )
        return {
            **base,
            "computed_expected": {"n": first, "value": first_value},
            "status": "objective_pass" if passed else "objective_fail",
            "answer_derivation_consistency": (
                "consistent" if passed and derivation_confirms else "unconfirmed"
            ),
        }

    if task.id.startswith("R2C1_uncertainty_determinate"):
        parity_ok = all((n * n + n) % 2 == 0 for n in range(-200, 201))
        return {
            **base,
            "parity_check_all_even": parity_ok,
            "status": "manual_review_required",
            "detail": "conclusion and proof scope require rubric review",
        }

    if task.id.startswith("R2C2_uncertainty_underdetermined"):
        compact = text.lower()
        says_no = "no" in compact or "not unique" in compact
        inherits_correct_caution = "not unique" in compact or "cannot be uniquely" in compact
        return {
            **base,
            "states_no_unique_determination": inherits_correct_caution,
            "mentions_no": says_no,
            "status": "manual_review_required",
            "detail": "uncertainty statement requires rubric review",
        }

    if task.id.startswith("R2D_hypothesis_generalization"):
        first = None
        first_value = None
        for n in range(0, 101):
            value = n * n + n + 17
            if not sympy.isprime(value):
                first = n
                first_value = value
                break
        return {
            **base,
            "computed_expected": {
                "smallest_counterexample_n": first,
                "value": first_value,
                "factorization": (
                    sympy.factorint(first_value) if first_value is not None else None
                ),
            },
            "status": "manual_review_required",
            "detail": "hypothesis quality, evidence limits and minimality require rubric review",
        }

    if task.id.startswith("R2E_self_correction"):
        x = sympy.Symbol("x")
        correct = sympy.expand((x + 2) ** 2)
        compact = (text + " " + derivation).lower().replace(" ", "")
        rejects = "incorrect" in (text + " " + derivation).lower()
        gives_correct = "x^2+4x+4" in compact or "x²+4x+4" in compact
        gives_missing_term = "4x" in compact
        return {
            **base,
            "computed_expected": str(correct),
            "status": (
                "objective_pass"
                if rejects and gives_correct and gives_missing_term
                else "objective_fail"
            ),
            "answer_derivation_consistency": (
                "consistent" if rejects and gives_correct else "unconfirmed"
            ),
        }

    return {
        **base,
        "status": "manual_review_required",
        "detail": "no automated check registered for this task",
    }


def tool_evaluation(task: Round2Task, tool: dict | None, final: dict) -> dict:
    if tool is None:
        return {
            "tool_available": False,
            "use_tool": False,
            "note": "no tool phase for this task",
        }
    expression = tool.get("requested_expression", "")
    status = tool.get("status")
    used_star = "**" in expression and "^" not in expression
    parsed_by_orchestrator = status in {"accepted", "executed"}
    executed = status == "executed"
    verification = tool.get("verification") or {}
    coefficient = None
    if task.id.startswith("R2B1_tool_voluntary"):
        coefficient = "54"
    elif task.id.startswith("R2B2_tool_required"):
        coefficient = "80"
    final_answer = _answer_text(final)
    interpreted_correctly = coefficient is not None and _contains_int(final_answer, int(coefficient))
    return {
        "tool_available": True,
        "use_tool": bool(tool.get("use_tool")),
        "requested_expression": expression,
        "uses_double_star_not_caret": used_star,
        "orchestrator_accepted": parsed_by_orchestrator,
        "tool_executed": executed,
        "tool_status": status,
        "tool_verification_status": verification.get("status"),
        "final_answer_correct": interpreted_correctly,
        "tool_result_interpreted": interpreted_correctly if executed else None,
    }


class Round2Runner(BenchmarkRunner):
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

    def _final_after_tool(
        self,
        task: Round2Task,
        tool_record: dict,
        experiment_id: str,
        token_usage: dict,
        calls: list[dict],
    ) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    task.math_question
                    + "\n\nThe symbolic_expand record is:\n"
                    + json.dumps(tool_record, ensure_ascii=True)
                    + EXPERIMENTAL_INSTRUCTION
                ),
            },
        ]
        parsed, call = self._call(
            experiment_id,
            "final_answer_after_tool",
            messages,
            EXPERIMENTAL_SCHEMA,
            1200,
            token_usage,
        )
        calls.append(call)
        return _validate_experimental(parsed)

    def run_task(self, task: Round2Task) -> dict:
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
                "round": 2,
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
            "round2_task_started",
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
                    VOLUNTARY_SCHEMA,
                    300,
                    token_usage,
                )
                calls.append(call)
                provisional = _validate_voluntary(parsed)
                tool_record = self._execute_tool(
                    experiment_id,
                    {
                        "use_tool": provisional["use_tool"],
                        "expression": provisional["expression"],
                        "reason": "voluntary Round 2 decision",
                    },
                )
                if provisional["use_tool"]:
                    final = self._final_after_tool(
                        task, tool_record, experiment_id, token_usage, calls
                    )
                else:
                    final = provisional
            elif task.mode == "tool_required":
                parsed, call = self._call(
                    experiment_id,
                    "tool_request",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task.prompt},
                    ],
                    DIRECT_TOOL_SCHEMA,
                    300,
                    token_usage,
                )
                calls.append(call)
                arguments = parsed.get("arguments")
                expression = (
                    arguments.get("expression", "")
                    if isinstance(arguments, dict)
                    else ""
                )
                tool_record = self._execute_tool(
                    experiment_id,
                    {
                        "use_tool": True,
                        "expression": expression,
                        "reason": "required Round 2 tool request",
                    },
                )
                final = self._final_after_tool(
                    task, tool_record, experiment_id, token_usage, calls
                )
            else:
                parsed, call = self._call(
                    experiment_id,
                    "final_answer",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task.prompt},
                    ],
                    (
                        ANSWER_SCHEMA
                        if task.protocol == "A_round1_answer_reasoning"
                        else EXPERIMENTAL_SCHEMA
                    ),
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
                    "consistency": verification.get("answer_derivation_consistency"),
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
                    "final_answer": result.get("final_answer"),
                    "latency_ms": round(latency_ms, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                    "incomplete": type(exc).__name__ == "RuntimeError",
                }
            )
            self.store.log_step(
                experiment_id,
                "round2_error",
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


def run_round2() -> Path:
    settings = load_settings(
        db_path=DATA_DIR / "block15_round2.sqlite3",
        jsonl_path=DATA_DIR / "block15_round2_events.jsonl",
    )
    settings.ensure_data_dir()
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

        run_id = "round2_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DATA_DIR / f"block15_round2_results_{run_id}.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

        runner = Round2Runner(
            settings, client, store, orchestrator, digest, model_info, run_id
        )
        record: dict = {
            "run_id": run_id,
            "started_at": _now(),
            "round": 2,
            "model": settings.model,
            "model_digest": digest,
            "model_info": model_info,
            "settings": {
                "think": settings.think,
                "num_ctx": settings.context_limit,
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "repeat_penalty": settings.repeat_penalty,
                "seed": settings.seed,
                "keep_alive": settings.keep_alive,
                "num_predict_tool_decision": 300,
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
            "free_mb_end": None,
            "stopped_early": False,
            "stop_reason": None,
        }

        for index, task in enumerate(RUN_ORDER, start=1):
            free_before = free_physical_mb()
            elapsed = runner.elapsed_s
            if runner.calls_used >= CALL_LIMIT or elapsed > TASK_START_CUTOFF_S:
                record["stopped_early"] = True
                record["stop_reason"] = (
                    f"call limit {CALL_LIMIT} or runtime cutoff "
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
        output_path.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"results: {output_path}", flush=True)
        print(f"sqlite: {settings.db_path}", flush=True)
        print(f"jsonl: {settings.jsonl_path}", flush=True)
        print(
            f"calls_used={runner.calls_used} runtime_s={runner.elapsed_s:.1f}",
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
    parser = argparse.ArgumentParser(description="Block 1.5 Round 2 runner")
    parser.add_argument(
        "--list", action="store_true", help="list Round 2 task IDs and exit"
    )
    args = parser.parse_args(argv)
    if args.list:
        for task in RUN_ORDER:
            print(
                f"{task.id}\t{task.group}\t{task.category}\t"
                f"{task.protocol}\t{task.mode}"
            )
        return 0
    run_round2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
