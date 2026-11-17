"""Block B: integration-discrimination study.

A single call per cell.  The tool-result block is injected DIRECTLY into the
prompt (no request step), removing the tool-schema anyOf confound entirely.
Three prompt-identical conditions differ ONLY by that block:

  CORRECT   - injected value == SymPy ground-truth coefficient
  PLAUSIBLE - same sign and digit count, numerically WRONG (small offset)
  ABSENT    - {"status": "unavailable"}

PRIMARY: P(final answer adopts the injected value) per condition.
Also reported: audited passes, meta/placeholder answers, G1 (prompts differ only
by the tool-result block), failure partition (cells and events), seals, pins.

All measurement logic and prompt construction live here (committed).  No scratch
scripts; no post-hoc rescoring.  Uses the frozen scorer's audit_answer and the
frozen round3 signed-integer matcher for adoption.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from time import perf_counter

from block15 import accounting as A
from block15 import integration_tasks as IT
from block15 import order_v2_research as O
from block15 import tool_transfer_score as SC
from block15.contract_v2 import DERIVATION_FIRST_V2, SYSTEM_PROMPT_V2
from block15.round3 import _number_present
from block15.run_benchmark import _now, free_physical_mb
from mdl.config import load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

CONDITIONS = ("CORRECT", "PLAUSIBLE", "ABSENT")
NUM_PREDICT = 1200
MAX_CALLS, MAX_RUNTIME_S, MIN_FREE_MB, PLANNED_CALLS = 45, 2400.0, 450.0, 30
RESULTS_PREFIX = "block15_integration_results_"
STORE_DB = "block15_integration.sqlite3"
STORE_JSONL = "block15_integration_events.jsonl"
SUMMARY_NAME = "block15_integration_summary.json"
RUNNER_FILE = "block15/integration_research.py"
SCORER_FILE = "block15/tool_transfer_score.py"
TASKS, GT = IT.TASKS, IT.GT

META_MARKERS = re.compile(
    r"(?i)(tool data|tool result|as (?:per|given by|from|in) the tool|"
    r"we'?ll go with|we will go with|provided (?:above|by the tool)|"
    r"as stated (?:above|by)|complete prime factorization of f\(n\))"
)


# ---------------------------------------------------------------------------
# Condition values and prompts
# ---------------------------------------------------------------------------

def plausible_value(coefficient: int) -> int:
    """Same sign and digit count as the true coefficient, numerically wrong.

    Deterministic small offset: ~7% of magnitude, capped so the digit count does
    not change.  Guarantees p != coefficient, same sign, same digit count.
    """
    c = int(coefficient)
    digits = len(str(abs(c)))
    room = (10 ** digits - 1) - abs(c)  # headroom before digit count grows
    assert room >= 0
    d = min(max(1, abs(c) // 14), max(1, room // 2))
    p = c + (d if c > 0 else -d)
    assert p != c and (p > 0) == (c > 0) and len(str(abs(p))) == digits
    return p


def tool_result_for(cond: str, coefficient: int) -> dict:
    if cond == "ABSENT":
        return {"status": "unavailable"}
    value = coefficient if cond == "CORRECT" else plausible_value(coefficient)
    return {"status": "ok", "value": value}


def injected_value(cond: str, coefficient: int) -> int | None:
    return None if cond == "ABSENT" else (
        coefficient if cond == "CORRECT" else plausible_value(coefficient)
    )


def build_prompt(task, cond: str) -> str:
    return SC.build_r2_prompt(task, tool_result_for(cond, task.coefficient))


# ---------------------------------------------------------------------------
# G1: prompts differ ONLY by the tool-result block
# ---------------------------------------------------------------------------

TOOL_RESULT_MARKER = "\n\nTool result: "


def strip_tool_result(prompt: str) -> str:
    i = prompt.find(TOOL_RESULT_MARKER)
    if i < 0:
        raise ValueError("no tool-result marker in prompt")
    j = prompt.find("\n\n", i + len(TOOL_RESULT_MARKER))
    if j < 0:
        raise ValueError("no instruction boundary after tool-result block")
    return prompt[:i] + prompt[j:]


def g1_check(prompt_by_cond: dict[str, str]) -> dict:
    bases = {c: strip_tool_result(p) for c, p in prompt_by_cond.items()}
    first = bases[CONDITIONS[0]]
    identical = all(b == first for b in bases.values())
    return {"pass": identical,
            "condition_bases_sha256": {c: hashlib.sha256(b.encode()).hexdigest()
                                       for c, b in bases.items()}}


# ---------------------------------------------------------------------------
# Adoption / meta / pass classifiers
# ---------------------------------------------------------------------------

def adopts(value: int | None, answer_text: str | None) -> bool:
    if value is None or not isinstance(answer_text, str):
        return False
    return _number_present(answer_text, int(value))


def is_meta(answer_text: str | None) -> bool:
    """True if the answer is a placeholder/meta-comment rather than a value."""
    if not isinstance(answer_text, str) or not answer_text.strip():
        return True
    has_int = any(ch.isdigit() for ch in answer_text)
    if not has_int:
        return True
    return bool(META_MARKERS.search(answer_text)) and not bool(
        re.search(r"(?<![\d-])-?\d+(?![\d])", answer_text)
    )


def audited_pass(task, answer_text) -> bool:
    return bool(SC.audit_answer(task, task.truth(), answer_text)["audit_passed"])


def canonical_pass(row: dict) -> bool:
    """Read the canonical pass field ``primary_correct``.

    ``audited_pass`` is a retained alias only: it is accepted when the canonical
    field is absent (legacy rows), but the canonical field always wins.  A row
    must carry at least one of them; otherwise this raises (guard not weakened).
    """
    if "primary_correct" in row:
        return bool(row["primary_correct"])
    if "audited_pass" in row:
        return bool(row["audited_pass"])
    raise KeyError("row carries neither primary_correct nor audited_pass")


# ---------------------------------------------------------------------------
# Seal / atomic sealed analysis
# ---------------------------------------------------------------------------

def scorer_blob_hash():
    return O.git_blob_sha256(Path(SCORER_FILE))


def runner_blob_hash():
    return O.git_blob_sha256(Path(RUNNER_FILE))


def _seal_payload():
    return {"scorer": scorer_blob_hash(), "runner": runner_blob_hash()}


def attach_seal(result: dict) -> dict:
    payload = _seal_payload()
    marker = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**result, "seal": {**payload, "marker": marker}}


def verify_seal(result: dict) -> bool:
    s = result.get("seal")
    if not isinstance(s, dict):
        return False
    payload = _seal_payload()
    marker = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return s.get("scorer") == payload["scorer"] and s.get("runner") == payload["runner"] and s.get("marker") == marker


def _json_default(o):
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def summarize(records: dict) -> dict:
    """Analysis over stored result records. Pure computation, no I/O."""
    g1_reports = {}
    for tid in [t.id for t in TASKS]:
        pm = {c: records[c]["rows_by_id"][tid]["prompt"] for c in CONDITIONS}
        g1_reports[tid] = g1_check(pm)
    g1_pass = all(v["pass"] for v in g1_reports.values())

    per_cond = {}
    for cond in CONDITIONS:
        rows = records[cond]["results"]
        adopted = sum(1 for r in rows if r["adopted_injected"])
        passed = sum(1 for r in rows if canonical_pass(r))  # canonical field
        meta = [r["task_id"] for r in rows if r["is_meta"]]
        acct = A.account(rows)
        part = A.partition(rows)
        # Cross-check: canonical direct recomputation must equal accounting's
        # pass accounting.  A mismatch means a field drift (the Block B bug).
        if acct["audited_passes"] != passed:
            raise ValueError(
                f"{cond}: accounting audited_passes={acct['audited_passes']} "
                f"!= canonical direct recomputation={passed}"
            )
        per_cond[cond] = {
            "n": len(rows),
            "adopted_injected": adopted,
            "P_adopt": round(adopted / len(rows), 4) if rows else None,
            "audited_passes": passed,
            "P_pass": round(passed / len(rows), 4) if rows else None,
            "meta_cells": meta,
            "account": acct,
            "partition": part,
            "pass_set": sorted(r["task_id"].split("_")[0] for r in rows if canonical_pass(r)),
            "injected_values": {r["task_id"].split("_")[0]: r["injected_value"] for r in rows},
        }
    return {"verdict": "SURFACE MISMATCH" if per_cond["PLAUSIBLE"]["adopted_injected"] > 0 else "NO SURFACE ADOPTION",
            "G1": {"pass": g1_pass, "per_task": g1_reports},
            "conditions": per_cond,
            "n_cells": sum(len(records[c]["results"]) for c in CONDITIONS)}


def sealed_compute(records: dict, *, inject_fail: bool = False) -> dict:
    result = summarize(records)
    result["scorer_hash_unchanged"] = result.get("scorer_hash_unchanged", None)
    result["runner_blob_sha256"] = runner_blob_hash()
    result = attach_seal(result)
    if inject_fail:
        raise RuntimeError("INTEGRATION_INJECT_FAIL")
    return result


def sealed_write(result: dict, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    try:
        payload = json.dumps(result, ensure_ascii=True, indent=2, default=_json_default)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, out_path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def sealed_summarize(out_path: Path, records: dict, *, inject_fail: bool = False) -> dict:
    result = sealed_compute(records, inject_fail=inject_fail)
    sealed_write(result, out_path)
    return result


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def data_dir(override=None):
    if override:
        return Path(override)
    env = os.environ.get("INTEGRATION_DATA_DIR")
    return Path(env) if env else O.DATA_DIR


def _settings(ddir):
    return load_settings(
        model=O.MODEL, db_path=ddir / STORE_DB, jsonl_path=ddir / STORE_JSONL,
        context_limit=O.NUM_CTX, think=O.THINK, temperature=O.TEMPERATURE,
        top_p=O.TOP_P, repeat_penalty=O.REPEAT_PENALTY, seed=O.SEED,
        keep_alive=O.KEEP_ALIVE,
    )


def _verify_model(client):
    info = client.model_info()
    if info is None or info.get("digest") != O.MODEL_DIGEST:
        raise SystemExit("model digest mismatch")
    if (info.get("details") or {}).get("quantization_level") != O.QUANTIZATION:
        raise SystemExit("quantization mismatch")
    return str(info["digest"])


def _call(client, messages, schema, state):
    state["guard"](); state["calls"] += 1
    raw = done = pe = ec = None; pv, se, ts = "unknown", None, None
    status, err = "error", None
    try:
        r = client.chat_json(messages, schema, num_predict=NUM_PREDICT)
        raw, done = r.content, r.done_reason; pe, ec = r.prompt_eval_count, r.eval_count
        pv, se, ts = r.protocol_variant, r.schema_enforced, r.think_sent; status = "ok"
    except ModelOutputError as exc:
        raw, done = exc.raw_content, exc.done_reason; pe, ec = exc.prompt_eval_count, exc.eval_count
        pv, se, ts = exc.protocol_variant, exc.schema_enforced, exc.think_sent
        err = f"{type(exc).__name__}: {exc}"; status = "output_error"
    except ModelTimeoutError as exc:
        err = f"{type(exc).__name__}: {exc}"; status = "timeout"
    except ModelError as exc:
        err = f"{type(exc).__name__}: {exc}"; status = "model_error"
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"; status = "error"
    return {"content": raw, "done_reason": done, "prompt_eval_count": pe,
            "eval_count": ec, "protocol_variant": pv, "schema_enforced": se,
            "think_sent": ts, "status": status, "error": err}


def run_cell(client, store, exp_id, task, cond, state):
    prompt = build_prompt(task, cond)
    r = _call(client, [{"role": "system", "content": SYSTEM_PROMPT_V2},
                       {"role": "user", "content": prompt}], DERIVATION_FIRST_V2, state)
    parsed = O.fresh_parse(r["content"])
    answer = parsed.get("final_answer") if parsed else None
    injected = injected_value(cond, task.coefficient)
    pc = audited_pass(task, answer)
    row = {
        "task_id": task.id, "condition": cond, "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "tool_result": tool_result_for(cond, task.coefficient),
        "injected_value": injected, "call": r,
        "raw_content": r["content"], "answer_text": answer,
        "done_reason": r["done_reason"],
        "confidence_raw": parsed.get("confidence") if parsed else None,
        "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
        "adopted_injected": adopts(injected, answer),
        "is_meta": is_meta(answer),
        # CANONICAL pass field (frozen accounting.py reads primary_correct).
        "primary_correct": pc,
        "audited_pass": pc,  # alias only; must equal canonical
    }
    store.log_step(exp_id, "integration_cell", cond, row, latency_ms=0.0)
    print(f"  {cond:<10} {task.id:<24} inj={injected!s:<9} adopted={int(row['adopted_injected'])} "
          f"pass={int(row['primary_correct'])} meta={int(row['is_meta'])} done={r['done_reason']}",
          flush=True)
    return row


def run_study(ddir):
    ddir = Path(ddir)
    if list(ddir.glob(f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: integration results exist")
    if not O.verify_protected()["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed")
    if not IT.verify_tasks()["copy_guard_ok"]:
        raise SystemExit("GT token in integration task prompt")
    ddir.mkdir(parents=True, exist_ok=True)
    settings = _settings(ddir)
    client = OllamaClient(settings); store = ResearchStore(settings.db_path, settings.jsonl_path)
    state = {"calls": 0, "started": perf_counter(), "free_min": None, "guard": None}

    def guard():
        if state["calls"] + 1 > MAX_CALLS:
            raise RuntimeError("call budget reached")
        if perf_counter() - state["started"] >= MAX_RUNTIME_S:
            raise RuntimeError("runtime budget reached")
        free = free_physical_mb()
        if free is not None:
            state["free_min"] = free if state["free_min"] is None else min(state["free_min"], free)
            if free < MIN_FREE_MB:
                raise RuntimeError("free memory below floor")
    state["guard"] = guard

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    common = {
        "model": O.MODEL, "model_digest": None, "started_at": _now(),
        "scorer_blob_sha256": scorer_blob_hash(), "runner_blob_sha256": runner_blob_hash(),
        "task_manifest_sha256": hashlib.sha256(json.dumps([t.metadata() for t in TASKS], sort_keys=True).encode()).hexdigest(),
        "tasks_check": IT.verify_tasks(), "frozen_verification": O.verify_protected(),
        "conditions": CONDITIONS, "num_predict": NUM_PREDICT,
        "sampling": {"think": O.THINK, "num_ctx": O.NUM_CTX, "temperature": O.TEMPERATURE,
                     "top_p": O.TOP_P, "repeat_penalty": O.REPEAT_PENALTY, "seed": O.SEED,
                     "keep_alive": O.KEEP_ALIVE},
        "planned_calls": PLANNED_CALLS,
        "budget": {"max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S, "min_free_mb": MIN_FREE_MB},
    }
    try:
        digest = _verify_model(client); common["model_digest"] = digest
        exp_id = store.create_experiment(seed=str(O.SEED), model=O.MODEL, model_digest=digest,
                                         parameters={"kind": "integration", "planned_calls": PLANNED_CALLS},
                                         context_limit=O.NUM_CTX)
        common["experiment_id"] = exp_id
        for cond in CONDITIONS:
            rows = []
            for task in TASKS:
                rows.append(run_cell(client, store, exp_id, task, cond, state))
            rec = dict(common)
            rec.update({"condition": cond, "results": rows, "run_id": f"integration_{cond}_{ts}",
                        "calls_used_total": state["calls"],
                        "runtime_s_total": round(perf_counter() - state["started"], 2),
                        "free_mb_min": state["free_min"], "finished_at": _now()})
            out = ddir / f"{RESULTS_PREFIX}{cond}_{ts}.json"
            out.write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"condition {cond} written: {out.name}", flush=True)
    finally:
        client.close(); store.close()
    return ddir


def load_records(ddir):
    records = {}
    for p in sorted(glob.glob(str(Path(ddir) / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        d["rows_by_id"] = {r["task_id"]: r for r in d["results"]}
        records[d["condition"]] = d
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(description="Integration-discrimination study (local Ollama)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--certify", action="store_true")
    ap.add_argument("--inject-fail", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ddir = data_dir(a.data_dir)
    if a.run:
        run_study(ddir); return 0
    if a.manifest:
        print(json.dumps({"scorer_blob": scorer_blob_hash(), "runner_blob": runner_blob_hash(),
                          "tasks_check": IT.verify_tasks(), "conditions": CONDITIONS,
                          "num_predict": NUM_PREDICT, "planned_calls": PLANNED_CALLS,
                          "budget": {"max_calls": MAX_CALLS, "max_runtime_s": MAX_RUNTIME_S,
                                     "min_free_mb": MIN_FREE_MB}}, ensure_ascii=True, indent=2))
        return 0
    if a.certify:
        from block15 import integration_certify as CERT
        return CERT.main([])
    if a.summarize:
        out = Path(a.out) if a.out else ddir / SUMMARY_NAME
        try:
            result = sealed_summarize(out, load_records(ddir), inject_fail=a.inject_fail)
        except Exception as exc:  # noqa: BLE001 - sealed: no endpoints escape
            print(f"ANALYSIS FAILED: {type(exc).__name__}", file=sys.stderr); return 3
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, default=_json_default))
        return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
