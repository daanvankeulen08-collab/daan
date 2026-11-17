"""Skill-tool study: can the local model select and parameterise an executable
tool to repair NO_SEARCH failures, with and without a procedure card?

Additive harness. Imports frozen ORDER_V2 / diagnosis modules for helpers and
the allowlisted tool/cards; writes only new data/block15_skill_tool_* artifacts.
No generation at import or in --manifest/--verify/--summarize modes.

Pre-registered in PREREG_SKILL_TOOL.md (committed before generation).
Never executes round3_report.py.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from time import perf_counter

from block15 import accounting as A
from block15 import order_v2_research as O
from block15 import skill_cards as C
from block15 import skill_tools as T
from block15.contract_v2 import DERIVATION_FIRST_V2
from block15.round3 import _number_present
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
NUM_PREDICT = O.NUM_PREDICT           # 1200 for call 2
NUM_PREDICT_REQUEST = 300             # call 1 (tool request)

MAX_CALLS = 80
MAX_RUNTIME_S = 3600.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 72  # 9 tasks x 4 conditions x 2 calls

STORE_DB_NAME = "block15_skill_tool.sqlite3"
STORE_JSONL_NAME = "block15_skill_tool_events.jsonl"
RESULTS_PREFIX = "block15_skill_tool_results_"
SUMMARY_NAME = "block15_skill_tool_summary.json"

LEVELS = ("L3", "L0")
EXEC = ("SHAM", "REAL")
CONDITIONS = ("L3_SHAM", "L3_REAL", "L0_SHAM", "L0_REAL")

PILOT_IDS: tuple[str, ...] = (
    "V2M03_minimal_n2_plus_5n_plus_1223",
    "V2M04_minimal_2n2_plus_6n_plus_1031",
    "V2M06_minimal_n2_plus_3n_plus_1429",
    "V2M07_minimal_n2_plus_n_plus_1481",
    "V2M09_minimal_3n2_plus_3n_plus_1033",
    "V2M10_minimal_2n2_plus_4n_plus_1483",
    "V2M11_minimal_4n2_plus_4n_plus_1163",
    "V2M14_minimal_5n2_plus_5n_plus_1399",
    "V2M15_minimal_3n2_plus_3n_plus_1283",
)

# Tool-request schema (the format dict for call 1).  The model is asked to
# emit a JSON object matching this schema; it is identical in REAL and SHAM.
REQUEST_SCHEMA: dict = T.TOOL_SCHEMA

SHAM_RESULT = {"status": "unavailable"}


def split_condition(cond: str) -> tuple[str, str]:
    level, exec_ = cond.split("_")
    return level, exec_


# ---------------------------------------------------------------------------
# Prompts.  Call 1 is IDENTICAL for REAL and SHAM at a given level (no signal).
# ---------------------------------------------------------------------------


def request_prompt(task, level: str) -> str:
    parts = [task.question]
    assist = C.assistance_text(level)
    if assist:
        parts.append(assist)
    parts.append(C.tool_schema_block())
    parts.append(
        "Return a JSON object matching the tool-request schema. Decide whether "
        "to call the tool; do not explain your reasoning."
    )
    return "\n\n".join(parts)


def final_prompt(task, request_obj: dict | None, tool_result: dict) -> str:
    # Append the tool result, then ask for the DERIVATION_FIRST_V2 final object.
    result_text = json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))
    return (
        task.question
        + "\n\nTool result: " + result_text
        + "\n\n" + O.EFFECTIVE_INSTRUCTION_V2
    )


# ---------------------------------------------------------------------------
# Helpers for parsing call 1 and validating the request
# ---------------------------------------------------------------------------


def parse_request(content: str | None) -> dict | None:
    parsed = O.fresh_parse(content)
    return parsed if isinstance(parsed, dict) else None


def validate_request(obj: dict | None) -> tuple[bool, dict | None]:
    """Validate a tool_request object against REQUEST_SCHEMA (simple checks)."""
    if not isinstance(obj, dict):
        return False, None
    if set(obj) - {"tool_request", "missing_process"}:
        return False, None
    req = obj.get("tool_request", None)
    if req is None:
        return True, None
    if not isinstance(req, dict) or set(req) - {"tool", "arguments"}:
        return False, None
    if req.get("tool") != T.TOOL_NAME:
        return False, None
    args = req.get("arguments")
    if not isinstance(args, dict) or set(args) - {"a", "b", "c", "n_max"}:
        return False, None
    if any(k not in args for k in ("a", "b", "c", "n_max")):
        return False, None
    if not all(isinstance(args[k], int) and not isinstance(args[k], bool)
               for k in ("a", "b", "c", "n_max")):
        return False, None
    if not (0 < args["n_max"] <= 128):
        return False, None
    return True, {"tool": T.TOOL_NAME, "arguments": dict(args)}


def parameters_correct(request: dict | None, task) -> bool:
    """True iff a valid request names the task's exact a,b,c and a safe bound."""
    if not request:
        return False
    a = request["arguments"]
    return (a["a"], a["b"], a["c"]) == (task.a, task.b, task.c) \
        and 0 < a["n_max"] <= 128


def verify_prompts_no_gt() -> dict:
    truth = O.ground_truth_manifest()
    task_by_id = {t.id: t for t in O.TASKS}
    report = {}
    for tid in PILOT_IDS:
        task = task_by_id[tid]
        for level in LEVELS:
            p = request_prompt(task, level)
            hits = sorted(
                int(v) for v in truth[tid]["answer_tokens"]
                if _number_present(p, int(v))
            )
            report[f"{tid}|{level}"] = hits
            if hits:
                raise SystemExit(f"prompt leaks GT for {tid}/{level}: {hits}")
    return report


# ---------------------------------------------------------------------------
# Protected-manifest verification
# ---------------------------------------------------------------------------


def verify_frozen():
    return O.verify_protected()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


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


def call(client, messages, schema, num_predict, state):
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
    latency = (perf_counter() - started) * 1000.0
    return {
        "content": raw, "done_reason": done, "prompt_eval_count": pe,
        "eval_count": ec, "protocol_variant": pv, "schema_enforced": se,
        "think_sent": ts, "status": status, "error": err,
        "latency_ms": round(latency, 2),
    }


def run_cell(client, store, exp_id, task, cond, state, gt):
    level, exec_ = split_condition(cond)
    task_by_id = {t.id: t for t in O.TASKS}

    # CALL 1: tool request. Prompt is identical for REAL and SHAM at a level.
    r1_prompt = request_prompt(task, level)
    r1 = call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                       {"role": "user", "content": r1_prompt}],
              REQUEST_SCHEMA, NUM_PREDICT_REQUEST, state)
    req_obj = parse_request(r1["content"])
    valid, normalized = validate_request(req_obj)
    tool_requested = bool(req_obj and req_obj.get("tool_request") is not None)
    pcorr = parameters_correct(normalized, task)

    # CALL 2: append tool result; REAL executes, SHAM returns unavailable.
    if exec_ == "REAL" and valid and normalized:
        tool_result = T.first_composite_quadratic(**normalized["arguments"])
    else:
        tool_result = dict(SHAM_RESULT)
    r2_prompt = final_prompt(task, normalized, tool_result)
    r2 = call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                       {"role": "user", "content": r2_prompt}],
              DERIVATION_FIRST_V2, NUM_PREDICT, state)
    parsed = O.fresh_parse(r2["content"])
    answer = parsed.get("final_answer") if parsed else None
    audit = O.audit_answer(task, gt[task.id], answer)
    gt_tokens = [int(v) for v in gt[task.id]["answer_tokens"]]
    prompt_copy = any(_number_present(r2_prompt, int(v)) for v in gt_tokens)
    result_used = bool(
        exec_ == "REAL" and valid and normalized
        and isinstance(tool_result, dict) and "n" in tool_result
        and answer is not None
        and all(_number_present(str(answer), int(v))
                for v in ([tool_result["n"], tool_result["value"]] + tool_result["factors"]))
    )

    row = {
        "task_id": task.id, "condition": cond, "level": level, "exec": exec_,
        "call1": r1, "call2": r2,
        "call1_prompt_sha256": O._sha256_text(r1_prompt),
        "call2_prompt_sha256": O._sha256_text(r2_prompt),
        "raw_request": r1["content"],
        "tool_request": normalized, "tool_request_raw": req_obj,
        "tool_requested": tool_requested, "tool_request_valid": valid,
        "parameters_correct": pcorr,
        "tool_result": tool_result, "tool_result_used": result_used,
        "answer_text": answer,
        "emitted_key_order": list(O.emitted_key_order(parsed)) if parsed else [],
        "matches_own_schema": bool(parsed) and O.emission_order_provenance(
            parsed, DERIVATION_FIRST_V2, O.ANSWER_FIRST_V2)["matches_own_schema"],
        "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
        "validate_v2_violations": O.validate_v2(parsed, DERIVATION_FIRST_V2)[1] if parsed else ["unparseable"],
        "done_reason": r2["done_reason"],
        "prompt_eval_count": r2["prompt_eval_count"], "eval_count": r2["eval_count"],
        "confidence_raw": parsed.get("confidence") if parsed else None,
        "copy_possible": prompt_copy, "audit": audit,
        "primary_correct": bool(audit["audit_passed"]) and not prompt_copy,
    }
    row["failure_flags"] = A.failure_flags(row)
    store.log_step(exp_id, "skill_tool_cell", cond, row, latency_ms=r2["latency_ms"])
    print(f"    {cond:<9} {task.id.split('_')[0]:<6} req={tool_requested} "
          f"valid={valid} pcorr={pcorr} pass={row['primary_correct']} "
          f"used={result_used} done={r2['done_reason']} lat={(r1['latency_ms']+r2['latency_ms'])/1000:.1f}s",
          flush=True)
    return row


def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_study() -> Path:
    if glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: skill-tool result files exist")
    frozen = verify_frozen()
    if not frozen["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed")
    prompt_check = verify_prompts_no_gt()
    cards = C.verify_assistance_no_gt()
    gt = O.ground_truth_manifest()
    task_by_id = {t.id: t for t in O.TASKS}
    settings = _settings(); settings.ensure_data_dir()
    ts = datetime_now()
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
        "frozen_verification": frozen, "prompt_gt_check": prompt_check,
        "cards_check": cards,
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
        "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
        "accounting_flag_set": sorted(A.FAILURE_FLAG_SET),
        "pilot_ids": list(PILOT_IDS),
    }
    try:
        digest = _verify_model(client)
        common["model_digest"] = digest
        exp_id = store.create_experiment(
            seed=str(SEED), model=MODEL, model_digest=digest,
            parameters={"kind": "skill_tool", "planned_calls": PLANNED_CALLS},
            context_limit=NUM_CTX,
        )
        common["experiment_id"] = exp_id
        all_rows = {}
        for cond in CONDITIONS:
            rows = []
            for tid in PILOT_IDS:
                try:
                    rows.append(run_cell(client, store, exp_id, task_by_id[tid], cond, state, gt))
                except GuardStop as exc:
                    common.setdefault("stop_reason", str(exc))
                    common["stopped_early"] = True
                    print(f"STOP: {exc}", flush=True)
                    break
            all_rows[cond] = rows
            rec = dict(common)
            rec.update({
                "condition": cond, "results": rows, "run_id": f"skill_tool_{cond}_{ts}",
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


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def load_results():
    recs = {}
    for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    return recs


def g1_manipulation(recs) -> dict:
    """Call-1 payload (tool_request) must be byte-identical REAL vs SHAM per level."""
    detail = {}
    ok = True
    for level in LEVELS:
        sham = {r["task_id"]: r for r in recs[f"{level}_SHAM"]["results"]}
        real = {r["task_id"]: r for r in recs[f"{level}_REAL"]["results"]}
        mism = []
        for tid in PILOT_IDS:
            if tid not in sham or tid not in real:
                mism.append(tid); continue
            if sham[tid]["call1_prompt_sha256"] != real[tid]["call1_prompt_sha256"] \
                    or sham[tid]["raw_request"] != real[tid]["raw_request"]:
                mism.append(tid)
        detail[level] = {"mismatches": mism, "identical": not mism}
        if mism:
            ok = False
    return {"pass": ok, "verdict": "PASS" if ok else "INVALID", "detail": detail}


def summarize() -> dict:
    recs = load_results()
    g1 = g1_manipulation(recs)
    rows = {c: {r["task_id"]: r for r in recs[c]["results"]} for c in CONDITIONS}
    per = {}
    for c in CONDITIONS:
        rs = list(rows[c].values())
        passes = {r["task_id"] for r in rs if r["primary_correct"]}
        per[c] = {
            "cells": len(rs),
            "request_rate": round(sum(1 for r in rs if r["tool_requested"]) / len(rs), 4),
            "valid_request_rate": round(sum(1 for r in rs if r["tool_request_valid"]) / len(rs), 4),
            "param_accuracy": round(sum(1 for r in rs if r["parameters_correct"]) / len(rs), 4),
            "pass_count": len(passes),
            "pass_set": sorted(x.split("_")[0] for x in passes),
            "tool_result_used_count": sum(1 for r in rs if r["tool_result_used"]),
            "account": A.account(rs),
            "partition": A.partition(rs),
        }
    def passes(c): return per[c]["pass_count"]
    def failed(c): return per[c]["account"]["failed_cells"]
    tool_value = {}
    for level in LEVELS:
        s, rr = passes(f"{level}_SHAM"), passes(f"{level}_REAL")
        tool_value[level] = {
            "real_gt_sham": rr > s,
            "real_failed_lt_sham": failed(f"{level}_REAL") < failed(f"{level}_SHAM"),
        }
    autonomy = bool(
        passes("L0_REAL") > 2 and passes("L0_REAL") > passes("L0_SHAM")
    )
    scaffolding = bool(
        not autonomy and passes("L3_REAL") > passes("L3_SHAM")
    )
    dead = bool(not any(v["real_gt_sham"] for v in tool_value.values()))
    if dead:
        verdict = "DEAD"
    elif autonomy:
        verdict = "AUTONOMY"
    elif scaffolding:
        verdict = "SCAFFOLDING-DEPENDENT"
    else:
        verdict = "DEAD"
    overlaps = {}
    names = list(CONDITIONS)
    sets = {c: set(rows[c]) for c in names}  # ids; recompute from pass_set via pass ids
    pass_ids = {
        c: {r["task_id"] for r in rows[c].values() if r["primary_correct"]}
        for c in names
    }
    for i, x in enumerate(names):
        for y in names[i+1:]:
            overlaps[f"{x}&{y}"] = sorted(t.split("_")[0] for t in pass_ids[x] & pass_ids[y])
    return {
        "G1_manipulation": g1,
        "verdict": verdict,
        "criteria": {
            "tool_value": tool_value, "autonomy": autonomy,
            "scaffolding_dependent": scaffolding, "dead": dead,
        },
        "conditions": per,
        "pass_overlaps": overlaps,
        "comparators": {"baseline_A_passes": 0, "placebo_max_passes": 2,
                        "placebo_max_condition": "D1", "placebo_max_cells": ["V2M04", "V2M07"]},
        "frozen": frozen_report(),
        "module_git_blob_sha256_by_condition": {
            c: recs[c].get("module_git_blob_sha256") for c in recs
        },
        "artifact_sha256": {
            Path(p).name: O._sha256_file(Path(p))
            for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")))
        },
    }


def frozen_report():
    v = verify_frozen()
    return {
        "frozen_byte_identical": v["frozen_byte_identical"],
        "frozen_path_count": v["frozen_path_count"],
        "frozen_manifest_sha256": v["frozen_manifest_sha256"],
    }


def _configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Skill-tool study (local Ollama only)")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args(argv)
    if a.manifest:
        print(json.dumps({
            "pilot_ids": list(PILOT_IDS),
            "conditions": list(CONDITIONS),
            "tool_name": T.TOOL_NAME,
            "tool_schema_sha256": O._sha256_json(T.TOOL_SCHEMA, sort_keys=True),
            "cards_check": C.verify_assistance_no_gt(),
            "prompt_gt_check": verify_prompts_no_gt(),
            "frozen": frozen_report(),
            "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
            "accounting_flag_set": sorted(A.FAILURE_FLAG_SET),
        }, ensure_ascii=True, indent=2))
        return 0
    if a.verify:
        print(json.dumps({"frozen": frozen_report(),
                          "cards": C.verify_assistance_no_gt(),
                          "prompts": verify_prompts_no_gt()},
                         ensure_ascii=True, indent=2))
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
