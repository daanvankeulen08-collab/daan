"""M2 (card intervention): can a pre-registered negative/fading card cut false alarms
without losing hits? Fresh 30 tasks, DERIVATION_FIRST_V2, REAL tool execution only.

The card is OFFLINE-COMPILED static text (no runtime teacher text). Two conditions:
  CARD_NEG  - explicit negative card naming when the tool does NOT apply
  CARD_FADE - general faded reminder (no category names), same length budget
Both append the card to the Call-1 prompt; everything else is identical. The PRIMARY
comparison is CARD vs M1's no-card baseline (recomputed on these fresh tasks via a NO_CARD
control arm). To stay within the 130-call budget with 3 arms x 30 x 2 = 180 > 130, we run
only the two card arms here and use the NO_CARD pass/false-alarm from a small control subset.

Actually: to respect budget, two arms x 30 cells x 2 calls = 120 calls (<=130). The NO_CARD
baseline is M1's finding (false-alarm 1.0) generalized; M2 tests whether either card cuts it.

All measurement uses the frozen scorer block15.tool_transfer_score (unchanged). This module
is additive; writes only new data/block15_m2_* artifacts. certified before generation.
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
from block15 import m2_tasks as M2T
from block15 import order_v2_research as O
from block15 import skill_tools as T
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_v3 as V3
from block15.contract_v2 import DERIVATION_FIRST_V2
from block15.round3 import _number_present
from block15.run_benchmark import _now, free_physical_mb
from mdl.config import load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL, MODEL_DIGEST, QUANTIZATION = O.MODEL, O.MODEL_DIGEST, O.QUANTIZATION
NUM_CTX, TEMPERATURE = O.NUM_CTX, O.TEMPERATURE
TOP_P, REPEAT_PENALTY, SEED, KEEP_ALIVE, THINK = (
    O.TOP_P, O.REPEAT_PENALTY, O.SEED, O.KEEP_ALIVE, O.THINK
)
NUM_PREDICT, NUM_PREDICT_REQUEST = 1200, 300
MAX_CALLS, MAX_RUNTIME_S, MIN_FREE_MB, PLANNED_CALLS = 130, 5400.0, 450.0, 120

RESULTS_PREFIX = "block15_m2_results_"
STORE_DB_NAME = "block15_m2.sqlite3"
STORE_JSONL_NAME = "block15_m2_events.jsonl"
SUMMARY_NAME = "block15_m2_summary.json"
CONDITIONS = ("CARD_NEG", "CARD_FADE")

# Offline-compiled static cards. No ground-truth token, no task id, no model output.
CARD_NEG = (
    "Before deciding, check applicability: the stored tool accepts only integer "
    "coefficients a, b, c and a search bound for a quadratic f(n) = a*n^2 + b*n + c, "
    "and returns the first n where f(n) is composite. If the question does not ask "
    "for the smallest n making such a quadratic composite, the tool does not apply: "
    "do not request it and solve directly."
)
CARD_FADE = (
    "Only request the tool if the question asks for the smallest n where a quadratic "
    "is composite. Otherwise solve directly without a tool request."
)
CARDS = {"CARD_NEG": CARD_NEG, "CARD_FADE": CARD_FADE}
TASKS = M2T.TASKS
TASK_BY_ID = {t.id: t for t in TASKS}
GT = M2T.GT
TN = set(M2T.TOOL_NEEDED_IDS)
TNN = set(M2T.TOOL_NOT_NEEDED_IDS)
RUNNER_FILE = "block15/m2_research.py"
SCORER_FILE = "block15/tool_transfer_score.py"


class GuardStop(RuntimeError):
    pass


def data_dir(override=None):
    if override:
        return Path(override)
    env = os.environ.get("M2_DATA_DIR")
    return Path(env) if env else O.DATA_DIR


def scorer_blob_hash():
    return O.git_blob_sha256(Path(SCORER_FILE))


def runner_blob_hash():
    return O.git_blob_sha256(Path(RUNNER_FILE))


def verify_cards_no_gt():
    """Assert no card contains any task's ground-truth token or its id."""
    report = {}
    all_tokens = set()
    for t in TASKS:
        all_tokens.update(int(v) for v in t.truth()["answer_tokens"])
    for name, card in CARDS.items():
        hits = sorted(tok for tok in all_tokens if _number_present(card, tok))
        tids = [tid for tid in (t.id for t in TASKS) if tid in card]
        report[name] = {"gt_token_hits": hits, "task_id_hits": tids,
                        "token_length": len(card.split())}
        if hits or tids:
            raise SystemExit(f"card {name} leaks: {report[name]}")
    return report


def tool_schema_block():
    return ("A tool is available. Return a tool-request object matching this schema "
            "(or null if you will not use it):\n"
            + json.dumps(T.TOOL_SCHEMA, ensure_ascii=True, separators=(",", ":")))


def build_r1_prompt(task, cond):
    """Call-1 prompt: question + card (if any) + tool schema + ask."""
    parts = [task.question]
    if cond in CARDS:
        parts.append(CARDS[cond])
    parts.append(tool_schema_block())
    parts.append("Return a JSON object matching the tool-request schema. Decide whether "
                 "to call the tool; do not explain your reasoning.")
    return "\n\n".join(parts)


def build_r2_prompt(task, tool_result):
    return SC.build_r2_prompt(task, tool_result)


# --- seal / atomic sealed analyze (reuse V3 pattern) ---
def _seal_payload():
    return {"scorer": scorer_blob_hash(), "runner": runner_blob_hash()}


def attach_seal(result):
    payload = _seal_payload()
    marker = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**result, "seal": {**payload, "marker": marker}}


def verify_seal(result):
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


def _scorer_view(records):
    """Map M2 condition keys to the frozen scorer's hardcoded L0_REAL/L0_SHAM keys.

    The frozen scorer (pinned, confined-fix certified) hardcodes these two keys.
    M2 uses CARD_NEG / CARD_FADE. Adapter keeps the scorer untouched; M2's own
    _analysis() supplies the M2 criterion, so the scorer's G1/verdict are not used
    for M2's decision.
    """
    return {
        "L0_REAL": records["CARD_NEG"],
        "L0_SHAM": records["CARD_FADE"],
    }


def sealed_compute(records, *, inject_fail=False):
    view = _scorer_view(records)
    result = SC.summarize(view, [t.id for t in TASKS], list(M2T.TOOL_NEEDED_IDS),
                          scorer_hash=scorer_blob_hash(),
                          frozen_ok=O.verify_protected()["frozen_byte_identical"])
    result["scorer_hash_unchanged"] = result["scorer_hash"] == records["CARD_NEG"].get("scorer_blob_sha256")
    result["runner_blob_sha256"] = runner_blob_hash()
    result = attach_seal(result)
    if inject_fail:
        raise RuntimeError("M2_INJECT_FAIL")
    return result


def sealed_write(result, out_path):
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


def sealed_summarize(out_path, *, inject_fail=False, records=None):
    if records is None:
        records = load_records(data_dir())
    result = sealed_compute(records, inject_fail=inject_fail)
    sealed_write(result, out_path)
    return result


def _settings(ddir):
    return load_settings(model=MODEL, db_path=ddir / STORE_DB_NAME,
                         jsonl_path=ddir / STORE_JSONL_NAME, context_limit=NUM_CTX,
                         think=THINK, temperature=TEMPERATURE, top_p=TOP_P,
                         repeat_penalty=REPEAT_PENALTY, seed=SEED, keep_alive=KEEP_ALIVE)


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
    state["guard"](); state["calls"] += 1
    raw = done = pe = ec = None; pv, se, ts = "unknown", None, None
    status, err = "error", None
    try:
        r = client.chat_json(messages, schema, num_predict=num_predict)
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
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"; status = "error"
    return {"content": raw, "done_reason": done, "prompt_eval_count": pe, "eval_count": ec,
            "protocol_variant": pv, "schema_enforced": se, "think_sent": ts,
            "status": status, "error": err}


def run_cell(client, store, exp_id, task, cond, state):
    r1_prompt = build_r1_prompt(task, cond)
    r1 = _call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                        {"role": "user", "content": r1_prompt}], T.TOOL_SCHEMA,
               NUM_PREDICT_REQUEST, state)
    req_obj = SC.parse_request(r1["content"]); valid, normalized = SC.validate_request(req_obj)
    requested = bool(req_obj and req_obj.get("tool_request") is not None)
    pcorr = SC.parameters_correct(normalized, task)
    # M2 always REAL execution (sham not used); invalid -> unavailable
    tool_result = (T.first_composite_quadratic(**normalized["arguments"])
                   if valid and normalized else {"status": "unavailable"})
    r2_prompt = build_r2_prompt(task, tool_result)
    r2 = _call(client, [{"role": "system", "content": O.SYSTEM_PROMPT_V2},
                        {"role": "user", "content": r2_prompt}], DERIVATION_FIRST_V2,
               NUM_PREDICT, state)
    parsed = O.fresh_parse(r2["content"]); answer = parsed.get("final_answer") if parsed else None
    used = SC.tool_result_used(answer, tool_result, "REAL", valid, pcorr)
    row = {"task_id": task.id, "task_kind": task.kind, "condition": cond,
           "call1": r1, "call2": r2,
           "call1_prompt_sha256": hashlib.sha256(r1_prompt.encode()).hexdigest(),
           "call2_prompt_sha256": hashlib.sha256(r2_prompt.encode()).hexdigest(),
           "r1_prompt": r1_prompt, "raw_content": r2["content"], "raw_request": r1["content"],
           "tool_request": normalized, "tool_requested": requested, "tool_request_valid": valid,
           "parameters_correct": pcorr, "tool_result": tool_result, "tool_result_used": used,
           "answer_text": answer,
           "emitted_key_order": list(O.emitted_key_order(parsed)) if parsed else [],
           "validate_v2_ok": bool(parsed) and O.validate_v2(parsed, DERIVATION_FIRST_V2)[0],
           "validate_v2_violations": O.validate_v2(parsed, DERIVATION_FIRST_V2)[1] if parsed else ["unparseable"],
           "done_reason": r2["done_reason"], "prompt_eval_count": r2["prompt_eval_count"],
           "eval_count": r2["eval_count"], "confidence_raw": parsed.get("confidence") if parsed else None}
    row.update(SC.score_cell(row, task, GT[task.id]))
    store.log_step(exp_id, "m2_cell", cond, row, latency_ms=0.0)
    print(f"    {cond:<9} {task.id:<26} req={int(requested)} pc={int(pcorr)} "
          f"used={int(used)} pass={int(row['primary_correct'])} done={r2['done_reason']}", flush=True)
    return row


def _ts():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_study(ddir):
    if glob.glob(str(ddir / f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: M2 results exist")
    if not O.verify_protected()["frozen_byte_identical"]:
        raise SystemExit("FROZEN changed")
    verify_cards_no_gt()
    if not M2T.verify_tasks()["copy_guard_ok"]:
        raise SystemExit("GT token in M2 task prompt")
    ddir.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    settings = _settings(ddir)
    client = OllamaClient(settings); store = ResearchStore(settings.db_path, settings.jsonl_path)
    state = {"calls": 0, "started": perf_counter(), "free_min": None, "guard": None}

    def guard():
        if state["calls"] + 1 > MAX_CALLS: raise GuardStop("call budget")
        if perf_counter() - state["started"] >= MAX_RUNTIME_S: raise GuardStop("runtime budget")
        free = free_physical_mb()
        if free is not None:
            state["free_min"] = free if state["free_min"] is None else min(state["free_min"], free)
            if free < MIN_FREE_MB: raise GuardStop("free memory")
    state["guard"] = guard
    common = {"model": MODEL, "model_digest": None, "started_at": _now(),
              "scorer_blob_sha256": scorer_blob_hash(), "runner_blob_sha256": runner_blob_hash(),
              "cards": CARDS, "cards_check": verify_cards_no_gt(),
              "tasks_check": M2T.verify_tasks(),
              "task_manifest_sha256": hashlib.sha256(json.dumps([t.metadata() for t in TASKS], sort_keys=True).encode()).hexdigest(),
              "frozen_verification": O.verify_protected(),
              "sampling": {"think": THINK, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
                           "num_predict_request": NUM_PREDICT_REQUEST, "temperature": TEMPERATURE,
                           "top_p": TOP_P, "repeat_penalty": REPEAT_PENALTY, "seed": SEED,
                           "keep_alive": KEEP_ALIVE},
              "planned_calls": PLANNED_CALLS}
    try:
        digest = _verify_model(client); common["model_digest"] = digest
        exp_id = store.create_experiment(seed=str(SEED), model=MODEL, model_digest=digest,
                                         parameters={"kind": "m2_card", "planned_calls": PLANNED_CALLS},
                                         context_limit=NUM_CTX)
        common["experiment_id"] = exp_id
        for cond in CONDITIONS:
            rows = []
            for task in TASKS:
                try:
                    rows.append(run_cell(client, store, exp_id, task, cond, state))
                except GuardStop as exc:
                    common["stopped_early"] = True; common["stop_reason"] = str(exc); break
            rec = dict(common)
            rec.update({"condition": cond, "results": rows, "run_id": f"m2_{cond}_{ts}",
                        "calls_used_total": state["calls"],
                        "runtime_s_total": round(perf_counter() - state["started"], 2),
                        "free_mb_min": state["free_min"], "finished_at": _now()})
            p = ddir / f"{RESULTS_PREFIX}{cond}_{ts}.json"
            p.write_text(json.dumps(rec, ensure_ascii=True, indent=2), encoding="utf-8")
            print(f"condition {cond} written: {p.name}", flush=True)
            if common.get("stopped_early"): break
    finally:
        client.close(); store.close()
    return ddir


def load_records(ddir):
    recs = {}
    for p in sorted(glob.glob(str(ddir / f"{RESULTS_PREFIX}*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        recs[d["condition"]] = d
    return recs


def _analysis(records):
    """M2 criterion: false alarms down vs M1 (1.0) without losing hits.

    Discrimination = (tool-needed request rate) - (tool-not-needed request rate).
    Verdict DISCRIMINATION if ANY card arm has TNN request rate <= 0.30 AND TN request
    rate >= 0.80 (no lost hits) AND TN pass count >= baseline hits. Else CEILING.
    """
    per = {}
    for c in records:
        rows = records[c]["results"]
        tn = [r for r in rows if r["task_id"] in TN]
        tnn = [r for r in rows if r["task_id"] in TNN]
        per[c] = {
            "tn_request_rate": round(sum(1 for r in tn if r["tool_requested"])/len(tn), 4),
            "tnn_request_rate": round(sum(1 for r in tnn if r["tool_requested"])/len(tnn), 4),
            "tn_pass": sum(1 for r in tn if r["primary_correct"]),
            "tnn_pass": sum(1 for r in tnn if r["primary_correct"]),
            "discrimination": round(sum(1 for r in tn if r["tool_requested"])/len(tn)
                                    - sum(1 for r in tnn if r["tool_requested"])/len(tnn), 4),
            "account": A.account(rows), "partition": A.partition(rows),
            "pass_set": sorted(x.split("_")[0] for x in [r["task_id"] for r in rows if r["primary_correct"]]),
            "requested_ids": sorted(x.split("_")[0] for x in [r["task_id"] for r in rows if r["tool_requested"]]),
        }
    m1_hits = 14  # M1 tool-needed REAL pass count (frozen finding)
    any_disc = any(v["tnn_request_rate"] <= 0.30 and v["tn_request_rate"] >= 0.80
                   and v["tn_pass"] >= m1_hits for v in per.values())
    return {"verdict": "DISCRIMINATION" if any_disc else "CEILING",
            "any_discrimination": any_disc, "m1_baseline_hits": m1_hits,
            "m1_baseline_false_alarm": 1.0, "conditions": per}


def main(argv=None):
    ap = argparse.ArgumentParser(description="M2 card intervention (local Ollama only)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--inject-fail", action="store_true")
    ap.add_argument("--verify-cards", action="store_true")
    a = ap.parse_args(argv)
    ddir = data_dir(a.data_dir)
    if a.verify_cards:
        print(json.dumps(verify_cards_no_gt(), indent=2)); return 0
    if a.manifest:
        print(json.dumps({"scorer_blob": scorer_blob_hash(), "runner_blob": runner_blob_hash(),
                          "cards_check": verify_cards_no_gt(), "tasks_check": M2T.verify_tasks(),
                          "task_manifest_sha256": hashlib.sha256(json.dumps([t.metadata() for t in TASKS], sort_keys=True).encode()).hexdigest()},
                         ensure_ascii=True, indent=2)); return 0
    if a.run:
        run_study(ddir); return 0
    if a.summarize:
        out = Path(a.out) if a.out else ddir / SUMMARY_NAME
        try:
            result = sealed_summarize(out, inject_fail=a.inject_fail, records=load_records(ddir))
        except Exception as exc:
            print(f"ANALYSIS FAILED: {type(exc).__name__}", file=sys.stderr); return 3
        result["m2_criterion"] = _analysis(load_records(ddir))
        sealed_write(result, out)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, default=_json_default)); return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
