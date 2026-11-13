"""Small, explicitly labelled diagnostics for Block 1.5.

These are not additional benchmark tasks.  They test two observations from the
main run:

1. Whether putting ``reasoning`` before ``answer`` in the JSON schema removes
   the contradictions seen in A1/A2/B2.
2. Whether E2 can be completed when the tool request is explicit instead of
   optional (the main E2 run failed while formatting its tool decision).

The same local client, tool orchestrator, verifier and store are used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from block15.run_benchmark import (
    DATA_DIR,
    BenchmarkRunner,
    _now,
    _validate_answer,
    free_physical_mb,
    independent_check,
)
from block15.tasks import OUTPUT_INSTRUCTION, SYSTEM_PROMPT, TASKS
from mdl.config import load_settings
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient
from mdl.orchestrator import ToolOrchestrator

REASONING_FIRST_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reasoning", "answer", "confidence", "uncertainty"],
    "properties": {
        "reasoning": {"type": "string", "minLength": 1, "maxLength": 3000},
        "answer": {"type": "string", "minLength": 1, "maxLength": 1200},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "string", "maxLength": 1000},
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


def _reasoning_first_instruction() -> str:
    return (
        "\n\nReturn a JSON object with exactly these fields, in this order: "
        "reasoning (string), answer (string), confidence (number from 0 to 1), "
        "uncertainty (string). Reason first, then give the final answer. Put "
        "every string on one line; do not include literal newline characters "
        "inside string values. Do not use markdown."
    )


def run_diagnostics() -> Path:
    settings = load_settings(
        db_path=DATA_DIR / "block15.sqlite3",
        jsonl_path=DATA_DIR / "block15_events.jsonl",
    )
    settings.ensure_data_dir()
    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    orchestrator = ToolOrchestrator(settings.tool_timeout_s)
    try:
        model_info = client.model_info()
        if model_info is None:
            raise SystemExit(f"model {settings.model!r} is not installed")
        digest = model_info.get("digest")
        if not digest:
            raise SystemExit("model digest is unavailable")
        run_id = "diag_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DATA_DIR / f"block15_diagnostics_{run_id}.json"
        runner = BenchmarkRunner(
            settings, client, store, orchestrator, digest, model_info, run_id
        )
        record: dict = {
            "run_id": run_id,
            "started_at": _now(),
            "model": settings.model,
            "model_digest": digest,
            "free_mb_start": free_physical_mb(),
            "diagnostics": [],
        }

        def new_experiment(diag_id: str, task_meta: dict) -> str:
            experiment_id = store.create_experiment(
                seed=diag_id,
                model=settings.model,
                model_digest=digest,
                parameters={
                    **runner._settings_record(1200),
                    "run_id": run_id,
                    "diagnostic": True,
                    "diagnostic_id": diag_id,
                },
                context_limit=settings.context_limit,
            )
            store.log_event(
                experiment_id,
                "benchmark_diagnostic",
                {"diagnostic_id": diag_id, "task": task_meta},
            )
            return experiment_id

        # ------------------------------------------------------------------
        # 1. Reasoning-first schema for A1 and B2
        # ------------------------------------------------------------------
        for task in (TASKS[0], TASKS[4]):
            diag_id = f"{task.id}_reasoning_first"
            experiment_id = new_experiment(diag_id, task.metadata())
            token_usage = {
                "prompt_eval_count": 0,
                "eval_count": 0,
                "model_calls": 0,
            }
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": task.prompt + _reasoning_first_instruction(),
                },
            ]
            item = {
                "diagnostic_id": diag_id,
                "experiment_id": experiment_id,
                "task": task.metadata(),
                "schema_order": "reasoning_first",
                "status": "running",
            }
            try:
                parsed, call = runner._call(
                    experiment_id,
                    "final_answer",
                    messages,
                    REASONING_FIRST_SCHEMA,
                    1200,
                    token_usage,
                )
                answer = _validate_answer(parsed)
                verification = independent_check(task, answer, None)
                item.update(
                    {
                        "status": "completed",
                        "answer": answer,
                        "verification": verification,
                        "call": call,
                        "tokens": token_usage,
                    }
                )
                store.set_experiment_fields(
                    experiment_id,
                    hypothesis_json=task.metadata(),
                    interpretation_json=answer,
                    verification_json=verification,
                )
                store.finish_experiment(
                    experiment_id,
                    "completed",
                    token_usage=token_usage,
                )
            except Exception as exc:  # noqa: BLE001
                item.update(
                    {
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                        "tokens": token_usage,
                    }
                )
                store.finish_experiment(
                    experiment_id,
                    "failed",
                    error=str(exc),
                    token_usage=token_usage,
                )
            record["diagnostics"].append(item)
            output_path.write_text(
                json.dumps(record, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            print(f"{diag_id}: {item['status']}", flush=True)

        # ------------------------------------------------------------------
        # 2. E2 with an explicit tool request
        # ------------------------------------------------------------------
        task = TASKS[10]
        diag_id = "E2_tool_divisibility_forced"
        experiment_id = new_experiment(diag_id, task.metadata())
        token_usage = {
            "prompt_eval_count": 0,
            "eval_count": 0,
            "model_calls": 0,
        }
        item = {
            "diagnostic_id": diag_id,
            "experiment_id": experiment_id,
            "task": task.metadata(),
            "protocol": "explicit tool request, then interpretation",
            "status": "running",
        }
        try:
            tool_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Use the available symbolic_expand tool to expand the "
                        "polynomial (x + y)^5 - (x^5 + y^5). Return a JSON object "
                        "with exactly these fields: tool (string, must be "
                        "'symbolic_expand') and arguments (object with expression "
                        "string). Use only integers, variable names, parentheses "
                        "and + - * **."
                    ),
                },
            ]
            tool_decision, tool_call = runner._call(
                experiment_id,
                "tool_request",
                tool_messages,
                DIRECT_TOOL_SCHEMA,
                300,
                token_usage,
            )
            expression = (
                tool_decision.get("arguments", {}).get("expression", "")
                if isinstance(tool_decision.get("arguments"), dict)
                else ""
            )
            tool_record = runner._execute_tool(
                experiment_id,
                {
                    "use_tool": True,
                    "expression": expression,
                    "reason": "explicit diagnostic tool request",
                },
            )
            final_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        task.prompt
                        + "\n\nThe symbolic_expand record is:\n"
                        + json.dumps(tool_record, ensure_ascii=True)
                        + OUTPUT_INSTRUCTION
                    ),
                },
            ]
            final_parsed, final_call = runner._call(
                experiment_id,
                "final_answer",
                final_messages,
                REASONING_FIRST_SCHEMA,
                1200,
                token_usage,
            )
            answer = _validate_answer(final_parsed)
            verification = independent_check(task, answer, tool_record)
            item.update(
                {
                    "status": "completed",
                    "tool_decision": tool_decision,
                    "tool": tool_record,
                    "answer": answer,
                    "verification": verification,
                    "calls": [tool_call, final_call],
                    "tokens": token_usage,
                }
            )
            store.set_experiment_fields(
                experiment_id,
                hypothesis_json=task.metadata(),
                tool_request_json=tool_decision,
                tool_result_json=tool_record.get("result"),
                interpretation_json=answer,
                verification_json=verification,
            )
            store.finish_experiment(
                experiment_id,
                "completed",
                token_usage=token_usage,
            )
        except Exception as exc:  # noqa: BLE001
            item.update(
                {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "tokens": token_usage,
                }
            )
            store.finish_experiment(
                experiment_id,
                "failed",
                error=str(exc),
                token_usage=token_usage,
            )
        record["diagnostics"].append(item)
        record["finished_at"] = _now()
        record["free_mb_end"] = free_physical_mb()
        output_path.write_text(
            json.dumps(record, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        print(f"{diag_id}: {item['status']}", flush=True)
        print(f"diagnostics: {output_path}", flush=True)
        return output_path
    finally:
        client.close()
        store.close()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    run_diagnostics()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
