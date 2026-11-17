"""FROZEN SCORER for the tool-transfer study.

*** IMMUTABLE AFTER PREREGISTRATION.  NO POST-HOC RESCORING. ***

This module contains ALL measurement logic: prompt construction, request
validation, the strict SymPy audit, the copy check (r1_prompt surface ONLY),
failure accounting inputs, and the full analysis.  Its git blob hash is
recorded in PREREG_TOOL_TRANSFER.md before any generation and MUST be asserted
unchanged in the report.  If a scoring bug is found after generation, the run
is CONTAMINATED and must be discarded — never re-scored in place.

Design decisions frozen here:
* copy surface = r1_prompt (task + assistance + tool schema). The tool result
  appended in Call 2 legitimately contains ground truth and is NEVER scanned
  for copying; tool_result_used is recorded separately and never disqualifies.
* primary_correct = audit_passed AND NOT copy_possible.
* audit = strict SymPy: coefficient = exact integer present; minimality = n
  AND composite value AND both prime factors present.
* failure accounting via block15.accounting (fixed flag set; passes contribute
  zero events), given a top-level raw_content on the row.
"""

from __future__ import annotations

import json
import math

import sympy

from block15 import accounting as A
from block15 import skill_tools as T
from block15.contract_v2 import DERIVATION_FIRST_V2, OUTPUT_INSTRUCTION_V2
from block15.round3 import _number_present

SCORER_VERSION = "tool_transfer_scorer_v1_frozen"

# The neutral instruction + one schema-order sentence, inlined so the frozen
# scorer has no dependency on a mutable helper module for prompt construction.
EFFECTIVE_INSTRUCTION = (
    OUTPUT_INSTRUCTION_V2
    + "\n\nEmit the fields in the order required by the schema, not in the order "
    "they are listed here."
)

# The copy surface is the CALL-1 prompt only (task + assistance + schema).
COPY_SURFACE = "r1_prompt"


# ---------------------------------------------------------------------------
# Prompt construction (frozen: defines the copy surface)
# ---------------------------------------------------------------------------


def build_r1_prompt(task, tool_schema_block: str) -> str:
    """Call-1 prompt: task question + (no card at L0) + tool schema + request ask."""
    return "\n\n".join([
        task.question,
        tool_schema_block,
        "Return a JSON object matching the tool-request schema. Decide whether "
        "to call the tool; do not explain your reasoning.",
    ])


def build_r2_prompt(task, tool_result: dict) -> str:
    """Call-2 prompt: task question + appended tool result + neutral instruction."""
    result_text = json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))
    return (
        task.question
        + "\n\nTool result: " + result_text
        + "\n\n" + EFFECTIVE_INSTRUCTION
    )


# ---------------------------------------------------------------------------
# Request parsing / validation / parameter accuracy
# ---------------------------------------------------------------------------


def parse_request(content):
    # Local fresh parse (no dependency on the runner's parser).
    if not isinstance(content, str) or not content.strip():
        return None
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
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def validate_request(obj):
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


def parameters_correct(request, task) -> bool:
    if not request:
        return False
    a = request["arguments"]
    return (a["a"], a["b"], a["c"]) == (task.a, task.b, task.c) \
        and 0 < a["n_max"] <= 128


# ---------------------------------------------------------------------------
# Strict SymPy audit (frozen)
# ---------------------------------------------------------------------------

_INT_RE = __import__("re").compile(r"(?<![\d.])-?\d+(?!\d|\.\d)")


def _ints(text):
    if not isinstance(text, str):
        return set()
    t = text.replace("\u2212", "-").replace("\u2013", "-")
    t = __import__("re").sub(r"(?<=\d),(?=\d)", "", t)
    return {int(m.group()) for m in _INT_RE.finditer(t)}


def audit_answer(task, truth, answer_text) -> dict:
    """Strict audit: exact coefficient OR minimality conjunction."""
    values = _ints(answer_text)
    if truth["kind"] == "coefficient":
        exp = int(truth["coefficient"])
        present = exp in values
        return {
            "method": "sympy_expand_coeff",
            "expected": exp,
            "extracted": sorted(values),
            "exact_present": present,
            "strict_single": values == {exp},
            "audit_passed": bool(present),
        }
    n, value = int(truth["n"]), int(truth["value"])
    primes = [int(p) for p in truth["primes"]]
    required = {n, value, *primes}
    present = required.issubset(values)
    fac = sympy.factorint(value)
    fprimes = sorted(int(p) for p in fac)
    exp_one = all(int(e) == 1 for e in fac.values())
    product_ok = int(sympy.prod(int(p) ** int(e) for p, e in fac.items())) == value
    fact_ok = fprimes == primes and exp_one and product_ok
    return {
        "method": "sympy_first_composite_and_factorint",
        "expected_set": sorted(required),
        "extracted": sorted(values),
        "all_present": bool(present),
        "strict_set_equal": values == required,
        "sympy_factorization_verified": bool(fact_ok),
        "audit_passed": bool(present and fact_ok),
    }


# ---------------------------------------------------------------------------
# Per-cell scoring (frozen): copy over r1_prompt ONLY
# ---------------------------------------------------------------------------


def score_cell(row, task, truth) -> dict:
    """Score one cell. Returns derived fields to be persisted."""
    answer = row.get("answer_text")
    audit = audit_answer(task, truth, answer)
    gt_tokens = [int(v) for v in truth["answer_tokens"]]
    r1 = row["r1_prompt"]
    copy = any(_number_present(r1, v) for v in gt_tokens)
    primary = bool(audit["audit_passed"]) and not copy
    # accounting needs a top-level raw_content
    tmp = dict(row)
    tmp["raw_content"] = row.get("raw_content")
    tmp["copy_possible"] = copy
    tmp["primary_correct"] = primary
    flags = A.failure_flags(tmp)
    return {
        "audit": audit,
        "audit_passed": bool(audit["audit_passed"]),
        "copy_possible": copy,
        "primary_correct": primary,
        "failure_flags": flags,
    }


def tool_result_used(answer_text, tool_result, exec_mode, valid, params_ok) -> bool:
    """String-membership flag: does the answer carry the real tool result?"""
    if exec_mode != "REAL" or not valid or not params_ok:
        return False
    if not isinstance(tool_result, dict) or "n" not in tool_result:
        return False
    if not isinstance(answer_text, str):
        return False
    tokens = [tool_result["n"], tool_result["value"], *tool_result["factors"]]
    return all(_number_present(answer_text, int(v)) for v in tokens)


# ---------------------------------------------------------------------------
# Analysis (frozen)
# ---------------------------------------------------------------------------


def mcnemar_exact(b, c):
    total = b + c
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2**total))


def summarize(records, task_ids, tool_needed_ids, scorer_hash, frozen_ok):
    """Full analysis. records: dict condition -> result record."""
    rows = {c: {r["task_id"]: r for r in records[c]["results"]} for c in records}
    per = {}
    for c in records:
        rs = list(rows[c].values())
        passes = {r["task_id"] for r in rs if r["primary_correct"]}
        requested = {r["task_id"] for r in rs if r["tool_requested"]}
        per[c] = {
            "cells": len(rs),
            "requested": len(requested),
            "requested_ids": sorted(x.split("_")[0] for x in requested),
            "params_correct": sum(1 for r in rs if r["parameters_correct"]),
            "result_used": sum(1 for r in rs if r["tool_result_used"]),
            "passes": len(passes),
            "pass_set": sorted(x.split("_")[0] for x in passes),
            "pass_ids": passes,
            "account": A.account(rs),
            "partition": A.partition(rs),
        }
    # G1: call-1 payload byte-identical REAL vs SHAM
    g1_detail = {}
    g1_ok = True
    for level in ("L0",):
        sham = {r["task_id"]: r for r in records["L0_SHAM"]["results"]}
        real = {r["task_id"]: r for r in records["L0_REAL"]["results"]}
        mism = [tid for tid in task_ids if tid not in sham or tid not in real
                or sham[tid]["call1_prompt_sha256"] != real[tid]["call1_prompt_sha256"]
                or sham[tid]["raw_request"] != real[tid]["raw_request"]]
        g1_detail[level] = {"mismatches": mism, "identical": not mism}
        if mism:
            g1_ok = False
    g1 = {"pass": g1_ok, "verdict": "PASS" if g1_ok else "INVALID", "detail": g1_detail}

    # PRIMARY (replication): paired REAL-SHAM on tool-needed
    tn = set(tool_needed_ids)
    rp = per["L0_REAL"]["pass_ids"] & tn
    sp = per["L0_SHAM"]["pass_ids"] & tn
    real_only, sham_only = len(rp - sp), len(sp - rp)
    diff = len(rp) - len(sp)
    p = mcnemar_exact(real_only, sham_only)
    replicated = bool(
        diff > 0
        and per["L0_REAL"]["account"]["failed_cells"] < per["L0_SHAM"]["account"]["failed_cells"]
        and g1_ok
    )
    # CO-PRIMARY: false-alarm rate on tool-not-needed
    tnn = set(task_ids) - tn
    fa_ids = per["L0_REAL"]["requested_ids"] & {x.split("_")[0] for x in tnn}
    fa_rate = round(len(fa_ids) / len(tnn), 4)
    selective = fa_rate <= 0.30
    if not replicated:
        verdict = "NOT REPLICATED"
    elif selective:
        verdict = "PROCEDURAL SELECTION DEMONSTRATED"
    else:
        verdict = "PARAMETER BINDING ONLY, NOT SELECTION"
    # conversion failures: correct params + result available + wrong answer
    conv_fail = []
    for r in records["L0_REAL"]["results"]:
        if (r["parameters_correct"] and r["tool_result_used"] and not r["primary_correct"]):
            conv_fail.append(r["task_id"].split("_")[0])
    # misuse cost: tool-not-needed REAL vs SHAM passes
    misuse = {
        "REAL": len([x for x in per["L0_REAL"]["pass_set"] if x in {t.split('_')[0] for t in tnn}]),
        "SHAM": len([x for x in per["L0_SHAM"]["pass_set"] if x in {t.split('_')[0] for t in tnn}]),
    }
    overlaps = {}
    ids = sorted(records)
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            overlaps[f"{x}&{y}"] = sorted(t.split("_")[0] for t in per[x]["pass_ids"] & per[y]["pass_ids"])
    return {
        "G1": g1,
        "verdict": verdict,
        "criteria": {
            "replicated": replicated, "selective": selective,
            "real_minus_sham_tool_needed": diff,
            "mcnemar_p": round(p, 6), "false_alarm_rate": fa_rate,
            "false_alarm_ids": sorted(fa_ids),
        },
        "conditions": per,
        "conversion_failures": sorted(conv_fail),
        "misuse_cost_passes_tool_not_needed": misuse,
        "pass_overlaps": overlaps,
        "scorer_hash": scorer_hash,
        "scorer_hash_unchanged": None,  # filled by runner at summarize time
        "frozen_ok": frozen_ok,
    }
