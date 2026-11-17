"""Tool-transfer study runner: L0_REAL then L0_SHAM, single-flight.

All measurement logic lives in the FROZEN scorer block15.tool_transfer_score,
whose git blob hash is pinned in PREREG_TOOL_TRANSFER.md before generation.
This module only does: build prompts (via scorer), make two calls, execute or
sham the tool, persist raw cells, then call the scorer to derive fields and
analyze. It never re-scores with modified logic.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

from block15 import order_v2_research as O
from block15 import skill_tools as T
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_tasks as TT
from block15.contract_v2 import DERIVATION_FIRST_V2
from block15.run_benchmark import DATA_DIR, _now, free_physical_mb
from mdl.config import load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL, MODEL_DIGEST, QUANTIZATION = O.MODEL, O.MODEL_DIGEST, O.QUANTIZATION
NUM_CTX, TEMPERATURE = O.NUM_CTX, O.TEMPERATURE
TOP_P, REPEAT_PENALTY, SEED, KEEP_ALIVE, THINK = (
    O.TOP_P, O.REPEAT_PENALTY, O.SEED, O.KEEP_ALIVE, O.THINK
)
NUM_PREDICT = 1200
NUM_PREDICT_REQUEST = 300
MAX_CALLS = 130
MAX_RUNTIME_S = 5400.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 120

STORE_DB_NAME = "block15_tool_transfer.sqlite3"
STORE_JSONL_NAME = "block15_tool_transfer_events.jsonl"
RESULTS_PREFIX = "block15_tool_transfer_results_"
SUMMARY_NAME = "block15_tool_transfer_summary.json"

CONDITIONS = ("L0_REAL", "L0_SHAM")
SHAM_RESULT = {"status": "unavailable"}
TASKS = TT.TASKS
TASK_BY_ID = {t.id: t for t in TASKS}
GT = {t.id: t.truth() for t in TASKS}


def scorer_blob_hash() -> str | None:
    return O.git_blob_sha256(Path(__file__).parent / "tool_transfer_score.py")


def tool_schema_block() -> str:
    return (
        "A tool is available. Return a tool-request object matching this schema "
        "(or null if you will not use it):\n"
        + json.dumps(T.TOOL_SCHEMA, ensure_ascii=True, separators=(",", ":"))
    )


class GuardStop(RuntimeError):
    pass


def _settings():
    return load_settings(
        model=MODEL, db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=NUM_CTX, think=THINK, temperature=TEMPERATURE,
        top_p=TOP_P, repeat_penalty=REPEAT_PENALTY, seed=SEED, keep_alive=KEEP_ALIVE,
    )


def _verify_model(client):
    if not client.health():
        raise SystemExit("Ollama not reachable")
    info = client.model_info()
    if info is None or info.get("digest") != MODEL_DIGEST:
        raise SystemExit("model digest mismatch")
    if (info.get("details") or {}).get("quantization_level") != QUANTIZATION:
        raise SystemExit("quantization mismatch")
    return str(info["digest"])


def _call(client, messages, schema, num_predict, state):
    state["guard"]()
    state["calls"] += 1
    started = perf_counter()
    raw = done = pe = ec = None
    pv, se, ts = "unknown", None, None
    status, err = "error", None
    try:
        r = client.chat_json(messages, schema, num_predict=num_predict)
        raw, done = r.content, r.done_reason
        pe, ec = r.prompt_eval_count, r.eval_count
        pv, se, ts = r.protocol_variant, r.schema_enforced, r.think_sent
        status = "ok"
    except ModelOutputError as exc:
        raw, done = exc.raw_content, exc.done_reason
        pe, ec = exc.prompt_eval_count, exc.eval_count
        pv, se, ts = exc.protocol_variant, exc.schema_enforced, exc.think_sent
        err = f"{type(exc).__name__}: {exc}"; status = "output_error"
    except ModelTimeoutError as exc:
        err = f"{type(exc).__name__}: {exc}"; status = "timeout"
    except ModelError as exc:
        err = f"{type(exc).__name__}: {exc}"; status = "model_error"
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"; status = "error"
    return {
        "content": raw, "done_reason": done, "prompt_eval_count": pe,
        "eval_count": ec, "protocol_variant": pv, "schema_enforced": se,
        "think_sent": ts, "status": status, "error": err,
        "latency_ms": round((perf_counter() - started) * 1000.0, 2),
    }


def run_cell(client, store, exp_id, task, cond, state):
    task = TASK_BY_ID[task.id]
    # Call 1: tool request. Prompt is identical in REAL and SHAM.
    r1_prompt = SC.build_r1_prompt(task, tool_schema_block())
    r1 = _call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                        {"role": "user", "content": r1_prompt}],
               T.TOOL_SCHEMA, NUM_PREDICT_REQUEST, state)
    req_obj = SC.parse_request(r1["content"])
    valid, normalized = SC.validate_request(req_obj)
    requested = bool(req_obj and req_obj.get("tool_request") is not None)
    pcorr = SC.parameters_correct(normalized, task)

    # Call 2: append tool result. REAL executes, SHAM returns unavailable.
    if "REAL" in cond and valid and normalized:
        tool_result = T.first_composite_quadratic(**normalized["arguments"])
    else:
        tool_result = dict(SHAM_RESULT)
    r2_prompt = SC.build_r2_prompt(task, tool_result)
    r2 = _call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                        {"role": "user", "content": r2_prompt}],
              DERIVATION_FIRST_V2, NUM_PREDICT, state)
    parsed = O.fresh_parse(r2["content"])
    answer = parsed.get("final_answer") if parsed else None
    used = SC.tool_result_used(answer, tool_result, "REAL" if "REAL" in cond else "SHAM",
                               valid, pcorr)

    row = {
        "task_id": task.id, "task_kind": task.kind, "condition": cond,
        "call1": r1, "call2": r2,
        "call1_prompt_sha256": hashlib.sha256(r1_prompt.encode()).hexdigest(),
        "call2_prompt_sha256": hashlib.sha256(r2_prompt.encode()).hexdigest(),
        "r1_prompt": r1_prompt, "raw_content": r2["content"],
        "raw_request": r1["content"], "tool_request": normalized,
        "tool_requested": requested, "tool_request_valid": valid,
        "parameters_correct": pcorr, "tool_result": tool_result,
        "tool_result_used": used, "answer_text": answer,
        "emitted_key_order": list(O.emitted_key_order(parsed)) if parsed else [],
        "matches_own_schema": bool(parsed) and O.emission_order_provenance(
            parsed, DERIVATION_FIRST_V2, O.ANSWER_FIRST_V2)["matches_own_schema"],
        "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
        "validate_v2_violations": O.validate_v2(parsed, DERIVATION_FIRST_V2)[1] if parsed else ["unparseable"],
        "done_reason": r2["done_reason"],
        "prompt_eval_count": r2["prompt_eval_count"], "eval_count": r2["eval_count"],
        "confidence_raw": parsed.get("confidence") if parsed else None,
    }
    # ALL derived/scored fields come from the FROZEN scorer.
    scored = SC.score_cell(row, task, GT[task.id])
    row.update(scored)
    store.log_step(exp_id, "tool_transfer_cell", cond, row, latency_ms=r2["latency_ms"])
    print(f"    {cond:<8} {task.id:<26} kind={task.kind[:11]:<11} "
          f"req={int(requested)} pcorr={int(pcorr)} used={int(used)} "
          f"pass={int(row['primary_correct'])} done={r2['done_reason']} "
          f"lat={(r1['latency_ms']+r2['latency_ms'])/1000:.1f}s", flush=True)
    return row


def _ts():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_study():
    if glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: tool-transfer result files exist")
    sha = scorer_blob_hash()
    if sha is None:
        raise SystemExit("cannot resolve frozen scorer git blob hash")
    tasks_check = TT.verify_tasks()
    frozen = O.verify_protected()
    if not frozen["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed")
    settings = _settings(); settings.ensure_data_dir()
    ts = _ts()
    paths = {c: DATA_DIR / f"{RESULTS_PREFIX}{c}_{ts}.json" for c in CONDITIONS}
    for p in paths.values():
        if p.exists():
            raise SystemExit(f"refusing to overwrite {p}")
    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    state = {"calls": 0, "started": perf_counter(), "free_min": None, "guard": None}

    def guard():
        if state["calls"] + 1 > MAX_CALLS:
            raise GuardStop("call budget reached")
        if perf_counter() - state["started"] >= MAX_RUNTIME_S:
            raise GuardStop("runtime budget reached")
        free = free_physical_mb()
        if free is not None:
            state["free_min"] = free if state["free_min"] is None else min(state["free_min"], free)
            if free < MIN_FREE_MB:
                raise GuardStop("free memory below floor")
    state["guard"] = guard

    common = {
        "model": MODEL, "model_digest": None, "started_at": _now(),
        "scorer_blob_sha256": sha, "scorer_version": SC.SCORER_VERSION,
        "copy_surface": SC.COPY_SURFACE,
        "tasks_check": tasks_check,
        "frozen_verification": frozen,
        "task_ids": [t.id for t in TASKS],
        "tool_needed_ids": list(TT.TOOL_NEEDED_IDS),
        "tool_not_needed_ids": list(TT.TOOL_NOT_NEEDED_IDS),
        "sampling": {
            "think": THINK, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
            "num_predict_request": NUM_PREDICT_REQUEST, "temperature": TEMPERATURE,
            "top_p": TOP_P, "repeat_penalty": REPEAT_PENALTY, "seed": SEED,
            "keep_alive": KEEP_ALIVE,
            "system_prompt_sha256": O._sha256_text(O.SYSTEM_PROMPT_V2),
            "schema_sha256": O._sha256_json(DERIVATION_FIRST_V2, sort_keys=False),
        },
        "tool_schema_sha256": O._sha256_json(T.TOOL_SCHEMA, sort_keys=True),
        "guards": {"max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S,
                   "min_free_mb": MIN_FREE_MB, "planned_calls": PLANNED_CALLS},
        "planned_calls": PLANNED_CALLS,
    }
    try:
        digest = _verify_model(client)
        common["model_digest"] = digest
        exp_id = store.create_experiment(
            seed=str(SEED), model=MODEL, model_digest=digest,
            parameters={"kind": "tool_transfer", "planned_calls": PLANNED_CALLS},
            context_limit=NUM_CTX,
        )
        common["experiment_id"] = exp_id
        for cond in CONDITIONS:
            rows = []
            for task in TASKS:
                try:
                    rows.append(run_cell(client, store, exp_id, task, cond, state))
                except GuardStop as exc:
                    common["stopped_early"] = True
                    common["stop_reason"] = str(exc)
                    print(f"STOP: {exc}", flush=True)
                    break
            rec = dict(common)
            rec.update({
                "condition": cond, "results": rows, "run_id": f"tool_transfer_{cond}_{ts}",
                "calls_used_total": state["calls"],
                "runtime_s_total": round(perf_counter() - state["started"], 2),
                "free_mb_min": state["free_min"], "free_mb_end": free_physical_mb(),
                "finished_at": _now(),
            })
            paths[cond].write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"condition {cond} written: {paths[cond].name}", flush=True)
            if common.get("stopped_early"):
                break
    finally:
        client.close(); store.close()
    return paths[CONDITIONS[-1]]


def load_records():
    recs = {}
    for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    return recs


def summarize():
    recs = load_records()
    sha = scorer_blob_sha256()
    result = SC.summarize(
        recs, [t.id for t in TASKS], list(TT.TOOL_NEEDED_IDS),
        scorer_hash=sha, frozen_ok=O.verify_protected()["frozen_byte_identical"],
    )
    result["scorer_hash_unchanged"] = (
        result["scorer_hash"] == recs["L0_REAL"].get("scorer_blob_sha256")
    )
    result["artifact_sha256"] = {
        Path(p).name: O._sha256_file(Path(p))
        for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")))
    }
    return result


def _configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Tool-transfer study (local Ollama only)")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args(argv)
    if a.manifest:
        print(json.dumps({
            "scorer_blob_sha256": scorer_blob_hash(),
            "scorer_version": SC.SCORER_VERSION, "copy_surface": SC.COPY_SURFACE,
            "tasks_check": TT.verify_tasks(),
            "tasks": [t.metadata() for t in TASKS],
            "frozen": O.verify_protected()["frozen_byte_identical"],
        }, ensure_ascii=True, indent=2))
        return 0
    if a.run:
        run_study(); return 0
    if a.summarize:
        res = summarize()
        (DATA_DIR / SUMMARY_NAME).write_text(
            json.dumps(res, ensure_ascii=True, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=True, indent=2))
        return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
