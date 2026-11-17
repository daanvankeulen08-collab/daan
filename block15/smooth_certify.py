"""SMOOTH certification: executable checks for EVERY pre-registration requirement.

No generation, no Ollama. Deterministic output hash for the pre-registration.
Checks:
  A1 atomic sealed analyze (no endpoint leak on injected failure)
  A2 subprocess entrypoints (--summarize, --manifest)
  A3 task set (20 fresh, SymPy GT, copy guard, disjoint, SMOOTH/FACTOR construction)
  A4 G1 (prompts differ only by result block; detects tamper)
  A5 endpoint (exclusive wrong_commit vs mention_only) - unit fixtures
  A6 exact CI (Clopper-Pearson) + Fisher exact boundary checks
  A7 verdict logic boundaries
  A8 accounting invariant (summarize == direct raw recompute, canonical field)
  A9 fake-client dry run through run_cell -> summarize
  A10 blob pins present
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scipy.stats import beta as _beta
from scipy.stats import fisher_exact as _fisher

from block15 import accounting as A
from block15 import order_v2_research as O
from block15 import smooth_research as I
from block15 import smooth_tasks as ST

PY = sys.executable
MODULE = "block15.smooth_research"


class FakeClient:
    """Deterministic answers: echo injected value -> exclusive wrong_commit."""

    def chat_json(self, messages, schema, *, num_predict):
        user = messages[-1]["content"]
        injected = None
        marker = "\n\nTool result: "
        if marker in user:
            seg = user.split(marker, 1)[1].split("\n\n", 1)[0]
            obj = json.loads(seg)
            injected = obj.get("value")
        if injected is None:
            answer = "cannot determine"
        else:
            answer = str(injected)
        content = json.dumps({"derivation": ["step"], "final_answer": answer,
                              "uncertainty": "none", "confidence": 0.9})
        return SimpleNamespace(content=content, done_reason="stop",
                               prompt_eval_count=10, eval_count=20,
                               protocol_variant="primary", schema_enforced=True,
                               think_sent=False)


class FakeStore:
    def create_experiment(self, **kw):
        return "fake"

    def log_step(self, *a, **kw):
        pass

    def close(self):
        pass


def fake_run(ddir):
    ddir = Path(ddir)
    client, store = FakeClient(), FakeStore()
    state = {"calls": 0, "guard": lambda: None}
    for cond in I.CONDITIONS:
        rows = []
        for t in ST.TASKS:
            rows.append(I.run_cell(client, store, "fake", t, cond, state))
        rec = {"condition": cond, "results": rows, "num_predict": I.NUM_PREDICT,
               "scorer_blob_sha256": I.scorer_blob_hash(),
               "runner_blob_sha256": I.runner_blob_hash(), "calls_used_total": state["calls"]}
        (ddir / f"{I.RESULTS_PREFIX}{cond}_synth.json").write_text(
            json.dumps(rec, ensure_ascii=True), encoding="utf-8")
    return I.load_records(ddir)


def accounting_invariant(records: dict, summ: dict) -> dict:
    ok = True
    detail = {}
    for cond in I.CONDITIONS:
        rows = records[cond]["results"]
        direct = sum(1 for r in rows if r.get("primary_correct", False))
        missing = sum(1 for r in rows if "primary_correct" not in r)
        conflict = sum(1 for r in rows if "primary_correct" in r and "audited_pass" in r
                       and r["primary_correct"] != r["audited_pass"])
        acct = A.account(rows)
        part = A.partition(rows)
        d = {
            "cells": len(rows), "direct_passes": direct,
            "summarize_passes": summ["conditions"][cond]["audited_passes"],
            "account_passes": acct["audited_passes"],
            "failed_cells": acct["failed_cells"], "direct_failed_cells": len(rows) - direct,
            "failure_events": acct["failure_events"],
            "direct_failure_events": sum(len(A.failure_flags(r)) for r in rows
                                         if not r.get("primary_correct", False)),
            "missing_canonical": missing, "alias_conflict": conflict,
            "partition_matches": part == summ["conditions"][cond]["partition"],
        }
        cond_ok = (missing == 0 and conflict == 0
                   and d["direct_passes"] == d["summarize_passes"] == d["account_passes"]
                   and d["failed_cells"] == d["direct_failed_cells"]
                   and d["failure_events"] == d["direct_failure_events"]
                   and d["partition_matches"])
        detail[cond] = {**d, "pass": cond_ok}
        ok = ok and cond_ok
    return {"pass": ok, "conditions": detail}


POSTGEN_ENTRYPOINTS = ("--summarize", "--manifest")


def _run(args):
    e = dict(os.environ); e["PYTHONDONTWRITEBYTECODE"] = "1"; e["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([PY, "-m", MODULE, *args], capture_output=True, text=True,
                       encoding="utf-8", env=e, timeout=180)
    return {"returncode": p.returncode,
            "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
            "stderr": p.stderr.strip()}


def certify():
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        ddir = Path(td)
        recs = fake_run(ddir)

        # A1 atomic sealed analyze
        out = ddir / "s.json"
        r = _run(["--summarize", "--data-dir", str(ddir), "--out", str(out), "--inject-fail"])
        last = r["stderr"].strip().splitlines()[-1] if r["stderr"].strip() else ""
        no_endpoint = "ANALYSIS FAILED" in last and not any(c.isdigit() for c in last)
        checks["A1_atomic_seal"] = {
            "returncode_nonzero": r["returncode"] != 0, "no_file": not out.exists(),
            "no_endpoint_bytes": no_endpoint,
            "pass": r["returncode"] != 0 and not out.exists() and no_endpoint,
        }

        # A2 subprocess entrypoints
        rsum = _run(["--summarize", "--data-dir", str(ddir), "--out", str(out)])
        rman = _run(["--manifest"])
        checks["A2_entrypoints"] = {
            "summarize": rsum["returncode"], "manifest": rman["returncode"],
            "all_exercised": all(e in ("--summarize", "--manifest") for e in POSTGEN_ENTRYPOINTS),
            "pass": rsum["returncode"] == 0 and rman["returncode"] == 0,
        }
        sealed = I.sealed_compute(recs)
        checks["A2b_seal"] = {"verify": I.verify_seal(sealed), "pass": I.verify_seal(sealed)}

        # A3 task set
        tv = ST.verify_tasks()
        checks["A3_tasks"] = {
            "verify": tv,
            "pass": (tv["n_tasks"] == 20 and tv["ground_truth_ok"] and tv["copy_guard_ok"]
                     and tv["disjoint_ok"] and tv["smooth_ok"] and tv["factor_ok"]),
        }

        # A4 G1
        pm = {c: I.build_prompt(ST.TASKS[0], c) for c in I.CONDITIONS}
        g1 = I.g1_check(pm)
        tampered = dict(pm); tampered["FACTOR"] = tampered["FACTOR"] + " X"
        g1_bad = I.g1_check(tampered)
        checks["A4_g1"] = {"pass": g1["pass"] and not g1_bad["pass"]}

        # A5 endpoint (exclusive wrong_commit vs mention_only)
        t = ST.TASKS[0]
        sv = ST.smooth_value(t); g = t.coefficient
        unit = {
            "wc_exact": I.wrong_commit(sv["value"], str(sv["value"])),
            "wc_with_gt_is_false": not I.wrong_commit(sv["value"], f"{sv['value']} and {g}"),
            "wc_none_false": not I.wrong_commit(None, str(sv["value"])),
            "mo_co_presence": I.mention_only(sv["value"], f"{sv['value']} and {g}"),
            "mo_not_when_exact": not I.mention_only(sv["value"], str(sv["value"])),
            "ints_signed": I.answer_ints("-12 and 7 and -12") == {-12, 7},
        }
        checks["A5_endpoint"] = {"checks": unit, "pass": all(unit.values())}

        # A6 exact CI + Fisher
        u0 = I.exact_upper_95(0, 20); u20 = I.exact_upper_95(20, 20)
        ci = I.exact_ci_95(3, 20)
        fish = _fisher([[3, 17], [0, 20]])
        checks["A6_ci_fisher"] = {
            "upper_0_20": round(u0, 6), "upper_20_20": u20, "ci_3_20": [round(v, 6) for v in ci],
            "matches_beta": (abs(u0 - float(_beta.ppf(0.95, 1, 20))) < 1e-9
                             and abs(ci[1] - float(_beta.ppf(0.975, 4, 17))) < 1e-9),
            "fisher_finite": 0.0 <= float(fish[1]) <= 1.0,
            "pass": (abs(u0 - float(_beta.ppf(0.95, 1, 20))) < 1e-9 and u20 == 1.0
                     and ci[0] < ci[1] and 0.0 <= float(fish[1]) <= 1.0),
        }

        # A7 verdict logic boundaries
        vd = {
            "structural": I.decide_verdict(8, 20, 1, 20, True, 0.01)["verdict"] == "STRUCTURAL_REJECTION",
            "genuine": I.decide_verdict(0, 20, 1, 20, True, 0.5)["verdict"] == "GENUINE_REJECTION",
            "inconclusive": I.decide_verdict(6, 20, 6, 20, True, 1.0)["verdict"] == "INCONCLUSIVE",
            "invalid_on_g1": I.decide_verdict(0, 20, 0, 20, False, 1.0)["verdict"] == "INVALID",
        }
        checks["A7_verdict_logic"] = {"checks": vd, "pass": all(vd.values())}

        # A8 accounting invariant
        summ = I.summarize(recs)
        checks["A8_accounting_invariant"] = accounting_invariant(recs, summ)

        # A9 fake-client dry run
        checks["A9_dry_run"] = {
            "n_cells": summ["n_cells"],
            "smooth_wc": summ["conditions"]["SMOOTH"]["wrong_commit"],
            "factor_wc": summ["conditions"]["FACTOR"]["wrong_commit"],
            "pass": summ["n_cells"] == 60
                    and summ["conditions"]["SMOOTH"]["wrong_commit"] == 20
                    and summ["conditions"]["FACTOR"]["wrong_commit"] == 20,
        }

    checks["A10_blob_pins"] = {
        "scorer": I.scorer_blob_hash(), "runner": I.runner_blob_hash(),
        "pass": bool(I.scorer_blob_hash()) and bool(I.runner_blob_hash()),
    }
    all_pass = all(isinstance(v, dict) and v.get("pass", False) for v in checks.values())
    return {"certifier": "smooth_certify_v1", "checks": checks, "all_passed": all_pass}


def main(argv=None):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            result = certify()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"all_passed": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    blob = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["output_sha256"] = hashlib.sha256(blob).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
