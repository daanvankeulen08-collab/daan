# Pre-registration — Tool transfer V3 (certified harness, fresh generation)

**Status: pre-registered before any generation. No model call has been made for this V3 run.**

This is a NEW study after two CONTAMINATED attempts (V1: scorer `list & set` TypeError;
V2: runner undefined `scorer_blob_sha256` NameError). Both V1 and V2 were stopped per the
HARD RULE with NO re-scoring. The formal pre-registered endpoints (paired McNemar, false-
alarm rate, verdict matrix) were **never computed or observed** for V1/V2 — both
`--summarize` invocations crashed before producing any endpoint and no summary artifact
exists. Raw per-cell flags were visible in stored cells during read-only forensics, but
those are not the pre-registered endpoints and were not used to select tasks, criteria, or
fixes. The 30 tasks are reused because they are frozen and outcome-independent (verified
below), not because of any observed result.

Harness `block15/tool_transfer_v3.py`; certifier `block15/tool_transfer_v3_certify.py`;
backed by the certified scorer `block15/tool_transfer_score.py` and frozen tasks
`block15/tool_transfer_tasks.py`. Writes only new `data/block15_tool_transfer_v3_*` artifacts.
`block15/round3_report.py` is never executed.

## 0. Build + certify BEFORE generation (all green at commit `72afe6a`)

- **A1 atomic sealed analyze:** `sealed_summarize()` computes fully in memory, writes to a
  temp file, fsync, then `os.replace` (atomic) only on full success. On any exception
  nothing is written, nothing endpoint-bearing is printed. Test injects a mid-aggregation
  failure (`--inject-fail`) and asserts: nonzero exit, no summary file, no endpoint bytes
  (`ANALYSIS FAILED: RuntimeError` only). **PASS.**
- **A2 entrypoint coverage:** every post-generation command exercised on synthetic result
  files via **SUBPROCESS**, recording exit codes + stdout SHA-256: runner wrapper, scorer
  (bypass), G1, false-alarm aggregation, accounting, report writer, manifest, seal verify.
  Bypass proof: `--score` (unsealed) output is refused by both report writer (exit 2) and
  verify-seal (exit 2); sealed output accepted (`{"seal_valid": true}`). **PASS.**
  Exit codes: all post-gen commands 0; bypass report/verify 2. Output hashes in cert JSON.
- **A3 regressions:** `test_v1_false_alarm_list_set_regression` and
  `test_v2_wrapper_nameerror_regression` pass (plus 2 more) — 4 passed. **PASS.**
- **A4 confined-fix:** offline reproduce EXACTLY ORDER_V2 0/30+18/30, DIAGNOSIS A0 B2 C2,
  PLACEBO D1=3 D2=1, SKILL_TOOL L3_SHAM2 L0_SHAM2. **PASS (all four exact).**
- **A5 blob pins** (git blob SHA-256 at generation-time HEAD):
  - scorer `block15/tool_transfer_score.py`: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
  - runner `block15/tool_transfer_v3.py`: `212e9cf8d759f90a9710eb50ced466bc33486387032ed256a30f66bd836313e7`
  - Post-generation change to either ⇒ CONTAMINATED; stop, no re-score.
- **A6 `--certify`** runs A1–A4 and exits nonzero on any failure. Full output deterministic
  (verified identical across repeated runs). **Certification output SHA-256:**
  **`fd74465bdcc58257f132e7849c80c6beffd3bcef86ebcd0e754df3a0f1746e`**.
  No generation was started until certification was green and this hash recorded here.

## 1. Tasks — SAME 30 frozen V2 tasks
20 tool-needed minimality (`TFM01–TFM20`, first composite n≤64), 10 tool-not-needed
coefficient (`TFC01–TFC10`). Task manifest SHA-256
`138f2a1a441b9ce7ce59e61d0bfa147141878b003c10115ae840615ec52ec9a4` (unchanged from V2,
verified). `verify_tasks()` re-computes SymPy ground truth, asserts no GT token in any
prompt, distinct ids. Reused because frozen/outcome-independent (see preamble).

## 2. Conditions — L0_REAL, L0_SHAM only; NO card; identical TOOL_SCHEMA
Two calls per cell: call1 `num_predict=300` → tool_request JSON; call2 `num_predict=1200`
→ DERIVATION_FIRST_V2 final with tool result appended. REAL executes
`first_composite_quadratic`; SHAM returns `{"status":"unavailable"}`; condition never
revealed in any prompt. Sampling: seed 42, temp 0.1, top_p 1.0, repeat_penalty 1.1,
num_ctx 8192, think False, keep_alive 10m. Run order L0_REAL then L0_SHAM, single-flight.
Copy surface `r1_prompt` ONLY; `tool_result_used` recorded separately, never disqualifying.

## 3. G1 manipulation gate
Call-1 tool_request payloads byte-identical REAL vs SHAM (`call1_prompt_sha256`,
`raw_request`). Any difference ⇒ **INVALID** (reported first).

## 4. Endpoints and criteria
- **Primary (replication):** paired REAL − SHAM audited non-copy passes on the 20
  tool-needed tasks; McNemar exact; significance only at p<0.05.
- **Co-primary (discrimination):** false-alarm rate on the 10 tool-not-needed tasks.
- **Secondary:** parameter accuracy on tool-needed; conversion rate given correct params;
  misuse cost = REAL vs SHAM passes on tool-not-needed.
- **REPLICATED:** REAL > SHAM on tool-needed AND failed_cells lower (over **all 30 cells**,
  matching the TOTAL-failure guard; `account.failed_cells` is computed on all arm cells) AND G1 pass.
- **SELECTIVE:** false-alarm rate ≤ 0.30.
- **Verdict matrix:** REPLICATED+SELECTIVE → procedural selection demonstrated;
  REPLICATED+not SELECTIVE → parameter binding only, NOT selection (→ M2 per program goal);
  not REPLICATED → prior result did not transfer (report plainly).
- Guard TOTAL failures across all modes via `block15/accounting.py` (passes = 0 events).

### What a pass does not prove
Not unaided arithmetic (the tool supplies the answer), not general capability, not model
understanding beyond selection/parameterisation. Single seed, one tool, n=30.

## 5. Budget / execution
Max **130 calls**, **5400 s**, min free **450 MB**. Rationale: 120 planned calls; measured
35.27 s/call upper bound → 4232 s. New stores/run_id `block15_tool_transfer_v3_*`; results
`data/block15_tool_transfer_v3_results_<cond>_<ts>.json` (NOT matching `block15_round3_results_*`).
Refuse start if V3 results exist, FROZEN not byte-identical, tasks/drift checks fail, or
scorer/runner blob changed.

## 6. STOP conditions (categorical)
Endpoint revealed and unfavorable; fix not confined; G1 fails; FROZEN not 118/9ece313e;
budget trips; cannot prove no endpoint escaped a crash → STOP and report. No fix-and-rescore.

## 7. Protected manifest
FROZEN = ORDER_V2 118-path baseline, byte-identical (all `block15_tool_transfer*` excluded).
LIVE before/after are Git blob hashes at `72afe6a` (code commit) vs report HEAD.
PREREG/REPORT_TOOL_TRANSFER_V3.md are new root artifacts excluded from FROZEN.
