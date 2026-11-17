"""A2 null-reachability probe: does the model emit tool_request:null, and does
the schema form (anyOf vs type-array nullable) change that?

8 calls: 4 trivially no-tool tasks x 2 schema forms.  num_predict 300, sampling
identical to V3 (taken from block15.order_v2_research constants).  The prompt text
is identical across the two forms; only the ``format`` schema differs.

The record stores, for every cell, the raw content, the classified tool_request
value (null / object / missing / unparseable), and the protocol metadata
(protocol_variant, schema_enforced, think_sent) so a schema-enforcement fallback
can be distinguished from a genuine model output.  No scientific endpoint is
computed here; this is a harness diagnostic.
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter

from block15 import order_v2_research as O
from block15 import skill_tools as T
from block15 import tool_schema_validator as V
from block15.contract_v2 import SYSTEM_PROMPT_V2
from block15.run_benchmark import _now, free_physical_mb
from mdl.config import load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

PROBE_TASKS = (
    "What is 2+2? Answer with the integer.",
    "What is 6 times 7? Answer with the integer.",
    "What is 15 minus 9? Answer with the integer.",
    "What is 81 divided by 9? Answer with the integer.",
)
RESULTS_PREFIX = "block15_null_probe_results_"
STORE_DB = "block15_null_probe.sqlite3"
STORE_JSONL = "block15_null_probe_events.jsonl"
RUNNER_FILE = "block15/null_probe.py"
NUM_PREDICT = 300


def probe_schemas() -> dict:
    """F1 = current anyOf form; F2 = semantically identical nullable type-array."""
    f1 = copy.deepcopy(T.TOOL_SCHEMA)
    f2 = copy.deepcopy(T.TOOL_SCHEMA)
    obj_branch = f2["properties"]["tool_request"]["anyOf"][1]
    f2["properties"]["tool_request"] = {
        "type": ["object", "null"],
        "additionalProperties": obj_branch["additionalProperties"],
        "required": obj_branch["required"],
        "properties": obj_branch["properties"],
    }
    V.validate_schema(f1)
    V.validate_schema(f2)
    return {"F1_anyof": f1, "F2_nullable": f2}


def build_prompt(task: str, schema: dict) -> str:
    return "\n\n".join([
        task,
        "A tool is available. Return a tool-request object matching this schema "
        "(or null if you will not use it):\n"
        + json.dumps(schema, ensure_ascii=True, separators=(",", ":")),
        "Return a JSON object matching the tool-request schema. Decide whether "
        "to call the tool; do not explain your reasoning.",
    ])


def classify_request(content: str | None) -> dict:
    """Classify the tool_request value in a model response."""
    result = {"label": "unparseable", "value": None, "missing_process": None}
    if not isinstance(content, str) or not content.strip():
        return result
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    if start < 0:
        return result
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return result
    if not isinstance(obj, dict):
        return result
    result["missing_process"] = obj.get("missing_process")
    if "tool_request" not in obj:
        result["label"] = "missing"
    elif obj["tool_request"] is None:
        result["label"] = "null"
    else:
        result["label"] = "object"
        result["value"] = obj["tool_request"]
    return result


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


def data_dir(override=None):
    if override:
        return Path(override)
    env = os.environ.get("NULL_PROBE_DATA_DIR")
    return Path(env) if env else O.DATA_DIR


def _call(client, messages, schema, state):
    state["guard"](); state["calls"] += 1
    raw = done = pe = ec = None; pv, se, ts = "unknown", None, None
    status, err = "error", None
    try:
        r = client.chat_json(messages, schema, num_predict=NUM_PREDICT)
        raw, done = r.content, r.done_reason; pe, ec = r.prompt_eval_count, r.eval_count
        pv, se, ts = r.protocol_variant, r.schema_enforced, r.think_sent; status = "ok"
    except ModelOutputError as exc:
        raw, done = exc.raw_content, exc.done_reason
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


def run_probe(ddir, *, client=None, store=None, with_guard=True):
    """Run the 8 probe calls. Returns the record dict (also persisted)."""
    ddir = Path(ddir)
    if list(ddir.glob(f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: null-probe results exist")
    ddir.mkdir(parents=True, exist_ok=True)
    schemas = probe_schemas()
    settings = _settings(ddir)
    own_client = client is None
    if own_client:
        client = OllamaClient(settings)
        if not client.health():
            raise SystemExit("Ollama not reachable")
        digest = _verify_model(client)
    else:
        digest = None
    own_store = store is None
    if own_store:
        store = ResearchStore(settings.db_path, settings.jsonl_path)
        exp_id = store.create_experiment(
            seed=str(O.SEED), model=O.MODEL, model_digest=digest or "fake",
            parameters={"kind": "null_probe"}, context_limit=O.NUM_CTX,
        )
    else:
        exp_id = "fake"
    state = {"calls": 0, "started": perf_counter(), "guard": lambda: None}
    if with_guard and own_client:
        def guard():
            if state["calls"] + 1 > 8:
                raise RuntimeError("probe call budget reached")
            free = free_physical_mb()
            if free is not None and free < 450.0:
                raise RuntimeError("free memory below floor")
        state["guard"] = guard

    rows = []
    try:
        for form, schema in schemas.items():
            for task in PROBE_TASKS:
                prompt = build_prompt(task, schema)
                r = _call(client, [{"role": "system", "content": SYSTEM_PROMPT_V2},
                                   {"role": "user", "content": prompt}], schema, state)
                cls = classify_request(r["content"])
                row = {"form": form, "task": task, "prompt": prompt,
                       "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                       "call": r, "classification": cls}
                rows.append(row)
                store.log_step(exp_id, "null_probe_cell", form, row)
                print(f"  {form:<11} {task[:22]:<22} label={cls['label']:<10} "
                      f"variant={r['protocol_variant']} enforced={r['schema_enforced']}",
                      flush=True)
    finally:
        if own_client:
            client.close()
        if own_store:
            store.close()

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "model": O.MODEL, "model_digest": digest, "started_at": _now(),
        "runner_blob_sha256": O.git_blob_sha256(Path(RUNNER_FILE)),
        "num_predict": NUM_PREDICT,
        "sampling": {"think": O.THINK, "num_ctx": O.NUM_CTX, "temperature": O.TEMPERATURE,
                     "top_p": O.TOP_P, "repeat_penalty": O.REPEAT_PENALTY,
                     "seed": O.SEED, "keep_alive": O.KEEP_ALIVE},
        "schemas": {k: {"anyOf": "anyOf" in json.dumps(v),
                        "type_list_nullable": "null" in json.dumps(v.get("properties", {}).get("tool_request", {}).get("type", []))}
                    for k, v in schemas.items()},
        "results": rows, "calls_used": state["calls"], "finished_at": _now(),
    }
    out = ddir / f"{RESULTS_PREFIX}{ts}.json"
    out.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"written: {out.name}", flush=True)
    return record


def summarize(record: dict) -> dict:
    """Per-form counts of tool_request classification (a harness finding only)."""
    per = {}
    for form in ("F1_anyof", "F2_nullable"):
        rows = [r for r in record["results"] if r["form"] == form]
        counts = {}
        for r in rows:
            lab = r["classification"]["label"]
            counts[lab] = counts.get(lab, 0) + 1
        per[form] = {
            "counts": counts,
            "null_emitted": counts.get("null", 0),
            "schema_enforced_flags": sorted({str(r["call"]["schema_enforced"]) for r in rows}),
            "protocol_variants": sorted({r["call"]["protocol_variant"] for r in rows}),
        }
    return {"per_form": per, "n_cells": len(record["results"])}


def report_details(record: dict) -> list[dict]:
    """Per-cell detail: task, form, label, emitted tool_request value, metadata."""
    out = []
    for r in record["results"]:
        cls = r["classification"]
        out.append({
            "form": r["form"], "task": r["task"], "label": cls["label"],
            "tool_request": cls["value"], "missing_process": cls["missing_process"],
            "protocol_variant": r["call"]["protocol_variant"],
            "schema_enforced": r["call"]["schema_enforced"],
            "raw_content": r["call"]["content"],
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Null-reachability probe (local Ollama)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--report", default=None, help="print per-cell detail from a result file")
    a = ap.parse_args(argv)
    ddir = data_dir(a.data_dir)
    if a.report:
        rec = json.loads(Path(a.report).read_text(encoding="utf-8"))
        print(json.dumps(report_details(rec), ensure_ascii=True, indent=2))
        return 0
    if a.manifest:
        print(json.dumps({"schemas": {k: v for k, v in probe_schemas().items()},
                          "probe_tasks": list(PROBE_TASKS)}, ensure_ascii=True, indent=2))
        return 0
    if a.run:
        rec = run_probe(ddir)
        print(json.dumps(summarize(rec), ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
