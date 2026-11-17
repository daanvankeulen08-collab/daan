"""Placebo-control study for the diagnosis-guided retry branch.

Additive harness. Uses the same 12 ORDER_V2 failures and DERIVATION_FIRST_V2
with ORDER_V2 sampling; only the appended feedback text changes. Two new
placebo conditions:

  D1 -- fixed neutral "review your work" text (no diagnostic information)
  D2 -- neutral output-format restatement, token-length MATCHED to C's oracle
        text per task, carrying no failure class, locus or ground-truth token

Primary endpoint: audited non-copy pass count via the same strict SymPy audit.
Criterion: INFORMATIONAL iff C passes > max(D1,D2) passes AND C failed_cells
<= min(D1,D2) failed_cells; otherwise NON-INFORMATIONAL (perturbation noise).

Pre-registered in PREREG_PLACEBO.md (committed before generation). Writes only
new data/block15_placebo_* artifacts. Never executes round3_report.py.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from time import perf_counter

from block15 import accounting as A
from block15 import diagnosis_research as D
from block15 import order_v2_research as O
from block15.contract_v2 import DERIVATION_FIRST_V2
from block15.round3 import _number_present
from block15.run_benchmark import DATA_DIR, _now, free_physical_mb
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL, MODEL_DIGEST, QUANTIZATION = O.MODEL, O.MODEL_DIGEST, O.QUANTIZATION
NUM_CTX, NUM_PREDICT, TEMPERATURE = O.NUM_CTX, O.NUM_PREDICT, O.TEMPERATURE
TOP_P, REPEAT_PENALTY, SEED, KEEP_ALIVE, THINK = (
    O.TOP_P, O.REPEAT_PENALTY, O.SEED, O.KEEP_ALIVE, O.THINK
)

MAX_CALLS = 30
MAX_RUNTIME_S = 1800.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 24

STORE_DB_NAME = "block15_placebo.sqlite3"
STORE_JSONL_NAME = "block15_placebo_events.jsonl"
RESULTS_PREFIX = "block15_placebo_results_"
SUMMARY_NAME = "block15_placebo_summary.json"

CONDITIONS = ("D1", "D2")
FAILURE_IDS = D.FAILURE_IDS
TASK_BY_ID = D.TASK_BY_ID

# D1 is fixed by the pre-registration (neutral, no diagnostic information).
D1_TEXT = "Please review your work carefully and attempt the task again."

# D2: neutral output-format restatement, NO digits (so no GT token can appear),
# no failure-class words, no locus. Two fixed strings with exact token counts
# matching the two oracle-text lengths (20 and 28 whitespace tokens).
D2_SHORT = (
    "Please review the required output format before you answer. "
    "Return one JSON object with these fields: confidence, derivation, "
    "final_answer, uncertainty."
)
D2_LONG = D2_SHORT + " Please keep every string on a single line."

# Words that would make a placebo informative; asserted absent.
_CLASS_WORDS = ("NO_SEARCH", "ARITHMETIC_ERROR", "TRUNCATION", "UNCLASSIFIED",
                "SCHEMA_VIOLATION", "INVALID_JSON", "CONTRACT_MISMATCH", "failure class")


def tokens(text: str) -> list[str]:
    return text.split()


def d2_text_for(task_id: str) -> str:
    target = len(tokens(D.oracle_text(task_id)))
    if target == len(tokens(D2_SHORT)):
        return D2_SHORT
    if target == len(tokens(D2_LONG)):
        return D2_LONG
    raise SystemExit(f"no D2 length match for {task_id} (C has {target} tokens)")


def appended_text(task_id: str, condition: str) -> str:
    if condition == "B":
        return D.LABEL_TEXT
    if condition == "C":
        return D.oracle_text(task_id)
    if condition == "D1":
        return D1_TEXT
    if condition == "D2":
        return d2_text_for(task_id)
    raise ValueError(condition)


def prompt_for(task_id: str, condition: str) -> str:
    return TASK_BY_ID[task_id].prompt + "\n\n" + appended_text(task_id, condition)


def verify_placebo_texts() -> dict:
    """Assert D1/D2 carry no failure class, locus, or GT token; report lengths."""
    gt = O.ground_truth_manifest()
    rows = {}
    for tid in FAILURE_IDS:
        c_tok = len(tokens(D.oracle_text(tid)))
        per = {}
        for name in ("B", "C", "D1", "D2"):
            if name == "B":
                txt = D.LABEL_TEXT
            elif name == "C":
                txt = D.oracle_text(tid)
            else:
                txt = appended_text(tid, name)
            full = prompt_for(tid, name)
            gt_hits = {
                str(t): bool(_number_present(full, int(t)))
                for t in gt[tid]["answer_tokens"]
            }
            class_hits = [w for w in _CLASS_WORDS if w.lower() in txt.lower()]
            # D1/D2 must be clean; B is clean by construction; C is the oracle
            # (it intentionally names the class but must still avoid GT tokens).
            if name in ("D1", "D2"):
                assert not class_hits, f"{name} names a class for {tid}: {class_hits}"
                assert not any(gt_hits.values()), f"{name} leaks GT for {tid}"
                # no digit-based locus: D1/D2 must contain no standalone integer
                assert not [m for m in __import__("re").finditer(r"\d", txt)], \
                    f"{name} contains a digit for {tid}"
            per[name] = {
                "appended_text": txt,
                "appended_sha256": O._sha256_text(txt),
                "token_length": len(tokens(txt)),
                "gt_token_hits": gt_hits,
                "copy_possible": any(gt_hits.values()),
                "class_words": class_hits,
            }
        assert per["D2"]["token_length"] == per["C"]["token_length"], \
            f"D2 length != C length for {tid}"
        rows[tid] = {
            "C_oracle_token_length": c_tok,
            "conditions": per,
        }
    return rows


def verify_frozen():
    return D.verify_frozen_against_order_v2()


# ---------------------------------------------------------------------------
# Load B and C pass sets from the stored DIAGNOSIS results (passes recomputed
# with the same strict audit, not trusted from stored flags).
# ---------------------------------------------------------------------------


def load_diagnosis_pass_sets() -> dict[str, set[str]]:
    out = {}
    for c in ("B", "C"):
        p = sorted(glob.glob(str(DATA_DIR / f"{D.RESULTS_PREFIX}{c}_*.json")))[-1]
        rec = json.loads(Path(p).read_text(encoding="utf-8"))
        out[c] = {
            r["task_id"] for r in rec["results"]
            if D.audited_pass(r["task_id"], r)
        }
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class GuardStop(RuntimeError):
    pass


def _settings():
    return load_settings_safe()


def load_settings_safe():
    from mdl.config import load_settings
    return load_settings(
        model=MODEL, db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=NUM_CTX, think=THINK, temperature=TEMPERATURE,
        top_p=TOP_P, repeat_penalty=REPEAT_PENALTY, seed=SEED,
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
    return str(info["digest"])


def run_condition(client, store, exp_id, condition, state, placebo_checks):
    out = []
    for tid in FAILURE_IDS:
        state["guard"]()
        state["calls"] += 1
        prompt = prompt_for(tid, condition)
        messages = [
            {"role": "system", "content": O.SYSTEM_PROMPT_V2},
            {"role": "user", "content": prompt},
        ]
        started = perf_counter()
        raw = done = pe = ec = None
        pv, se, ts = "unknown", None, None
        status, err = "error", None
        try:
            resp = client.chat_json(messages, DERIVATION_FIRST_V2, num_predict=NUM_PREDICT)
            raw, done = resp.content, resp.done_reason
            pe, ec = resp.prompt_eval_count, resp.eval_count
            pv, se, ts = resp.protocol_variant, resp.schema_enforced, resp.think_sent
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
        parsed = O.fresh_parse(raw)
        answer = parsed.get("final_answer") if parsed else None
        row = {
            "task_id": tid, "condition": condition, "status": status, "error": err,
            "prompt_sha256": O._sha256_text(prompt),
            "raw_content": raw,
            "raw_content_sha256": O._sha256_text(raw) if raw is not None else None,
            "emitted_key_order": list(O.emitted_key_order(parsed)) if parsed else [],
            "matches_own_schema": bool(parsed) and O.emission_order_provenance(
                parsed, DERIVATION_FIRST_V2, O.ANSWER_FIRST_V2)["matches_own_schema"],
            "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
            "validate_v2_violations": O.validate_v2(parsed, DERIVATION_FIRST_V2)[1] if parsed else ["unparseable"],
            "protocol_variant": pv, "schema_enforced": se, "think_sent": ts,
            "done_reason": done, "prompt_eval_count": pe, "eval_count": ec,
            "answer_text": answer,
            "confidence_raw": parsed.get("confidence") if parsed else None,
            "appended_text": appended_text(tid, condition),
            "appended_text_sha256": placebo_checks[tid]["conditions"][condition]["appended_sha256"],
            "appended_token_length": placebo_checks[tid]["conditions"][condition]["token_length"],
            "copy_possible": placebo_checks[tid]["conditions"][condition]["copy_possible"],
            "latency_ms": round(latency, 2),
        }
        row["primary_correct"] = D.audited_pass(tid, row)
        row["failure_flags"] = A.failure_flags(row)
        store.log_step(exp_id, "placebo_cell", condition, row, latency_ms=latency)
        out.append(row)
        print(f"    {condition} {tid[:26]:<26} pc={row['primary_correct']} "
              f"done={done} toks={row['appended_token_length']} lat={latency/1000:.1f}s",
              flush=True)
    return out


def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_study() -> Path:
    if glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: placebo result files exist")
    frozen = verify_frozen()
    if not frozen["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed; refusing to generate")
    placebo = verify_placebo_texts()
    fp = O._verify_frozen()
    bp = load_diagnosis_pass_sets()
    settings = _settings()
    settings.ensure_data_dir()
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
        "frozen_verification": frozen, "frozen_tasks_verification": fp,
        "placebo_texts": placebo, "diagnosis_pass_sets": {k: sorted(v) for k, v in bp.items()},
        "sampling": {
            "think": THINK, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE, "top_p": TOP_P,
            "repeat_pENALTY": REPEAT_PENALTY, "seed": SEED, "keep_alive": KEEP_ALIVE,
            "system_prompt_sha256": O._sha256_text(O.SYSTEM_PROMPT_V2),
            "schema_sha256": O._sha256_json(DERIVATION_FIRST_V2, sort_keys=False),
        },
        "guards": {"max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S,
                   "min_free_mb": MIN_FREE_MB, "planned_calls": PLANNED_CALLS},
        "planned_calls": PLANNED_CALLS,
        "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
        "accounting_convention": sorted(A.FAILURE_FLAG_SET),
    }
    try:
        digest = _verify_model(client)
        common["model_digest"] = digest
        exp_id = store.create_experiment(
            seed=str(SEED), model=MODEL, model_digest=digest,
            parameters={"kind": "placebo_control", "planned_calls": PLANNED_CALLS},
            context_limit=NUM_CTX,
        )
        common["experiment_id"] = exp_id
        all_rows = {}
        for c in CONDITIONS:
            all_rows[c] = run_condition(client, store, exp_id, c, state, placebo)
        for c in CONDITIONS:
            rec = dict(common)
            rec.update({
                "condition": c, "results": all_rows[c], "run_id": f"placebo_{c}_{ts}",
                "calls_used_total": state["calls"],
                "runtime_s_total": round(perf_counter() - state["started"], 2),
                "free_mb_min": state["free_min"], "free_mb_end": free_physical_mb(),
                "finished_at": _now(),
            })
            paths[c].write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"condition {c} written: {paths[c].name}", flush=True)
    finally:
        client.close(); store.close()
    return paths["D2"]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def summarize() -> dict:
    recs = {}
    for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    # pass sets for B, C (from diagnosis), D1, D2 (this run)
    bp = load_diagnosis_pass_sets()
    passes = {
        "B": bp["B"],
        "C": bp["C"],
        "D1": {r["task_id"] for r in recs["D1"]["results"] if r["primary_correct"]},
        "D2": {r["task_id"] for r in recs["D2"]["results"] if r["primary_correct"]},
    }
    c_pass, d1_pass, d2_pass = len(passes["C"]), len(passes["D1"]), len(passes["D2"])
    # failed_cells for C (from diagnosis A baseline definition is not needed here;
    # use C's own failed cells and D1/D2 failed cells), under single definition
    dg_C = json.loads(Path(sorted(glob.glob(str(DATA_DIR / f"{D.RESULTS_PREFIX}C_*.json")))[-1]).read_text())["results"]
    c_failed = A.failed_cells(dg_C)
    d1_failed = A.failed_cells(recs["D1"]["results"])
    d2_failed = A.failed_cells(recs["D2"]["results"])
    informational = bool(
        c_pass > max(d1_pass, d2_pass) and c_failed <= min(d1_failed, d2_failed)
    )
    accounts = {
        "B": None,  # B rows are in diagnosis store; reported via pass set only
        "C": A.account(dg_C),
        "D1": A.account(recs["D1"]["results"]),
        "D2": A.account(recs["D2"]["results"]),
    }
    partitions = {
        "C": A.partition(dg_C),
        "D1": A.partition(recs["D1"]["results"]),
        "D2": A.partition(recs["D2"]["results"]),
    }
    overlaps = {}
    names = ["B", "C", "D1", "D2"]
    for x in names:
        for y in names:
            if x < y:
                overlaps[f"{x}&{y}"] = sorted(passes[x] & passes[y])
    return {
        "verdict": "INFORMATIONAL" if informational else "NON-INFORMATIONAL",
        "informational": informational,
        "pass_sets": {k: sorted(v) for k, v in passes.items()},
        "pass_counts": {k: len(v) for k, v in passes.items()},
        "overlaps": overlaps,
        "criterion_inputs": {
            "C_pass": c_pass, "max_D1_D2_pass": max(d1_pass, d2_pass),
            "C_failed_cells": c_failed, "min_D1_D2_failed_cells": min(d1_failed, d2_failed),
        },
        "accounts": accounts,
        "partitions": partitions,
        "appended_lengths": {
            tid: {c: placebo_len(tid, c) for c in ("B", "C", "D1", "D2")}
            for tid in FAILURE_IDS
        },
        "frozen": verify_frozen(),
        "live": D.live_git_blob_hashes(
            "88de7418cef4994662c92f0bc39f47638f8518f3", "HEAD"),
        "module_git_blob_sha256_by_condition": {
            c: recs[c].get("module_git_blob_sha256") for c in CONDITIONS
        },
        "artifact_sha256": {
            Path(p).name: O._sha256_file(Path(p))
            for p in sorted(glob.glob(str(DATA_DIR / f"{RESULTS_PREFIX}*.json")))
        },
    }


def placebo_len(tid, c):
    chk = verify_placebo_texts()[tid]["conditions"]
    return chk[c]["token_length"]


def _configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _configure_stdout()
    ap = argparse.ArgumentParser(description="Placebo-control study (local Ollama only)")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args(argv)
    if a.manifest:
        print(json.dumps({
            "failure_ids": list(FAILURE_IDS),
            "placebo_texts": verify_placebo_texts(),
            "frozen": verify_frozen(),
            "module_git_blob_sha256": O.git_blob_sha256(Path(__file__)),
            "accounting_flag_set": sorted(A.FAILURE_FLAG_SET),
        }, ensure_ascii=True, indent=2))
        return 0
    if a.verify:
        print(json.dumps({"frozen": verify_frozen(),
                          "placebo_texts": verify_placebo_texts()},
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
