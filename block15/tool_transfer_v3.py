"""Tool-transfer V3 runner: certified mechanics, sealed analysis, no endpoint leaks.

Reuses the certified scorer block15.tool_transfer_score (unchanged, blob da95df42...)
and the frozen 30 tasks. V3 contributions are MECHANICS only (crash/type/name fixes,
atomic sealed analysis, subprocess-testable entrypoints) — no scoring/outcome changes.

Post-generation commands operate on synthetic result files in a configurable data dir
(env TOOL_TRANSFER_V3_DATA_DIR or --data-dir). sealed_summarize computes everything in
memory, writes to a temp file, and atomically renames ONLY on full success; on any
exception nothing is written and nothing is printed (zero endpoint bytes escape).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter

from block15 import accounting as A
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

# V3-only stores (NEW run_id / prefix; never matches block15_round3_results_*)
STORE_DB_NAME = "block15_tool_transfer_v3.sqlite3"
STORE_JSONL_NAME = "block15_tool_transfer_v3_events.jsonl"
RESULTS_PREFIX = "block15_tool_transfer_v3_results_"
SUMMARY_NAME = "block15_tool_transfer_v3_summary.json"

CONDITIONS = ("L0_REAL", "L0_SHAM")
SHAM_RESULT = {"status": "unavailable"}
TASKS = TT.TASKS
TASK_BY_ID = {t.id: t for t in TASKS}
GT = {t.id: t.truth() for t in TASKS}

# Module whose blob is pinned as the runner.
RUNNER_FILE = "block15/tool_transfer_v3.py"
SCORER_FILE = "block15/tool_transfer_score.py"


class GuardStop(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Data dir override (for subprocess certification on synthetic files)
# ---------------------------------------------------------------------------


def data_dir(override: str | None = None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get("TOOL_TRANSFER_V3_DATA_DIR")
    return Path(env) if env else DATA_DIR


def scorer_blob_hash() -> str | None:
    return O.git_blob_sha256(Path(SCORER_FILE))


def runner_blob_hash() -> str | None:
    """NEW name — fixes V2's undefined scorer_blob_sha256() (mechanics)."""
    return O.git_blob_sha256(Path(RUNNER_FILE))


# ---------------------------------------------------------------------------
# Seal: proves the summary came through the wrapper, not a bypassed scorer call
# ---------------------------------------------------------------------------


def _seal_payload() -> dict:
    return {"scorer": scorer_blob_hash(), "runner": runner_blob_hash()}


def attach_seal(result: dict) -> dict:
    payload = _seal_payload()
    marker = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    result = dict(result)
    result["seal"] = {**payload, "marker": marker}
    return result


def verify_seal(result: dict) -> bool:
    s = result.get("seal")
    if not isinstance(s, dict):
        return False
    payload = _seal_payload()
    marker = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (
        s.get("scorer") == payload["scorer"]
        and s.get("runner") == payload["runner"]
        and s.get("marker") == marker
    )


# ---------------------------------------------------------------------------
# Atomic sealed analysis
# ---------------------------------------------------------------------------


def sealed_compute(records: dict, *, inject_fail: bool = False) -> dict:
    """Compute the FULL result in memory. No I/O, no print. Raises on any error."""
    result = SC.summarize(
        records,
        [t.id for t in TASKS],
        list(TT.TOOL_NEEDED_IDS),
        scorer_hash=scorer_blob_hash(),
        frozen_ok=O.verify_protected()["frozen_byte_identical"],
    )
    result["scorer_hash_unchanged"] = (
        result["scorer_hash"] == records["L0_REAL"].get("scorer_blob_sha256")
    )
    result["runner_blob_sha256"] = runner_blob_hash()
    result = attach_seal(result)
    if inject_fail:
        # A1 test hook: fail AFTER aggregation but BEFORE any write/print.
        raise RuntimeError("CERTIFY_INJECT_FAIL: mid-aggregation failure")
    return result


def _json_default(o):
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def sealed_write(result: dict, out_path: Path) -> None:
    """Write result to a temp file, fsync, then atomic rename to out_path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    try:
        payload = json.dumps(result, ensure_ascii=True, indent=2, default=_json_default)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out_path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def sealed_summarize(out_path: Path, *, inject_fail: bool = False,
                     records: dict | None = None) -> dict:
    """Compute + atomically write. On exception: nothing written, nothing printed."""
    if records is None:
        records = load_records(data_dir())
    result = sealed_compute(records, inject_fail=inject_fail)  # may raise -> no write
    sealed_write(result, out_path)                              # only after full success
    return result


# ---------------------------------------------------------------------------
# Prompt construction / runner (delegated to scorer; no scoring changes)
# ---------------------------------------------------------------------------


def tool_schema_block() -> str:
    return (
        "A tool is available. Return a tool-request object matching this schema "
        "(or null if you will not use it):\n"
        + json.dumps(T.TOOL_SCHEMA, ensure_ascii=True, separators=(",", ":"))
    )


def _settings(ddir: Path):
    return load_settings(
        model=MODEL, db_path=ddir / STORE_DB_NAME, jsonl_path=ddir / STORE_JSONL_NAME,
        context_limit=NUM_CTX, think=THINK, temperature=TEMPERATURE, top_p=TOP_P,
        repeat_penalty=REPEAT_PENALTY, seed=SEED, keep_alive=KEEP_ALIVE,
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
    r1_prompt = SC.build_r1_prompt(task, tool_schema_block())
    r1 = _call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                        {"role": "user", "content": r1_prompt}],
               T.TOOL_SCHEMA, NUM_PREDICT_REQUEST, state)
    req_obj = SC.parse_request(r1["content"])
    valid, normalized = SC.validate_request(req_obj)
    requested = bool(req_obj and req_obj.get("tool_request") is not None)
    pcorr = SC.parameters_correct(normalized, task)
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
    row.update(SC.score_cell(row, task, GT[task.id]))
    store.log_step(exp_id, "tool_transfer_cell", cond, row, latency_ms=r2["latency_ms"])
    print(f"    {cond:<8} {task.id:<26} req={int(requested)} pcorr={int(pcorr)} "
          f"used={int(used)} pass={int(row['primary_correct'])} done={r2['done_reason']}",
          flush=True)
    return row


def _ts():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_study(ddir: Path):
    if glob.glob(str(ddir / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: V3 result files exist")
    if not O.verify_protected()["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed")
    if not TT.verify_tasks()["copy_guard_ok"]:
        raise SystemExit("GT token in task prompt")
    ddir.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    paths = {c: ddir / f"{RESULTS_PREFIX}{c}_{ts}.json" for c in CONDITIONS}
    settings = _settings(ddir)
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
        "scorer_blob_sha256": scorer_blob_hash(),
        "runner_blob_sha256": runner_blob_hash(),
        "scorer_version": SC.SCORER_VERSION, "copy_surface": SC.COPY_SURFACE,
        "frozen_verification": O.verify_protected(), "tasks_check": TT.verify_tasks(),
        "task_ids": [t.id for t in TASKS],
        "tool_needed_ids": list(TT.TOOL_NEEDED_IDS),
        "tool_not_needed_ids": list(TT.TOOL_NOT_NEEDED_IDS),
        "sampling": {
            "think": THINK, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
            "num_predict_request": NUM_PREDICT_REQUEST, "temperature": TEMPERATURE,
            "top_p": TOP_P, "repeat_penalty": REPEAT_PENALTY, "seed": SEED,
            "keep_alive": KEEP_ALIVE,
        },
        "planned_calls": PLANNED_CALLS,
        "guards": {"max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S,
                   "min_free_mb": MIN_FREE_MB},
    }
    try:
        digest = _verify_model(client)
        common["model_digest"] = digest
        exp_id = store.create_experiment(
            seed=str(SEED), model=MODEL, model_digest=digest,
            parameters={"kind": "tool_transfer_v3", "planned_calls": PLANNED_CALLS},
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
                    break
            rec = dict(common)
            rec.update({
                "condition": cond, "results": rows, "run_id": f"tool_transfer_v3_{cond}_{ts}",
                "calls_used_total": state["calls"],
                "runtime_s_total": round(perf_counter() - state["started"], 2),
                "free_mb_min": state["free_min"], "finished_at": _now(),
            })
            paths[cond].write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            if common.get("stopped_early"):
                break
    finally:
        client.close(); store.close()
    return paths[CONDITIONS[-1]]


def load_records(ddir: Path) -> dict:
    recs = {}
    for p in sorted(glob.glob(str(ddir / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Tool-transfer V3 (local Ollama only)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--certify", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--score", action="store_true", help="UNSEALED scorer output (bypass demo)")
    ap.add_argument("--g1", action="store_true")
    ap.add_argument("--false-alarm", action="store_true")
    ap.add_argument("--accounting", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--verify-summary", action="store_true")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--inject-fail", action="store_true")
    a = ap.parse_args(argv)
    ddir = data_dir(a.data_dir)

    if a.run:
        run_study(ddir); return 0
    if a.certify:
        from block15 import tool_transfer_v3_certify as CERT
        return CERT.main([])
    if a.manifest:
        print(json.dumps({
            "scorer_blob_sha256": scorer_blob_hash(),
            "runner_blob_sha256": runner_blob_hash(),
            "runner_file": RUNNER_FILE, "scorer_file": SCORER_FILE,
            "tasks_check": TT.verify_tasks(),
        }, ensure_ascii=True, indent=2))
        return 0

    # Post-generation entrypoints (operate on result files in ddir).
    if a.summarize:
        out = Path(a.out) if a.out else ddir / SUMMARY_NAME
        try:
            result = sealed_summarize(out, inject_fail=a.inject_fail,
                                      records=load_records(ddir))
        except Exception as exc:  # noqa: BLE001 - sealed path: no endpoints escape
            print(f"ANALYSIS FAILED: {type(exc).__name__}", file=sys.stderr)
            return 3
        print(json.dumps(result, ensure_ascii=True, sort_keys=True,
                         default=_json_default))
        return 0
    if a.score:
        # Deliberate bypass path: scorer output WITHOUT seal (for cert proof).
        records = load_records(ddir)
        result = SC.summarize(records, [t.id for t in TASKS],
                              list(TT.TOOL_NEEDED_IDS), scorer_blob_hash(), True)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True,
                         default=_json_default))
        return 0
    if a.verify_summary:
        result = _read_json(a.summary)
        ok = verify_seal(result)
        print(json.dumps({"seal_valid": ok}))
        return 0 if ok else 2
    if a.report:
        result = _read_json(a.summary)
        if not verify_seal(result):
            print("REFUSED: summary lacks valid seal (wrapper bypassed)", file=sys.stderr)
            return 2
        text = "# Tool-transfer V3 report (sealed)\n\n" + json.dumps(
            {k: result.get(k) for k in ("G1", "verdict", "criteria")},
            ensure_ascii=True, indent=2) + "\n"
        out = Path(a.out) if a.out else ddir / "block15_tool_transfer_v3_report_body.md"
        sealed_write({"body": text}, out)
        print(hashlib.sha256(text.encode()).hexdigest())
        return 0
    # Specific-field entrypoints
    result = sealed_compute(load_records(ddir))
    if a.g1:
        print(json.dumps(result["G1"], ensure_ascii=True, sort_keys=True))
    elif a.false_alarm:
        print(json.dumps(result["criteria"]["false_alarm_rate"]))
    elif a.accounting:
        print(json.dumps({c: result["conditions"][c]["account"] for c in result["conditions"]},
                         ensure_ascii=True, sort_keys=True))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
