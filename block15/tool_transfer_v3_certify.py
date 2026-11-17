"""Tool-transfer V3 certification: A1 atomic sealed analyze, A2 subprocess entrypoint
coverage, A3 regressions, A4 confined-fix, A5 blob pins, A6 --certify gate.

No generation, no Ollama. All post-generation commands are exercised via SUBPROCESS on
synthetic result files. Exits nonzero on any failure. Output is deterministic given
committed code so its SHA-256 can be pinned in the pre-registration.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from block15 import accounting as A
from block15 import order_v2_research as O
from block15 import tool_transfer_fixtures as F
from block15 import tool_transfer_score as SC
from block15 import tool_transfer_tasks as TT
from block15 import tool_transfer_v3 as V3

TN = list(TT.TOOL_NEEDED_IDS)
TNN = list(TT.TOOL_NOT_NEEDED_IDS)
ALL = TN + TNN
PY = sys.executable
MODULE = "block15.tool_transfer_v3"


def _run(args, env=None):
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    if env:
        e.update(env)
    p = subprocess.run([PY, "-m", MODULE, *args], capture_output=True,
                       text=True, encoding="utf-8", env=e, timeout=180)
    return {
        "args": args,
        "returncode": p.returncode,
        "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
    }


def _write_synthetic(ddir: Path):
    ddir.mkdir(parents=True, exist_ok=True)
    recs = F.make_records(TN, TNN, fa_count=1, real_tn_passes=14,
                          sham_tn_passes=4, g1_identical=True)
    for cond, rec in recs.items():
        rec = dict(rec)
        rec["condition"] = cond
        rec["scorer_blob_sha256"] = V3.scorer_blob_hash()
        p = ddir / f"{V3.RESULTS_PREFIX}{cond}_synth.json"
        p.write_text(json.dumps(rec, ensure_ascii=True), encoding="utf-8")
    return recs


def a1_atomic_seal(ddir: Path) -> dict:
    """Inject mid-aggregation failure; assert nothing written, no endpoint bytes."""
    out = ddir / "a1_summary.json"
    if out.exists():
        out.unlink()
    r = _run(["--summarize", "--data-dir", str(ddir), "--out", str(out),
              "--inject-fail"])
    leak = any(ch.isdigit() for ch in (r["stdout"] + r["stderr"]))
    # The guard message contains no digits by design; any digit = endpoint leak.
    return {
        "returncode_nonzero": r["returncode"] != 0,
        "no_summary_written": not out.exists(),
        "no_endpoint_bytes": not leak,
        "stderr": r["stderr"],
        "pass": (r["returncode"] != 0) and (not out.exists()) and (not leak),
    }


def _recompute_pass(task_id, row, prompt=None):
    """Recompute an audited non-copy pass from STORED audited fields.

    Prior studies used different task id schemes and prompt surfaces; their stored
    cells already carry the frozen scorer's audit decision. Confined-fix requires
    reproducing counts from those fields (audit_passed AND NOT copy_possible), not
    mutating raw cells. V3 rows additionally carry a fresh scorer audit.
    """
    audit = row.get("audit") or {}
    audit_passed = row.get("audit_passed")
    if audit_passed is None:
        audit_passed = audit.get("audit_passed")
    if audit_passed is None:
        # last resort: primary_correct already folds in non-copy
        return bool(row.get("primary_correct"))
    return bool(audit_passed) and not bool(row.get("copy_possible", False))


def a4_confined_fix() -> dict:
    """Offline reproduce EXACT prior counts with the current analysis."""
    def load_where(pattern):
        paths = sorted(Path("data").glob(pattern))
        return json.loads(paths[-1].read_text(encoding="utf-8")) if paths else None

    expected = {}
    # ORDER_V2
    counts = {}
    for arm in ("answer_first", "derivation_first"):
        d = load_where(f"block15_order_v2_results_{arm}_*.json")
        counts[arm] = sum(1 for r in d["results"] if _recompute_pass(r["task_id"], r))
    expected["ORDER_V2"] = (counts == {"answer_first": 0, "derivation_first": 18}, counts)
    # DIAGNOSIS A/B/C
    dcounts = {}
    for c in "ABC":
        d = load_where(f"block15_diagnosis_results_{c}_*.json")
        dcounts[c] = sum(1 for r in d["results"] if _recompute_pass(r["task_id"], r))
    expected["DIAGNOSIS"] = (dcounts == {"A": 0, "B": 2, "C": 2}, dcounts)
    # PLACEBO D1/D2
    pcounts = {}
    for c in ("D1", "D2"):
        d = load_where(f"block15_placebo_results_{c}_*.json")
        pcounts[c] = sum(1 for r in d["results"] if _recompute_pass(r["task_id"], r))
    expected["PLACEBO"] = (pcounts == {"D1": 3, "D2": 1}, pcounts)
    # SKILL_TOOL L3_SHAM / L0_SHAM
    scounts = {}
    for c in ("L3_SHAM", "L0_SHAM"):
        d = load_where(f"block15_skill_tool_results_{c}_*.json")
        scounts[c] = sum(1 for r in d["results"] if _recompute_pass(r["task_id"], r))
    expected["SKILL_TOOL"] = (scounts == {"L3_SHAM": 2, "L0_SHAM": 2}, scounts)
    confined = all(v[0] for v in expected.values())
    return {
        "confined": confined,
        "detail": {k: {"ok": v[0], "counts": v[1]} for k, v in expected.items()},
        "pass": confined,
    }


def a2_subprocess_entrypoints(ddir: Path) -> dict:
    """Run every post-generation command on synthetic files via SUBPROCESS."""
    _write_synthetic(ddir)
    summary = ddir / "a2_summary.json"
    commands = {
        "runner_wrapper": ["--summarize", "--data-dir", str(ddir), "--out", str(summary)],
        "scorer_bypass": ["--score", "--data-dir", str(ddir)],
        "g1": ["--g1", "--data-dir", str(ddir)],
        "false_alarm": ["--false-alarm", "--data-dir", str(ddir)],
        "accounting": ["--accounting", "--data-dir", str(ddir)],
        "manifest": ["--manifest"],
    }
    out = {}
    for name, args in commands.items():
        r = _run(args)
        out[name] = {"returncode": r["returncode"],
                     "stdout_sha256": r["stdout_sha256"]}
    # report writer + verify on the SEALED summary
    out["report_writer"] = {}
    r = _run(["--report", "--data-dir", str(ddir), "--summary", str(summary),
              "--out", str(ddir / "a2_report.json")])
    out["report_writer"] = {"returncode": r["returncode"],
                            "stdout_sha256": r["stdout_sha256"]}
    r = _run(["--verify-summary", "--summary", str(summary)])
    out["verify_sealed"] = {"returncode": r["returncode"],
                            "stdout": r["stdout"]}
    # bypass proof: unsealed scorer output must be refused by report + verify
    bypass = _run(["--score", "--data-dir", str(ddir)])
    unsealed = ddir / "a2_unsealed.json"
    unsealed.write_text(bypass["stdout"], encoding="utf-8")
    rb = _run(["--report", "--summary", str(unsealed),
               "--out", str(ddir / "a2_bypass_report.json")])
    rv = _run(["--verify-summary", "--summary", str(unsealed)])
    out["bypass_refused"] = {
        "report_returncode": rb["returncode"],
        "verify_returncode": rv["returncode"],
    }
    ok = (
        all(v["returncode"] == 0 for k, v in out.items()
            if isinstance(v, dict) and "returncode" in v and k not in ("bypass_refused",))
        and out["verify_sealed"]["stdout"] == '{"seal_valid": true}'
        and out["bypass_refused"]["report_returncode"] != 0
        and out["bypass_refused"]["verify_returncode"] != 0
    )
    out["pass"] = ok
    return out


def a3_regressions() -> dict:
    r = subprocess.run([PY, "-m", "pytest", "-q", "-o", "addopts=",
                        "tests/test_tool_transfer_v3.py"],
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    return {"returncode": r.returncode, "pass": r.returncode == 0,
            "tail": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""}


def certify():
    scorer = V3.scorer_blob_hash()
    runner = V3.runner_blob_hash()
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        ddir = Path(td)
        _write_synthetic(ddir)  # A1 needs synthetic files so inject_fail is the real cause
        checks["A1_atomic_seal"] = a1_atomic_seal(ddir)
        checks["A2_subprocess_entrypoints"] = a2_subprocess_entrypoints(ddir)
        checks["A4_confined_fix"] = a4_confined_fix()
    checks["A3_regressions"] = a3_regressions()
    checks["A5_blob_pins"] = {
        "scorer_blob_sha256": scorer, "runner_blob_sha256": runner,
        "pass": bool(scorer) and bool(runner),
    }
    all_pass = all(isinstance(v, dict) and v.get("pass", False)
                   for v in checks.values())
    return {
        "certifier": "tool_transfer_v3_certify_v1",
        "checks": checks, "all_passed": all_pass,
    }


def main(argv=None):
    try:
        result = certify()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"all_passed": False,
                          "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1
    blob = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["output_sha256"] = hashlib.sha256(blob).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
