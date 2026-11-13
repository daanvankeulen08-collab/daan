"""Labelled Round 2 recovery run.

The primary Round 2 run stopped ``R2B2_tool_required`` with a runner-side
``NameError`` before any model call.  This script reruns only that task under
the same prompt and settings, logging to the same Round 2 SQLite/JSONL store
but writing a new, separately named result file.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from block15.round2_tasks import RUN_ORDER, Round2Task
from block15.round2 import (
    CALL_LIMIT,
    Round2Runner,
    free_physical_mb,  # imported for compatibility with runner conventions
)
from mdl.config import load_settings
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient
from mdl.orchestrator import ToolOrchestrator


def _now() -> str:
    from block15.run_benchmark import _now as run_benchmark_now

    return run_benchmark_now()


def run_recovery(task_ids: list[str]) -> Path:
    settings = load_settings(
        db_path=Path(__file__).resolve().parents[1] / "data" / "block15_round2.sqlite3",
        jsonl_path=Path(__file__).resolve().parents[1]
        / "data"
        / "block15_round2_events.jsonl",
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

        selected = [task for task in RUN_ORDER if task.id in task_ids]
        if not selected:
            raise SystemExit(f"no matching tasks for recovery: {task_ids}")

        recovery_id = "round2_recovery_" + datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        output_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / f"block15_round2_recovery_{recovery_id}.json"
        )
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

        runner = Round2Runner(
            settings, client, store, orchestrator, digest, model_info, recovery_id
        )
        # Respect the overall Round 2 call budget including the primary run.
        previous_calls = 15
        if runner.calls_used + previous_calls > CALL_LIMIT:
            raise SystemExit("overall Round 2 call limit would be exceeded")
        runner.calls_used = previous_calls

        record = {
            "recovery_id": recovery_id,
            "parent_run": "round2_20261110T214854Z",
            "reason": "R2B2_tool_required was skipped by a runner NameError before any model call.",
            "started_at": _now(),
            "model": settings.model,
            "model_digest": digest,
            "previous_calls": previous_calls,
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
            },
            "free_mb_start": free_physical_mb(),
            "results": [],
        }

        for task in selected:
            print(f"[recovery] {task.id}", flush=True)
            task_result = runner.run_task(task)
            record["results"].append(task_result)
            print(
                f"    status={task_result['status']} calls={task_result['tokens']['model_calls']}",
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
            f"calls_used_total={runner.calls_used} runtime_s={runner.elapsed_s:.1f}",
            flush=True,
        )
        return output_path
    finally:
        client.close()
        store.close()


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    run_recovery(["R2B2_tool_required"])
