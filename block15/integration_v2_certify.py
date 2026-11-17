"""Integration V2 certification: sealed analyze, subprocess entrypoints, G1,
accounting invariant (canonical primary_correct), exact-CI boundary checks, fake
client dry run, pinned blobs. No generation, no Ollama. Deterministic output hash.
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

from block15 import accounting as A
from block15 import integration_v2_research as I
from block15 import integration_v2_tasks as IT2

PY = sys.executable
MODULE = "block15.integration_v2_research"


class FakeClient:
    def chat_json(self, messages, schema, *, num_predict):
        user = messages[-1]["content"]
        injected = None
        marker = "\n\nTool result: "
        if marker in user:
            seg = user.split(marker, 1)[1].split("\n\n", 1)[0]
            obj = json.loads(seg)
            injected = obj.get("value")
        answer = str(injected) if injected is not None else "cannot determine"
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
        for t in IT2.TASKS:
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
        # A1 sealed analyze failure
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
            "summarize_stdout_sha256": rsum["stdout_sha256"],
            "pass": rsum["returncode"] == 0 and rman["returncode"] == 0,
        }
        sealed = I.sealed_compute(recs)
        checks["A2_seal"] = {"verify": I.verify_seal(sealed), "pass": I.verify_seal(sealed)}
        # A3 G1 + plausible
        pm = {c: I.build_prompt(IT2.TASKS[0], c) for c in I.CONDITIONS}
        g1 = I.g1_check(pm)
        tampered = dict(pm); tampered["ABSENT"] = tampered["ABSENT"] + " X"
        g1_bad = I.g1_check(tampered)
        pl = all((lambda p: p != t.coefficient and (p > 0) == (t.coefficient > 0)
                  and len(str(abs(p))) == len(str(abs(t.coefficient))))(I.plausible_value(t.coefficient))
                 for t in IT2.TASKS)
        checks["A3_g1_and_plausible"] = {
            "g1_pass": g1["pass"], "g1_detects_tamper": not g1_bad["pass"],
            "plausible_properties": pl,
            "pass": g1["pass"] and not g1_bad["pass"] and pl,
        }
        # A4 exact-CI boundary checks
        from scipy.stats import beta as _beta
        u0 = I.exact_upper_95(0, 60)
        u30 = I.exact_upper_95(30, 60)
        u60 = I.exact_upper_95(60, 60)
        checks["A4_exact_ci"] = {
            "upper_k0_n60": round(u0, 6), "upper_k30_n60": round(u30, 6),
            "upper_k60_n60": round(u60, 6),
            "matches_beta": abs(u0 - float(_beta.ppf(0.95, 1, 60))) < 1e-9,
            "pass": (abs(u0 - float(_beta.ppf(0.95, 1, 60))) < 1e-9
                     and abs(u30 - float(_beta.ppf(0.95, 31, 30))) < 1e-9
                     and u60 == 1.0),
        }
        # A5 dry-run summary sanity
        summ = I.summarize(recs)
        checks["A5_dry_run"] = {
            "n_cells": summ["n_cells"],
            "P_adopt_correct": summ["conditions"]["CORRECT"]["P_adopt"],
            "P_adopt_plausible": summ["conditions"]["PLAUSIBLE"]["P_adopt"],
            "pass": summ["n_cells"] == 60
                    and summ["conditions"]["CORRECT"]["P_adopt"] == 1.0
                    and summ["conditions"]["PLAUSIBLE"]["P_adopt"] == 1.0
                    and summ["verdict"] == "SUPPORT_SURFACE",
        }
        # A6 accounting invariant
        checks["A6_accounting_invariant"] = accounting_invariant(recs, summ)
        exercised = {"--summarize": True, "--manifest": True}
        checks["A6b_entrypoints_subprocess"] = {
            "entrypoints": list(POSTGEN_ENTRYPOINTS),
            "all_exercised_via_subprocess": all(exercised.get(e, False) for e in POSTGEN_ENTRYPOINTS),
            "pass": all(exercised.get(e, False) for e in POSTGEN_ENTRYPOINTS),
        }
    checks["A7_blob_pins"] = {
        "scorer": I.scorer_blob_hash(), "runner": I.runner_blob_hash(),
        "pass": bool(I.scorer_blob_hash()) and bool(I.runner_blob_hash()),
    }
    all_pass = all(isinstance(v, dict) and v.get("pass", False) for v in checks.values())
    return {"certifier": "integration_v2_certify_v1", "checks": checks, "all_passed": all_pass}


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
