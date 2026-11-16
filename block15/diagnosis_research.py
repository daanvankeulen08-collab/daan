"""Diagnosis-guided retry study for the 12 ORDER_V2 derivation-first failures.

Additive harness.  It imports the frozen ORDER_V2 module for helpers only and
writes new ``block15_diagnosis_*`` stores and result files.  No generation at
import or in ``--manifest``/``--verify``/``--summarize`` modes.

Pre-registered in PREREG_DIAGNOSIS.md (committed before generation).

Conditions, all with schema DERIVATION_FIRST_V2 and ORDER_V2 sampling:
  A BLIND  -- identical prompt; 2 tasks verify byte-identity with stored output
  B LABEL  -- append a generic "judged incorrect" label
  C ORACLE -- append the machine-true failure class + locus (no GT token)
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from time import perf_counter

from block15 import order_v2_research as O
from block15.contract_v2 import DERIVATION_FIRST_V2
from block15.round3 import _number_present
from block15.run_benchmark import DATA_DIR, _now, free_physical_mb
from mdl.config import load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL = O.MODEL
MODEL_DIGEST = O.MODEL_DIGEST
QUANTIZATION = O.QUANTIZATION

NUM_CTX = O.NUM_CTX
NUM_PREDICT = O.NUM_PREDICT
TEMPERATURE = O.TEMPERATURE
TOP_P = O.TOP_P
REPEAT_PENALTY = O.REPEAT_PENALTY
SEED = O.SEED
KEEP_ALIVE = O.KEEP_ALIVE
THINK = O.THINK

MAX_CALLS = 40
MAX_RUNTIME_S = 2400.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 26  # 2 (A verify) + 12 (B) + 12 (C); 36 if A reruns all 12

STORE_DB_NAME = "block15_diagnosis.sqlite3"
STORE_JSONL_NAME = "block15_diagnosis_events.jsonl"
RESULTS_PREFIX = "block15_diagnosis_results_"
SUMMARY_NAME = "block15_diagnosis_summary.json"

CONDITIONS = ("A", "B", "C")
A_VERIFY_N = 2

LABEL_TEXT = (
    "Your previous attempt was judged incorrect. No further information is "
    "available. Attempt the task again."
)

# The 12 derivation_first failures, in the exact ORDER_V2 task order.
FAILURE_IDS: tuple[str, ...] = (
    "V2C02_coeff_2x_minus_7_pow6_x4",
    "V2M02_minimal_n2_plus_7n_plus_1163",
    "V2M03_minimal_n2_plus_5n_plus_1223",
    "V2M04_minimal_2n2_plus_6n_plus_1031",
    "V2M06_minimal_n2_plus_3n_plus_1429",
    "V2M07_minimal_n2_plus_n_plus_1481",
    "V2M08_minimal_n2_plus_n_plus_1487",
    "V2M09_minimal_3n2_plus_3n_plus_1033",
    "V2M10_minimal_2n2_plus_4n_plus_1483",
    "V2M11_minimal_4n2_plus_4n_plus_1163",
    "V2M14_minimal_5n2_plus_5n_plus_1399",
    "V2M15_minimal_3n2_plus_3n_plus_1283",
)

# Machine classification (pre-registered, first-match-wins precedence).
# class -> evidence; locus only for NO_SEARCH (max tested n).
CLASSIFICATION: dict[str, dict] = {
    "V2C02_coeff_2x_minus_7_pow6_x4": {
        "class": "UNCLASSIFIED",
        "evidence": "no precedence rule matched (derivation ends at correct formula, "
        "no checkable false numeric claim, GT token absent from derivation)",
    },
    "V2M02_minimal_n2_plus_7n_plus_1163": {
        "class": "ARITHMETIC_ERROR",
        "evidence": "derivation step [4] claims f(4)=1217; SymPy f(4)=1207",
    },
    "V2M03_minimal_n2_plus_5n_plus_1223": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=3; derivation tested n in [0,1]; n=3 never tested",
    },
    "V2M04_minimal_2n2_plus_6n_plus_1031": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=3; derivation tested n in [0,1]; n=3 never tested",
    },
    "V2M06_minimal_n2_plus_3n_plus_1429": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=4; derivation tested n in [0,1]; n=4 never tested",
    },
    "V2M07_minimal_n2_plus_n_plus_1481": {
        "class": "NO_SEARCH", "locus": 2,
        "evidence": "true n=4; derivation tested n in [0,1,2]; n=4 never tested",
    },
    "V2M08_minimal_n2_plus_n_plus_1487": {
        "class": "TRUNCATION",
        "evidence": "done_reason == length; unparseable at stop",
    },
    "V2M09_minimal_3n2_plus_3n_plus_1033": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=6; derivation tested n in [0,1]; n=6 never tested",
    },
    "V2M10_minimal_2n2_plus_4n_plus_1483": {
        "class": "NO_SEARCH", "locus": 2,
        "evidence": "true n=3; derivation tested n in [0,1,2]; n=3 never tested",
    },
    "V2M11_minimal_4n2_plus_4n_plus_1163": {
        "class": "NO_SEARCH", "locus": 2,
        "evidence": "true n=3; derivation tested n in [0,1,2]; n=3 never tested",
    },
    "V2M14_minimal_5n2_plus_5n_plus_1399": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=7; derivation tested n in [0,1]; n=7 never tested",
    },
    "V2M15_minimal_3n2_plus_3n_plus_1283": {
        "class": "NO_SEARCH", "locus": 1,
        "evidence": "true n=4; derivation tested n in [0,1]; n=4 never tested",
    },
}

_PREFIX = (
    "Your previous attempt was judged incorrect. Failure class: "
)


def oracle_text(task_id: str) -> str:
    c = CLASSIFICATION[task_id]
    cls = c["class"]
    if cls == "NO_SEARCH":
        return (
            _PREFIX + "NO_SEARCH. You did not test values beyond n="
            + str(c["locus"]) + ". Attempt the task again."
        )
    if cls == "ARITHMETIC_ERROR":
        return (
            _PREFIX + "ARITHMETIC_ERROR. A numeric claim in your derivation is "
            "false; recheck the arithmetic where you evaluate f(n). Attempt the "
            "task again."
        )
    if cls == "TRUNCATION":
        return (
            _PREFIX + "TRUNCATION. Your response was cut off at the output length "
            "limit; produce a shorter JSON object. Attempt the task again."
        )
    return (
        _PREFIX + "UNCLASSIFIED. No specific failure locus could be identified. "
        "Attempt the task again."
    )


def _prompt(task, condition: str) -> str:
    base = task.prompt
    if condition == "A":
        return base
    if condition == "B":
        return base + "\n\n" + LABEL_TEXT
    return base + "\n\n" + oracle_text(task.id)


def _gt_tokens(task_id: str) -> list[int]:
    return [int(v) for v in O.ground_truth_manifest()[task_id]["answer_tokens"]]


def _copy_check(task_id: str, prompt: str) -> dict:
    hits = {str(t): bool(_number_present(prompt, t)) for t in _gt_tokens(task_id)}
    return {"tokens": hits, "copy_possible": any(hits.values())}


def verify_oracle_no_gt() -> dict:
    """Assert every oracle text contains no ground-truth token; per-cell result."""
    task_by_id = {t.id: t for t in O.TASKS}
    results = {}
    for tid in FAILURE_IDS:
        txt = oracle_text(tid)
        prompt = _prompt(task_by_id[tid], "C")
        results[tid] = {
            "oracle_text": txt,
            "oracle_sha256": O._sha256_text(txt),
            "full_prompt_sha256": O._sha256_text(prompt),
            "copy": _copy_check(tid, prompt),
        }
        if results[tid]["copy"]["copy_possible"]:
            raise SystemExit(f"oracle text leaks ground truth for {tid}")
    return results


# ---------------------------------------------------------------------------
# Protected-manifest verification (FROZEN unchanged; LIVE via git blobs)
# ---------------------------------------------------------------------------


def diagnosis_frozen_hashes(root: Path | None = None) -> dict[str, str | None]:
    root = root or DATA_DIR.parent
    paths = [
        p for p in O.frozen_paths(root)
        if not Path(p).name.startswith("block15_diagnosis_")
    ]
    return {p: O._sha256_file(root / p) for p in paths}


def verify_frozen_against_order_v2() -> dict:
    cur = diagnosis_frozen_hashes()
    base = O.FROZEN_BASELINE_SHA256
    diff = {p: {"before": v, "after": cur.get(p)} for p, v in base.items() if v != cur.get(p)}
    return {
        "frozen_path_count": len(cur),
        "frozen_baseline_path_count": len(base),
        "frozen_byte_identical": not diff and set(cur) == set(base),
        "frozen_differences": diff,
        "frozen_manifest_sha256": O._sha256_json(cur),
        "frozen_baseline_manifest_sha256": O.FROZEN_BASELINE_MANIFEST_SHA256,
    }


def live_git_blob_hashes(before_commit: str, after_commit: str) -> dict:
    root = DATA_DIR.parent
    rows = {}
    for p in O.live_paths(root):
        f = root / p
        rows[p] = {
            "before": O.git_blob_sha256(f, commit=before_commit),
            "after": O.git_blob_sha256(f, commit=after_commit),
        }
        b, a = rows[p]["before"], rows[p]["after"]
        rows[p]["status"] = (
            "new" if b is None and a is not None
            else "removed" if a is None and b is not None
            else "changed" if b != a else "unchanged"
        )
    return rows


# ---------------------------------------------------------------------------
# Baseline ORDER_V2 stored outputs
# ---------------------------------------------------------------------------


def load_order_v2_baseline() -> dict[str, dict]:
    p = sorted(glob.glob(str(DATA_DIR / f"{O.RESULTS_PREFIX}derivation_first_*.json")))[-1]
    record = json.loads(Path(p).read_text(encoding="utf-8"))
    return {r["task_id"]: r for r in record["results"]}


TASK_BY_ID: dict[str, object] = {t.id: t for t in O.TASKS}


def audited_pass(task_id: str, row: dict) -> bool:
    """Same strict SymPy audit as ORDER_V2, applied to a persisted cell."""
    truth = O.ground_truth_manifest()[task_id]
    parsed = O.fresh_parse(row.get("raw_content"))
    answer = parsed.get("final_answer") if parsed else None
    audit = O.audit_answer(TASK_BY_ID[task_id], truth, answer)
    base_prompt = TASK_BY_ID[task_id].prompt
    copied = _copy_check(task_id, base_prompt)
    return bool(audit["audit_passed"]) and not copied["copy_possible"]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class GuardStop(RuntimeError):
    pass


def _settings():
    return load_settings(
        model=MODEL,
        db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=NUM_CTX,
        think=THINK,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        repeat_penalty=REPEAT_PENALTY,
        seed=SEED,
        keep_alive=KEEP_ALIVE,
    )


def _verify_model(client):
    if not client.health():
        raise SystemExit("Ollama not reachable")
    info = client.model_info()
    if info is None or info.get("digest") != MODEL_DIGEST:
        raise SystemExit("model digest mismatch")
    if (info.get("details") or {}).get("quantization_level") != QUANTIZATION:
        raise SystemExit("quantization mismatch")
    return str(info["digest"]), info


def run_condition(client, store, exp_id, condition, task_ids, runner_state, oracle_checks):
    """Run one condition over task_ids; returns list of rows."""
    task_by_id = TASK_BY_ID
    base = load_order_v2_baseline()
    out = []
    for tid in task_ids:
        runner_state["guard"]()
        runner_state["calls"] += 1
        task = task_by_id[tid]
        prompt = _prompt(task, condition)
        messages = [
            {"role": "system", "content": O.SYSTEM_PROMPT_V2},
            {"role": "user", "content": prompt},
        ]
        started = perf_counter()
        raw = None
        done = None
        pe = ec = None
        pv, se, ts = "unknown", None, None
        status = "error"
        err = None
        try:
            resp = client.chat_json(messages, DERIVATION_FIRST_V2, num_predict=NUM_PREDICT)
            raw = resp.content
            done = resp.done_reason
            pe, ec = resp.prompt_eval_count, resp.eval_count
            pv, se, ts = resp.protocol_variant, resp.schema_enforced, resp.think_sent
            status = "ok"
        except ModelOutputError as exc:
            raw = exc.raw_content
            done = exc.done_reason
            pe, ec = exc.prompt_eval_count, exc.eval_count
            pv, se, ts = exc.protocol_variant, exc.schema_enforced, exc.think_sent
            err = f"{type(exc).__name__}: {exc}"
            status = "output_error"
        except ModelTimeoutError as exc:
            err = f"{type(exc).__name__}: {exc}"
            status = "timeout"
        except ModelError as exc:
            err = f"{type(exc).__name__}: {exc}"
            status = "model_error"
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            status = "error"
        latency = (perf_counter() - started) * 1000.0

        parsed = O.fresh_parse(raw)
        answer = parsed.get("final_answer") if parsed else None
        row = {
            "task_id": tid,
            "condition": condition,
            "status": status,
            "error": err,
            "prompt_sha256": O._sha256_text(prompt),
            "raw_content": raw,
            "raw_content_sha256": O._sha256_text(raw) if raw is not None else None,
            "emitted_key_order": list(O.emitted_key_order(parsed)) if parsed else [],
            "matches_own_schema": bool(parsed) and O.emission_order_provenance(
                parsed, DERIVATION_FIRST_V2, O.ANSWER_FIRST_V2
            )["matches_own_schema"],
            "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
            "validate_v2_violations": O.validate_v2(parsed, DERIVATION_FIRST_V2)[1] if parsed else ["unparseable"],
            "protocol_variant": pv,
            "schema_enforced": se,
            "think_sent": ts,
            "done_reason": done,
            "prompt_eval_count": pe,
            "eval_count": ec,
            "answer_text": answer,
            "confidence_raw": parsed.get("confidence") if parsed else None,
            "copy_possible": oracle_checks[tid]["copy"]["copy_possible"],
            "oracle_text_sha256": oracle_checks[tid]["oracle_sha256"],
            "latency_ms": round(latency, 2),
        }
        row["primary_correct"] = audited_pass(tid, row)
        if condition == "A":
            row["byte_identical_to_order_v2"] = (
                raw == base[tid].get("raw_content")
            )
            row["baseline_primary_correct"] = audited_pass(tid, base[tid])
        store.log_step(exp_id, "diagnosis_cell", condition, row, latency_ms=latency)
        out.append(row)
        print(
            f"    {condition} {tid[:28]:<28} pc={row['primary_correct']} "
            f"done={done} eval={ec} lat={latency/1000:.1f}s",
            flush=True,
        )
    return out


def run_study() -> Path:
    if glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: diagnosis result files exist")
    frozen = verify_frozen_against_order_v2()
    if not frozen["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed; refusing to generate")
    oracle_checks = verify_oracle_no_gt()
    fp = O._verify_frozen()
    base = load_order_v2_baseline()
    settings = _settings()
    settings.ensure_data_dir()
    ts = datetime_now()
    paths = {c: DATA_DIR / f"{RESULTS_PREFIX}{c}_{ts}.json" for c in CONDITIONS}
    for p in paths.values():
        if p.exists():
            raise SystemExit(f"refusing to overwrite {p}")

    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    state = {"calls": 0, "started": perf_counter(), "free_min": None}

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

    common = {
        "model": MODEL,
        "model_digest": None,
        "started_at": _now(),
        "frozen_verification": frozen,
        "frozen_tasks_verification": fp,
        "oracle_checks": oracle_checks,
        "classification": CLASSIFICATION,
        "failure_ids": list(FAILURE_IDS),
        "sampling": {
            "think": THINK, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE, "top_p": TOP_P,
            "repeat_penalty": REPEAT_PENALTY, "seed": SEED,
            "keep_alive": KEEP_ALIVE,
            "system_prompt_sha256": O._sha256_text(O.SYSTEM_PROMPT_V2),
            "schema": DERIVATION_FIRST_V2,
            "schema_sha256": O._sha256_json(DERIVATION_FIRST_V2, sort_keys=False),
        },
        "guards": {
            "max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S,
            "min_free_mb": MIN_FREE_MB, "planned_calls": PLANNED_CALLS,
        },
        "planned_calls": PLANNED_CALLS,
        "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
    }
    try:
        digest, info = _verify_model(client)
        common["model_digest"] = digest
        exp_id = store.create_experiment(
            seed=str(SEED), model=MODEL, model_digest=digest,
            parameters={"kind": "diagnosis_retry", "planned_calls": PLANNED_CALLS},
            context_limit=NUM_CTX,
        )
        common["experiment_id"] = exp_id
        all_rows = {}

        # Condition A: verify byte-identity on 2 tasks.
        a_verify = run_condition(client, store, exp_id, "A", list(FAILURE_IDS[:A_VERIFY_N]),
                                 state, oracle_checks)
        all_rows["A"] = a_verify
        identical = all(r.get("byte_identical_to_order_v2") for r in a_verify)
        determinism = {
            "verified_tasks": [r["task_id"] for r in a_verify],
            "all_byte_identical": identical,
            "verdict": "PASS" if identical else "FAIL",
        }
        if identical:
            # Baseline for all 12 = stored ORDER_V2 cells (no more A calls).
            all_rows["A"] = []
            for tid in FAILURE_IDS:
                r = dict(base[tid])
                r["task_id"] = tid
                r["condition"] = "A"
                r["primary_correct"] = audited_pass(tid, base[tid])
                r["byte_identical_to_order_v2"] = True
                r["source"] = "stored_ORDER_V2"
                all_rows["A"].append(r)
        else:
            a_rest = run_condition(client, store, exp_id, "A", list(FAILURE_IDS[A_VERIFY_N:]),
                                   state, oracle_checks)
            all_rows["A"] = a_verify + a_rest
        common["determinism"] = determinism

        # Conditions B and C.
        all_rows["B"] = run_condition(client, store, exp_id, "B", list(FAILURE_IDS), state, oracle_checks)
        all_rows["C"] = run_condition(client, store, exp_id, "C", list(FAILURE_IDS), state, oracle_checks)

        kill_dead = sum(1 for r in all_rows["C"] if r["primary_correct"]) == 0
        common["kill_gate"] = {
            "C_new_audited_passes": sum(1 for r in all_rows["C"] if r["primary_correct"]),
            "branch_dead": kill_dead,
            "verdict": "DEAD" if kill_dead else "ALIVE",
        }

        for c in CONDITIONS:
            rec = dict(common)
            rec.update({
                "condition": c,
                "results": all_rows[c],
                "run_id": f"diagnosis_{c}_{ts}",
                "calls_used_total": state["calls"],
                "runtime_s_total": round(perf_counter() - state["started"], 2),
                "free_mb_min": state["free_min"],
                "free_mb_end": free_physical_mb(),
                "finished_at": _now(),
            })
            paths[c].write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"condition {c} written: {paths[c].name}", flush=True)
    finally:
        client.close()
        store.close()
    return paths["C"]


def datetime_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Read-only analysis
# ---------------------------------------------------------------------------


def _mcnemar_exact(b, c):
    return O._mcnemar_exact(b, c)


def summarize() -> dict:
    recs = {}
    for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    rows = {c: {r["task_id"]: r for r in recs[c]["results"]} for c in recs}
    stats = {}
    for c in CONDITIONS:
        rs = list(rows[c].values())
        modes = {}
        flags = {}
        for r in rs:
            m = "primary_correct" if r["primary_correct"] else (
                r["status"] if r["status"] != "ok" else "primary_wrong"
            )
            modes[m] = modes.get(m, 0) + 1
        stats[c] = {
            "cells": len(rs),
            "primary_count": sum(1 for r in rs if r["primary_correct"]),
            "failure_modes": modes,
            "distinct_failed_cells": sum(1 for r in rs if not r["primary_correct"]),
            "total_failure_events": sum(
                (0 if r["primary_correct"] else 1)
                + (1 if r["done_reason"] == "length" else 0)
                + (1 if not r["validate_v2_ok"] else 0)
                + (1 if r["copy_possible"] else 0)
                for r in rs
            ),
        }
    a_cnt, b_cnt, c_cnt = (stats[c]["primary_count"] for c in CONDITIONS)

    def paired_counts(cond_x: str, cond_y: str) -> tuple[int, int]:
        x_pass_only = sum(
            1 for tid in FAILURE_IDS
            if rows[cond_x][tid]["primary_correct"] and not rows[cond_y][tid]["primary_correct"]
        )
        y_pass_only = sum(
            1 for tid in FAILURE_IDS
            if not rows[cond_x][tid]["primary_correct"] and rows[cond_y][tid]["primary_correct"]
        )
        return x_pass_only, y_pass_only

    bA, cA = paired_counts("A", "C")
    bB, cB = paired_counts("B", "C")
    paired = {
        "C_vs_A_b_appassonly": bA, "C_vs_A_c_new": cA,
        "C_vs_A_p": round(_mcnemar_exact(bA, cA), 6),
        "C_vs_B_b": bB, "C_vs_B_c": cB,
        "C_vs_B_p": round(_mcnemar_exact(bB, cB), 6),
    }
    success = bool(
        c_cnt > a_cnt and c_cnt >= b_cnt
        and stats["C"]["total_failure_events"] <= stats["A"]["total_failure_events"]
    )
    return {
        "kill_gate": recs["C"].get("kill_gate"),
        "determinism": recs["A"].get("determinism"),
        "class_distribution": {
            cls: sum(1 for v in CLASSIFICATION.values() if v["class"] == cls)
            for cls in sorted({v["class"] for v in CLASSIFICATION.values()})
        },
        "conditions": stats,
        "paired": paired,
        "success_criterion_met": success,
        "frozen": verify_frozen_against_order_v2(),
        "live": live_git_blob_hashes("38905757070bfa30e499d48b3ce7d0a21c7702a6",
                                     "HEAD"),
        "module_git_blob_sha256_by_condition": {
            c: recs[c].get("module_git_blob_sha256") for c in recs
        },
        "artifact_sha256": {
            Path(p).name: O._sha256_file(Path(p))
            for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")))
        },
    }


def _configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Diagnosis-guided retry (local Ollama only)")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args(argv)
    if a.manifest:
        print(json.dumps({
            "failure_ids": list(FAILURE_IDS),
            "classification": CLASSIFICATION,
            "oracle_checks": verify_oracle_no_gt(),
            "frozen": verify_frozen_against_order_v2(),
            "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
        }, ensure_ascii=True, indent=2))
        return 0
    if a.verify:
        print(json.dumps({
            "frozen": verify_frozen_against_order_v2(),
            "oracle_checks": verify_oracle_no_gt(),
        }, ensure_ascii=True, indent=2))
        return 0
    if a.run:
        run_study()
        return 0
    if a.summarize:
        res = summarize()
        (DATA_DIR / SUMMARY_NAME).write_text(
            json.dumps(res, ensure_ascii=True, indent=2), encoding="utf-8"
        )
        print(json.dumps(res, ensure_ascii=True, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
