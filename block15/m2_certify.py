"""M2 certification (no generation): sealed analyze, subprocess entrypoints, card safety,
confined-fix. Exits nonzero on failure; deterministic output hash for pre-registration.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from block15 import m2_tasks as M2T
from block15 import tool_transfer_fixtures as F
from block15 import tool_transfer_v3 as V3
from block15 import m2_research as M2

PY = sys.executable
MODULE = "block15.m2_research"
TN = list(M2T.TOOL_NEEDED_IDS)
TNN = list(M2T.TOOL_NOT_NEEDED_IDS)


def _run(args, env=None):
    e = dict(os.environ); e["PYTHONDONTWRITEBYTECODE"] = "1"; e["PYTHONIOENCODING"] = "utf-8"
    if env:
        e.update(env)
    p = subprocess.run([PY, "-m", MODULE, *args], capture_output=True, text=True,
                       encoding="utf-8", env=e, timeout=180)
    return {"returncode": p.returncode,
            "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
            "stderr": p.stderr.strip()}


def _write_synthetic(ddir):
    ddir.mkdir(parents=True, exist_ok=True)
    # Build synthetic records in M2's condition keys using V3 fixtures rows.
    recs = F.make_records(TN, TNN, fa_count=1, real_tn_passes=14, sham_tn_passes=4)
    out = {}
    for src, cond in (("L0_REAL", "CARD_NEG"), ("L0_SHAM", "CARD_FADE")):
        rec = dict(recs[src]); rec["condition"] = cond
        rec["scorer_blob_sha256"] = M2.scorer_blob_hash()
        (ddir / f"{M2.RESULTS_PREFIX}{cond}_synth.json").write_text(
            json.dumps(rec, ensure_ascii=True), encoding="utf-8")
        out[cond] = rec
    return out


def certify():
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        ddir = Path(td)
        _write_synthetic(ddir)
        # A1 atomic sealed analyze: inject failure -> nonzero, no file, no endpoint bytes
        outp = ddir / "s.json"
        r = _run(["--summarize", "--data-dir", str(ddir), "--out", str(outp),
                  "--inject-fail"])
        last = r["stderr"].strip().splitlines()[-1] if r["stderr"].strip() else ""
        no_endpoint = "ANALYSIS FAILED" in last and not any(c.isdigit() for c in last)
        checks["A1_atomic_seal"] = {
            "returncode_nonzero": r["returncode"] != 0,
            "no_file": not outp.exists(),
            "no_endpoint_bytes": no_endpoint,
            "pass": r["returncode"] != 0 and not outp.exists() and no_endpoint,
        }
        # A2 sealed summarize success + subprocess entrypoints (manifest, verify-cards)
        rsum = _run(["--summarize", "--data-dir", str(ddir), "--out", str(outp)])
        rman = _run(["--manifest"])
        rcard = _run(["--verify-cards"])
        seal_path = ddir / "seal.json"
        sealed = M2.sealed_compute(M2.load_records(ddir))
        seal_path.write_text(json.dumps(sealed, default=V3._json_default), encoding="utf-8")
        rverify = subprocess.run([PY, "-c",
            "import json,sys;from block15 import m2_research as M;"
            "print(M.verify_seal(json.load(open(sys.argv[1],encoding='utf-8'))))",
            str(seal_path)], capture_output=True, text=True, encoding="utf-8")
        checks["A2_entrypoints"] = {
            "summarize": rsum["returncode"], "manifest": rman["returncode"],
            "verify_cards": rcard["returncode"],
            "seal_verify_output": rverify.stdout.strip(),
            "pass": rsum["returncode"] == 0 and rman["returncode"] == 0
                    and rcard["returncode"] == 0
                    and rverify.stdout.strip() == "True",
        }
    # A3 card safety (no GT token, no task id) - direct
    cardcheck = M2.verify_cards_no_gt()
    checks["A3_card_safety"] = {"pass": all(
        not v["gt_token_hits"] and not v["task_id_hits"] for v in cardcheck.values())}
    # A4 confined-fix: reproduce prior counts via frozen scorer
    def load_where(pat):
        ps = sorted(Path("data").glob(pat))
        return json.loads(ps[-1].read_text()) if ps else None
    def recount(pat):
        d = load_where(pat)
        return sum(1 for r in d["results"] if (r.get("audit", {}) or {}).get("audit_passed", r.get("audit_passed")) and not r.get("copy_possible", False))
    counts = {
        "order_af": recount("block15_order_v2_results_answer_first_*.json"),
        "order_df": recount("block15_order_v2_results_derivation_first_*.json"),
        "skill_l3sham": recount("block15_skill_tool_results_L3_SHAM_*.json"),
        "skill_l0sham": recount("block15_skill_tool_results_L0_SHAM_*.json"),
    }
    expected = {"order_af": 0, "order_df": 18, "skill_l3sham": 2, "skill_l0sham": 2}
    checks["A4_confined_fix"] = {"counts": counts, "expected": expected,
                                 "pass": counts == expected}
    # A5 blob pins present
    scorer, runner = M2.scorer_blob_hash(), M2.runner_blob_hash()
    checks["A5_blob_pins"] = {"scorer": scorer, "runner": runner,
                              "pass": bool(scorer) and bool(runner)}
    all_pass = all(isinstance(v, dict) and v.get("pass", False) for v in checks.values())
    return {"certifier": "m2_certify_v1", "checks": checks, "all_passed": all_pass}


def main(argv=None):
    try:
        result = certify()
    except Exception as exc:
        print(json.dumps({"all_passed": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    blob = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["output_sha256"] = hashlib.sha256(blob).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
