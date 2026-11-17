"""Synthetic fixtures for certifying tool_transfer_score.summarize() end-to-end.

Pure offline data builders — no Ollama, no model generation.  These exercise
all aggregation branches including the type-correctness of every set/list
operation that previously raised TypeError.
"""
from __future__ import annotations


def make_row(task_id, *, primary=False, requested=True, params_ok=True,
             used=False, valid=True, raw="{}", status="ok", done="stop",
             copy=False, conf=0.9, validate_ok=True, pv_hash="same", raw_request="req"):
    """Build a minimal row carrying every field summarize()/accounting reads."""
    return {
        "task_id": task_id,
        "primary_correct": primary,
        "tool_requested": requested,
        "parameters_correct": params_ok,
        "tool_result_used": used,
        "tool_request_valid": valid,
        "raw_content": raw,
        "status": status,
        "done_reason": done,
        "copy_possible": copy,
        "confidence_raw": conf,
        "validate_v2_ok": validate_ok,
        "call1_prompt_sha256": pv_hash,
        "raw_request": raw_request,
    }


def make_records(tn_ids, tnn_ids, *, fa_count, real_tn_passes, sham_tn_passes,
                 g1_identical=True, conv_fail=False, missing_raw=False):
    """Build a records dict for L0_REAL / L0_SHAM.

    fa_count: number of tool-not-needed tasks with an inappropriate tool_request
              in L0_REAL (0, 1, or 10 as needed).
    real_tn_passes / sham_tn_passes: number of tool-needed tasks that pass.
    """
    all_ids = list(tn_ids) + list(tnn_ids)
    real_rows, sham_rows = [], []
    for i, tid in enumerate(tn_ids):
        real_rows.append(make_row(
            tid, primary=(i < real_tn_passes), requested=True, params_ok=True,
            used=(i < real_tn_passes), raw=None if (missing_raw and i == 0) else "{}",
        ))
        sham_rows.append(make_row(
            tid, primary=(i < sham_tn_passes), requested=True, params_ok=True,
            used=False, pv_hash="same", raw_request="req",
        ))
    for j, tid in enumerate(tnn_ids):
        fa = j < fa_count
        real_rows.append(make_row(
            tid, primary=False, requested=fa, params_ok=False, used=False,
        ))
        sham_rows.append(make_row(tid, primary=False, requested=fa, used=False))

    if not g1_identical:
        # Break byte-identity of call-1 payload on one tool-needed cell (REAL only)
        real_rows[0]["raw_request"] = "DIFFERENT"
    if conv_fail and real_tn_passes < len(tn_ids):
        # make one cell have correct params + result used + wrong answer
        real_rows[real_tn_passes]["used"] = True

    return {
        "L0_REAL": {"results": real_rows, "condition": "L0_REAL"},
        "L0_SHAM": {"results": sham_rows, "condition": "L0_SHAM"},
    }
