"""Offline certification for the tool-transfer scorer + runner pipeline.

Runs with NO Ollama: a fake client drives run_cell() through call1 (tool request)
and call2 (final answer), with real tool execution or sham, then calls the frozen
scorer's summarize(). Exits nonzero on any failure. Output is deterministic so a
hash can be pinned in the pre-registration.
"""
from __future__ import annotations

import hashlib
import json
import sys
from types import SimpleNamespace

from block15 import tool_transfer_fixtures as F
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_tasks as TT
from block15 import tool_transfer_research as R
from block15 import tool_transfer_score as SCORE

TN = list(TT.TOOL_NEEDED_IDS)
TNN = list(TT.TOOL_NOT_NEEDED_IDS)
ALL = TN + TNN


class FakeClient:
    """Emits deterministic tool_request (call1) + final answer (call2)."""

    def __init__(self, *, request_tool=True, wrong_params=False, real_final=True):
        self.request_tool = request_tool
        self.wrong_params = wrong_params
        self.real_final = real_final

    def chat_json(self, messages, schema, *, num_predict):
        user = messages[-1]["content"]
        if num_predict == 300:
            # Call 1: return a tool_request JSON. Determine a,b,c from the task
            # by matching the question text against frozen tasks.
            task = _task_from_prompt(user)
            args = {"a": task.a if task.a is not None else 1,
                    "b": task.b if task.b is not None else 0,
                    "c": task.c if task.c is not None else 1,
                    "n_max": 64}
            if self.wrong_params:
                args["c"] = args["c"] + 1
            req = {"tool_request": {"tool": "first_composite_quadratic",
                                    "arguments": args}} if self.request_tool else {"tool_request": None}
            content = json.dumps(req)
        else:
            # Call 2: infer tool result from prompt; produce a final answer.
            if '"status":"unavailable"' in user or '"status": "unavailable"' in user:
                answer = "cannot determine"
            else:
                truth = _truth_from_prompt(user)
                if truth and self.real_final:
                    if truth["kind"] == "minimality":
                        answer = (f"n = {truth['n']}, f(n) = {truth['value']}, "
                                  f"prime factorization = {' * '.join(str(p) for p in truth['primes'])}")
                    else:
                        answer = str(truth["coefficient"])
                else:
                    answer = "wrong"
            content = json.dumps({
                "derivation": ["step"],
                "final_answer": answer,
                "uncertainty": "none",
                "confidence": 0.9,
            })
        return SimpleNamespace(
            content=content, done_reason="stop", prompt_eval_count=10,
            eval_count=20, protocol_variant="primary", schema_enforced=True,
            think_sent=False,
        )


def _task_from_prompt(user):
    for t in TT.TASKS:
        if t.question in user:
            return t
    return TT.TASKS[0]


def _truth_from_prompt(user):
    for t in TT.TASKS:
        if t.question in user:
            return t.truth()
    return None


class FakeStore:
    def log_step(self, *a, **k):
        pass


def fake_dry_run():
    """Drive run_cell for both conditions on a subset, then summarize()."""
    subset = TT.TASKS[:4] + TT.TASKS[20:22]  # 2 tool-needed + 2 tool-not-needed
    recs = {}
    for cond in ("L0_REAL", "L0_SHAM"):
        client = FakeClient(request_tool=True, wrong_params=False, real_final=True)
        state = {"calls": 0, "guard": lambda: None}
        rows = []
        for t in subset:
            # For SHAM, run_cell uses tool_result=unavailable automatically via cond.
            rows.append(R.run_cell(client, FakeStore(), "exp", t, cond, state))
        recs[cond] = {"results": rows, "condition": cond}
    out = SC.summarize(recs, [t.id for t in subset],
                       [t.id for t in subset if t.kind == "minimality"],
                       "certify-hash", True)
    return {
        "cells_per_condition": {c: len(recs[c]["results"]) for c in recs},
        "tool_execution_exercised": any(
            isinstance(r["tool_result"], dict) and "n" in r["tool_result"]
            for r in recs["L0_REAL"]["results"]
        ),
        "sham_exercised": any(
            r["tool_result"] == {"status": "unavailable"}
            for r in recs["L0_SHAM"]["results"]
        ),
        "call1_call2_exercised": all(
            "call1" in r and "call2" in r
            for c in recs for r in recs[c]["results"]
        ),
        "summary_verdict": out["verdict"],
        "summary_computed": True,
    }


def certify():
    checks = {}
    # 1. False-alarm fixtures 0/1/10
    fa = {}
    for k in (0, 1, 10):
        out = SC.summarize(F.make_records(TN, TNN, fa_count=k,
                                          real_tn_passes=14, sham_tn_passes=4),
                           ALL, TN, "h", True)
        fa[str(k)] = out["criteria"]["false_alarm_rate"]
    checks["false_alarm_rates"] = fa
    assert fa == {"0": 0.0, "1": 0.1, "10": 1.0}, fa
    # 2. Empty tool-needed
    out = SC.summarize(F.make_records([], TNN, fa_count=0,
                                      real_tn_passes=0, sham_tn_passes=0),
                       TNN, [], "h", True)
    checks["empty_tn_p"] = out["criteria"]["mcnemar_p"]
    assert out["criteria"]["mcnemar_p"] == 1.0
    # 3. G1 identity / violation
    g1a = SC.summarize(F.make_records(TN, TNN, fa_count=0,
                                      real_tn_passes=14, sham_tn_passes=4,
                                      g1_identical=True), ALL, TN, "h", True)
    g1b = SC.summarize(F.make_records(TN, TNN, fa_count=0,
                                      real_tn_passes=14, sham_tn_passes=4,
                                      g1_identical=False), ALL, TN, "h", True)
    checks["g1_identical"] = g1a["G1"]["verdict"]
    checks["g1_violation"] = g1b["G1"]["verdict"]
    assert (g1a["G1"]["verdict"], g1b["G1"]["verdict"]) == ("PASS", "INVALID")
    # 4. passes contribute zero events
    rows = [F.make_row(f"T{i:02d}_x", primary=True, conf=99, copy=True,
                       status="error", done="length") for i in range(5)]
    from block15 import accounting as A
    checks["pass_events"] = A.account(rows)["failure_events"]
    assert checks["pass_events"] == 0
    # 5. fake-client end-to-end
    checks["dry_run"] = fake_dry_run()
    d = checks["dry_run"]
    assert d["summary_computed"] and d["tool_execution_exercised"]
    assert d["sham_exercised"] and d["call1_call2_exercised"]
    assert d["cells_per_condition"] == {"L0_REAL": 6, "L0_SHAM": 6}
    result = {
        "certifier": "tool_transfer_certify_v1",
        "scorer_version": SC.SCORER_VERSION,
        "checks": checks,
        "all_passed": True,
    }
    return result


def main(argv=None):
    import contextlib
    import io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            result = certify()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"all_passed": False, "error": f"{type(exc).__name__}: {exc}"},
                         indent=2))
        return 1
    blob = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["output_sha256"] = hashlib.sha256(blob).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
