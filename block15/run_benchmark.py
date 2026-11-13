"""Sequential Block 1.5 benchmark runner.

The runner uses only existing Block 1 components:

* ``mdl.OllamaClient`` for single-flight LFM3 inference;
* ``mdl.ToolOrchestrator`` for the allowlisted symbolic_expand tool;
* ``mdl.verify_symbolic_expand`` for independent expansion checks;
* ``mdl.ResearchStore`` for SQLite plus append-only hash-chained JSONL.

It writes to separate ``data/block15*`` files so the Block 1 experiment records
are never overwritten.  All model calls are sequential.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.tasks import (
    ANSWER_SCHEMA,
    OUTPUT_INSTRUCTION,
    RUN_ORDER,
    SYSTEM_PROMPT,
    TASKS,
    TOOL_DECISION_INSTRUCTION,
    TOOL_DECISION_SCHEMA,
    Task,
)
from mdl.config import Settings, load_settings
from mdl.errors import MdlError, ModelError, ModelOutputError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient
from mdl.orchestrator import ToolOrchestrator
from mdl.verifier import verify_symbolic_expand

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MIN_FREE_MB = 450.0


# ---------------------------------------------------------------------------
# Small platform helpers
# ---------------------------------------------------------------------------


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_physical_mb() -> float | None:
    if not hasattr(ctypes, "windll"):
        return None
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.ullAvailPhys / (1024 * 1024), 1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# Validation and independent checks
# ---------------------------------------------------------------------------


def _validate_answer(parsed: dict) -> dict:
    required = ("answer", "reasoning", "confidence", "uncertainty")
    missing = [name for name in required if name not in parsed]
    if missing:
        raise ValueError(f"answer JSON is missing fields: {missing}")
    if not isinstance(parsed["answer"], str) or not parsed["answer"].strip():
        raise ValueError("answer must be a non-empty string")
    if not isinstance(parsed["reasoning"], str):
        raise ValueError("reasoning must be a string")
    if not isinstance(parsed["uncertainty"], str):
        raise ValueError("uncertainty must be a string")
    confidence = parsed["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return {
        "answer": parsed["answer"],
        "reasoning": parsed["reasoning"],
        "confidence": confidence,
        "uncertainty": parsed["uncertainty"],
    }


def _contains_int(text: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", text) is not None


def _formula_looks_quadratic(text: str) -> bool:
    compact = re.sub(r"\s+", "", text.lower())
    return any(
        token in compact
        for token in ("2n^2-2n+1", "2n**2-2n+1", "2n²-2n+1", "2n^2−2n+1")
    )


def independent_check(task: Task, answer: dict, tool: dict | None) -> dict:
    """Compute an independent ground truth and compare where objective.

    The check is deliberately separate from the model.  For proof and
    hypothesis tasks the final logical judgement remains a manual rubric step;
    the machine check only verifies the underlying mathematical facts.
    """

    text = answer["answer"]
    base = {
        "method": task.verification,
        "expected": task.expected,
        "observed_answer": text,
        "observed_confidence": answer["confidence"],
    }

    if task.id in {"A1_coefficient_baseline", "A1_coefficient_tool", "A1_coefficient_repeat"}:
        x = sympy.Symbol("x")
        coefficient = sympy.expand((x**2 + 3 * x + 2) * (x + 1) ** 6).coeff(x, 5)
        passed = _contains_int(text, int(coefficient))
        return {
            **base,
            "computed_expected": str(coefficient),
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer contains the independently computed coefficient"
            if passed
            else "answer does not contain the independently computed coefficient",
        }

    if task.id == "A2_difference_terms":
        x = sympy.Symbol("x")
        expanded = sympy.expand((x + 1) ** 6 - (x - 1) ** 6)
        terms = sympy.Add.make_args(expanded)
        coefficient_sum = sympy.expand(expanded).subs(x, 1)
        passed = _contains_int(text, len(terms)) and _contains_int(
            text, int(coefficient_sum)
        )
        return {
            **base,
            "computed_expected": {
                "nonzero_terms": len(terms),
                "coefficient_sum": int(coefficient_sum),
                "expanded": str(expanded),
            },
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer contains both computed values"
            if passed
            else "answer does not contain both computed values",
        }

    if task.id == "B1_counterexample":
        first = None
        first_value = None
        for n in range(0, 1001):
            value = n * n + n + 17
            if not sympy.isprime(value):
                first = n
                first_value = value
                break
        passed = first is not None and _contains_int(text, first)
        return {
            **base,
            "computed_expected": {"n": first, "value": first_value},
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer contains the first counterexample index"
            if passed
            else "answer does not contain the first counterexample index",
        }

    if task.id == "B2_sequence_rule":
        n = sympy.Symbol("n")
        data = [(i + 1, term) for i, term in enumerate([1, 5, 13, 25, 41])]
        poly = sympy.interpolate(data, n)
        next_values = [int(poly.subs(n, i)) for i in (6, 7)]
        passed = all(_contains_int(text, value) for value in next_values)
        formula_ok = _formula_looks_quadratic(text + " " + answer["reasoning"])
        return {
            **base,
            "computed_expected": {
                "next_two_terms": next_values,
                "interpolated_polynomial": str(sympy.expand(poly)),
            },
            "status": (
                "objective_pass"
                if passed and formula_ok
                else "objective_fail"
            ),
            "detail": (
                "answer contains both next terms and a quadratic formula"
                if passed and formula_ok
                else "answer misses a next term or the expected quadratic form"
            ),
        }

    if task.id == "C1_hypothesis_primality":
        failures = []
        for n in range(1, 101):
            value = n * n - n + 41
            if not sympy.isprime(value):
                failures.append((n, value, sympy.factorint(value)))
        return {
            **base,
            "known_failure": failures[:3],
            "status": "manual_review_required",
            "detail": "hypothesis quality and falsifiability require rubric review",
        }

    if task.id == "C2_hypothesis_last_digit":
        residues = {n: (n**5 - n) % 10 for n in range(-20, 21)}
        return {
            **base,
            "residue_check_all_zero": all(value == 0 for value in residues.values()),
            "factorization": str(sympy.factor(sympy.Symbol("n") ** 5 - sympy.Symbol("n"))),
            "status": "manual_review_required",
            "detail": "hypothesis quality requires rubric review",
        }

    if task.id == "D1_even_proof":
        parity_ok = all((n * n + n) % 2 == 0 for n in range(-200, 201))
        return {
            **base,
            "parity_check_all_even": parity_ok,
            "status": "manual_review_required",
            "detail": "proof validity requires rubric review",
        }

    if task.id == "D2_false_primality_proof":
        counterexample = None
        for n in range(1, 101):
            value = n * n + n + 41
            if not sympy.isprime(value):
                counterexample = (n, value, sympy.factorint(value))
                break
        return {
            **base,
            "first_counterexample": counterexample,
            "status": "manual_review_required",
            "detail": "proof or counterexample validity requires rubric review",
        }

    if task.id == "E1_tool_coefficient":
        x = sympy.Symbol("x")
        coefficient = sympy.expand((2 * x - 3) ** 9).coeff(x, 7)
        passed = _contains_int(text, int(coefficient))
        return {
            **base,
            "computed_expected": str(coefficient),
            "tool": tool,
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer contains the independently computed coefficient"
            if passed
            else "answer does not contain the independently computed coefficient",
        }

    if task.id == "E2_tool_divisibility":
        x, y = sympy.symbols("x y")
        expression = (x + y) ** 5 - (x**5 + y**5)
        divisor = 5 * x * y * (x + y)
        quotient = sympy.simplify(expression / divisor)
        remainder = sympy.simplify(expression - divisor * quotient)
        passed = remainder == 0 and (
            "yes" in text.lower() or "divisible" in text.lower()
        )
        return {
            **base,
            "computed_quotient": str(quotient),
            "remainder": str(remainder),
            "tool": tool,
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer states divisibility and the remainder is zero"
            if passed
            else "answer does not clearly state the verified divisibility",
        }

    if task.id == "F1_error_correction":
        x = sympy.Symbol("x")
        correct = sympy.expand((x + 1) ** 2)
        compact = re.sub(r"\s+", "", text.lower())
        passed = (
            ("incorrect" in text.lower() or "not correct" in text.lower())
            and ("2x" in compact or "2*x" in compact)
        )
        return {
            **base,
            "computed_expected": str(correct),
            "status": "objective_pass" if passed else "objective_fail",
            "detail": "answer rejects the misconception and gives the linear term"
            if passed
            else "answer does not clearly reject the misconception or give 2x",
        }

    if task.id == "F2_revise_conclusion":
        return {
            **base,
            "counterexample_check": 41**2 == 1681,
            "status": "manual_review_required",
            "detail": "scope-of-counterexample reasoning requires rubric review",
        }

    return {
        **base,
        "status": "manual_review_required",
        "detail": "no automated check registered for this task",
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class BenchmarkRunner:
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
        self.settings = settings
        self.client = client
        self.store = store
        self.orchestrator = orchestrator
        self.digest = digest
        self.model_info = model_info
        self.run_id = run_id

    def _settings_record(self, num_predict: int) -> dict:
        return {
            "model": self.settings.model,
            "num_ctx": self.settings.context_limit,
            "num_predict": int(num_predict),
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "repeat_penalty": self.settings.repeat_penalty,
            "seed": self.settings.seed,
            "think": self.settings.think,
            "keep_alive": self.settings.keep_alive,
        }

    def _call(
        self,
        experiment_id: str,
        phase: str,
        messages: list[dict],
        schema: dict,
        num_predict: int,
        token_usage: dict,
    ) -> tuple[dict, dict]:
        started = perf_counter()
        settings = self._settings_record(num_predict)
        try:
            response = self.client.chat_json(
                messages, schema, num_predict=num_predict
            )
        except (ModelError, ModelOutputError) as exc:
            latency_ms = (perf_counter() - started) * 1000.0
            self.store.log_step(
                experiment_id,
                "model_call",
                "error",
                {
                    "phase": phase,
                    "messages": messages,
                    "schema": schema,
                    "settings": settings,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                latency_ms=latency_ms,
            )
            raise

        latency_ms = (perf_counter() - started) * 1000.0
        token_usage["model_calls"] += 1
        token_usage["prompt_eval_count"] += int(response.prompt_eval_count or 0)
        token_usage["eval_count"] += int(response.eval_count or 0)
        status = "ok" if response.done_reason != "length" else "truncated"
        record = {
            "phase": phase,
            "messages": messages,
            "schema": schema,
            "settings": settings,
            "raw_content": response.content,
            "parsed": response.parsed,
            "done_reason": response.done_reason,
            "prompt_eval_count": response.prompt_eval_count,
            "eval_count": response.eval_count,
            "wall_ms": round(response.wall_ms, 2),
            "latency_ms": round(latency_ms, 2),
        }
        self.store.log_step(
            experiment_id,
            "model_call",
            status,
            record,
            latency_ms=latency_ms,
        )
        return response.parsed, record

    def _execute_tool(self, experiment_id: str, decision: dict) -> dict:
        use_tool = bool(decision.get("use_tool"))
        expression = decision.get("expression", "")
        if not isinstance(expression, str):
            expression = ""
        record: dict = {
            "use_tool": use_tool,
            "requested_expression": expression,
            "decision_reason": decision.get("reason", ""),
            "status": "not_used",
        }
        if not use_tool:
            self.store.log_step(
                experiment_id, "tool_decision", "not_used", record
            )
            return record
        if not expression.strip():
            record["status"] = "invalid_request"
            record["error"] = "use_tool was true but expression was empty"
            self.store.log_step(
                experiment_id, "tool_decision", "invalid_request", record
            )
            return record

        request = {
            "tool": "symbolic_expand",
            "arguments": {"expression": expression},
        }
        try:
            validated = self.orchestrator.validate(request)
        except MdlError as exc:
            record["status"] = "rejected"
            record["error"] = str(exc)
            self.store.log_step(
                experiment_id,
                "tool_decision",
                "rejected",
                {**record, "request": request},
            )
            return record

        record["status"] = "accepted"
        record["request"] = validated.model_dump()
        self.store.log_step(
            experiment_id, "tool_decision", "accepted", record
        )
        try:
            execution = self.orchestrator.execute(validated)
        except MdlError as exc:
            record["status"] = "execution_error"
            record["error"] = str(exc)
            self.store.log_step(
                experiment_id, "tool_execution", "error", record
            )
            return record

        verification = verify_symbolic_expand(
            validated.arguments.expression, execution.result
        )
        record.update(
            {
                "status": "executed",
                "result": execution.result.model_dump(),
                "tool_latency_ms": round(execution.latency_ms, 2),
                "verification": verification.to_dict(),
            }
        )
        self.store.log_step(
            experiment_id,
            "tool_execution",
            "ok",
            {
                "request": validated.model_dump(),
                "result": execution.result.model_dump(),
                "verification": verification.to_dict(),
            },
            latency_ms=execution.latency_ms,
        )
        self.store.set_experiment_fields(
            experiment_id,
            tool_request_json=validated.model_dump(),
            tool_result_json=execution.result.model_dump(),
            verification_json=verification.to_dict(),
        )
        return record

    def run_task(self, task: Task) -> dict:
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
                "task_id": task.id,
                "category": task.category,
                "difficulty": task.difficulty,
                "mode": task.mode,
                "repeat_of": task.repeat_of,
                "variant_of": task.variant_of,
            },
            context_limit=self.settings.context_limit,
        )
        self.store.log_event(
            experiment_id,
            "benchmark_task",
            {
                "task": task.metadata(),
                "model_info": self.model_info,
                "started_at": _now(),
            },
        )

        calls: list[dict] = []
        tool_record: dict | None = None
        result: dict = {
            "run_id": self.run_id,
            "task": task.metadata(),
            "experiment_id": experiment_id,
            "status": "running",
            "calls": calls,
            "tool": None,
            "final_answer": None,
            "verification": None,
            "latency_ms": None,
            "tokens": token_usage,
            "error": None,
        }

        try:
            if task.mode == "tool":
                decision_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": task.prompt + TOOL_DECISION_INSTRUCTION,
                    },
                ]
                decision, decision_call = self._call(
                    experiment_id,
                    "tool_decision",
                    decision_messages,
                    TOOL_DECISION_SCHEMA,
                    300,
                    token_usage,
                )
                calls.append(decision_call)
                tool_record = self._execute_tool(experiment_id, decision)
                result["tool"] = tool_record
                tool_context = json.dumps(tool_record, ensure_ascii=True)
                final_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            task.prompt
                            + "\n\nThe symbolic_expand record is:\n"
                            + tool_context
                            + OUTPUT_INSTRUCTION
                        ),
                    },
                ]
            else:
                final_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": task.prompt + OUTPUT_INSTRUCTION,
                    },
                ]

            final_parsed, final_call = self._call(
                experiment_id,
                "final_answer",
                final_messages,
                ANSWER_SCHEMA,
                1200,
                token_usage,
            )
            calls.append(final_call)
            final_answer = _validate_answer(final_parsed)
            result["final_answer"] = final_answer
            verification = independent_check(task, final_answer, tool_record)
            result["verification"] = verification
            self.store.log_step(
                experiment_id,
                "independent_verification",
                verification["status"],
                verification,
            )
            self.store.set_experiment_fields(
                experiment_id,
                hypothesis_json=task.metadata(),
                interpretation_json=final_answer,
                context_json={
                    "task": task.metadata(),
                    "tool": tool_record,
                    "verification": verification,
                    "calls": calls,
                },
                verification_json=verification,
            )
            latency_ms = (perf_counter() - started) * 1000.0
            result["latency_ms"] = round(latency_ms, 2)
            result["status"] = "completed"
            self.store.finish_experiment(
                experiment_id,
                "completed",
                latency_ms=latency_ms,
                token_usage=token_usage,
            )
        except Exception as exc:  # noqa: BLE001 - a failed task must be recorded
            latency_ms = (perf_counter() - started) * 1000.0
            result["status"] = "failed"
            result["latency_ms"] = round(latency_ms, 2)
            result["error"] = f"{type(exc).__name__}: {exc}"
            self.store.log_step(
                experiment_id,
                "benchmark_error",
                "failed",
                {
                    "task_id": task.id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
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


def run_benchmark(only: list[str] | None = None) -> Path:
    settings = load_settings(
        db_path=DATA_DIR / "block15.sqlite3",
        jsonl_path=DATA_DIR / "block15_events.jsonl",
    )
    settings.ensure_data_dir()
    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    orchestrator = ToolOrchestrator(settings.tool_timeout_s)
    try:
        if not client.health():
            raise SystemExit("Ollama is not reachable at the configured URL")
        model_info = client.model_info()
        if model_info is None:
            raise SystemExit(f"model {settings.model!r} is not installed")
        digest = model_info.get("digest")
        if not digest:
            raise SystemExit("model digest is unavailable; refusing to run")

        selected = [task for task in RUN_ORDER if not only or task.id in only]
        if not selected:
            raise SystemExit("no matching tasks selected")

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DATA_DIR / f"block15_results_{run_id}.json"
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

        runner = BenchmarkRunner(
            settings, client, store, orchestrator, digest, model_info, run_id
        )
        run_record: dict = {
            "run_id": run_id,
            "started_at": _now(),
            "model": settings.model,
            "model_digest": digest,
            "model_info": model_info,
            "settings": runner._settings_record(1200),
            "task_count": len(selected),
            "tasks": [],
            "free_mb_start": free_physical_mb(),
            "free_mb_end": None,
            "stopped_early": False,
            "stop_reason": None,
        }

        for index, task in enumerate(selected, start=1):
            free_before = free_physical_mb()
            print(
                f"[{index}/{len(selected)}] {task.id} "
                f"({task.category}, {task.difficulty}, {task.mode}) "
                f"free_MB={free_before}",
                flush=True,
            )
            if free_before is not None and free_before < MIN_FREE_MB:
                run_record["stopped_early"] = True
                run_record["stop_reason"] = (
                    f"free physical memory below {MIN_FREE_MB} MB"
                )
                print(run_record["stop_reason"], flush=True)
                break
            task_result = runner.run_task(task)
            run_record["tasks"].append(task_result)
            free_after = free_physical_mb()
            print(
                f"    status={task_result['status']} "
                f"latency_s={(task_result['latency_ms'] or 0) / 1000:.1f} "
                f"tokens={task_result['tokens']} free_MB={free_after}",
                flush=True,
            )
            # Persist after every task so an interrupted run remains inspectable.
            run_record["free_mb_end"] = free_after
            run_record["updated_at"] = _now()
            output_path.write_text(
                json.dumps(run_record, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

        run_record["finished_at"] = _now()
        run_record["free_mb_end"] = free_physical_mb()
        output_path.write_text(
            json.dumps(run_record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"results: {output_path}", flush=True)
        print(f"sqlite: {settings.db_path}", flush=True)
        print(f"jsonl: {settings.jsonl_path}", flush=True)
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
    parser = argparse.ArgumentParser(description="Block 1.5 sequential benchmark")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="run only the named task IDs (default: all)",
    )
    parser.add_argument(
        "--list", action="store_true", help="list task IDs and exit"
    )
    args = parser.parse_args(argv)
    if args.list:
        for task in RUN_ORDER:
            print(
                f"{task.id}\t{task.category}\t{task.difficulty}\t{task.mode}"
            )
        return 0
    try:
        run_benchmark(args.only)
        return 0
    except KeyboardInterrupt:
        return 130
    except MdlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
