# Pre-registration — Diagnosis-guided retry on the 12 ORDER_V2 failures

**Status: pre-registered before any generation. No model call has been made in this block.**

This document fixes the machine classification, conditions, endpoint, gates and budget
for the diagnosis-guided retry study. It is committed before generation. The harness is
`block15/diagnosis_research.py`, writing only new `data/block15_diagnosis_*` artifacts.
`block15/round3_report.py` is never executed.

---

## 0. STEP 0 record fixes (this block)

1. `REPORT_ORDER_V2.md` pass breakdown corrected to **13 bare integers + 1 verbose
   (V2C12) + 4 minimality = 18**; the mistaken "15/15 coefficient, 3/15 minimality"
   line was corrected to 14/15 coefficient and 4/15 minimality. Verified against raw cells.
2. Strict-diagnostic count added: **17 of 18** ORDER_V2 passes also pass the stored
   `strict_single_int` / `strict_set_equal` diagnostic; the sole exception is the verbose
   V2C12. This is only 1 lower than 18 — stated plainly, not materially lower.
3. Additive helper `git_blob_sha256` added to `block15/order_v2_research.py`; the module
   hash is now the **Git blob hash** (line-ending invariant) and is stored **per arm** in
   future result files. `summarize()` records `module_sha256` as the blob hash and keeps
   the worktree hash as `module_worktree_sha256`. No result cell changed.

---

## 1. Contract (identical in all conditions)

* Schema: **`DERIVATION_FIRST_V2`** (the ORDER_V2 derivation-first schema; SHA-256
  `7ca06e0060d04bd42c13ec7bf232404217acb0963f10f2af467cabe17ab7ef53`).
* Instruction: shared neutral `OUTPUT_INSTRUCTION_V2` **plus exactly one** schema-order
  sentence `"Emit the fields in the order required by the schema, not in the order they
  are listed here."` — unchanged from ORDER_V2.
* System prompt: `SYSTEM_PROMPT_V2` (Round 3 verbatim), SHA-256
  `ee09cc7bc5a939cb6638e5d33c9505e7e9b20f327274f2360be2a7e4e9152710`.
* Sampling identical to ORDER_V2: `think=False`, `num_ctx=8192`, `temperature=0.1`,
  `top_p=1.0`, `repeat_penalty=1.1`, `seed=42`, `keep_alive=10m`, `num_predict=1200`.
* **Only the appended feedback text differs between conditions.** No retry, repair,
  teacher hint, training, dependency change, network model API or model download.

---

## 2. Tasks — exactly the 12 derivation_first failures, in ORDER_V2 task order

`V2C02, V2M02, V2M03, V2M04, V2M06, V2M07, V2M08, V2M09, V2M10, V2M11, V2M14, V2M15`.

The baseline for all 12 is the **stored ORDER_V2 derivation_first output** for that task.

---

## 3. Machine classification (first match wins)

Precedence: **1 TRUNCATION** (`done_reason=="length"`) → **2 INVALID_JSON** (unparseable
at stop) → **3 SCHEMA_VIOLATION** (`validate_v2` violations > 0) → **4 NO_SEARCH**
(required search bound not reached; minimality: model never tested up to the true first
composite n) → **5 ARITHMETIC_ERROR** (a checkable numeric claim in the derivation is
false, verified with SymPy, step and false claim named) → **6 CONTRACT_MISMATCH**
(`final_answer` wrong while derivation contains all ground-truth tokens). No forced class:
anything unmatched is **UNCLASSIFIED**.

**Distribution: NO_SEARCH 9, ARITHMETIC_ERROR 1, TRUNCATION 1, UNCLASSIFIED 1 (total 12).**

| Task | Class | Evidence / locus |
|---|---|---|
| V2C02 | UNCLASSIFIED | derivation ends at correct formula, no checkable false numeric claim, GT token absent |
| V2M02 | ARITHMETIC_ERROR | step [4] claims f(4)=1217; SymPy f(4)=1207 |
| V2M03 | NO_SEARCH | true n=3; tested [0,1]; locus n=1 |
| V2M04 | NO_SEARCH | true n=3; tested [0,1]; locus n=1 |
| V2M06 | NO_SEARCH | true n=4; tested [0,1]; locus n=1 |
| V2M07 | NO_SEARCH | true n=4; tested [0,1,2]; locus n=2 |
| V2M08 | TRUNCATION | `done_reason=length`, unparseable at stop |
| V2M09 | NO_SEARCH | true n=6; tested [0,1]; locus n=1 |
| V2M10 | NO_SEARCH | true n=3; tested [0,1,2]; locus n=2 |
| V2M11 | NO_SEARCH | true n=3; tested [0,1,2]; locus n=2 |
| V2M14 | NO_SEARCH | true n=7; tested [0,1]; locus n=1 |
| V2M15 | NO_SEARCH | true n=4; tested [0,1]; locus n=1 |

The only ARITHMETIC_ERROR claim is verified: `f(n)=n^2+7n+1163`, `f(4)=16+28+1163=1207`,
not 1217 (the model's false claim), which caused it to skip the true first composite at n=4.

---

## 4. Conditions

* **A BLIND**: identical prompt to ORDER_V2, no feedback. Run on **2 tasks only** to verify
  byte-identity with the stored ORDER_V2 `raw_content`. If both byte-identical, use the
  stored outputs as the baseline for all 12 (no other A calls). If not byte-identical, run
  all 12 A calls and **report the determinism failure**.
* **B LABEL**: append only
  `"Your previous attempt was judged incorrect. No further information is available. Attempt the task again."`
* **C ORACLE**: append
  `"Your previous attempt was judged incorrect. Failure class: <CLASS>. <LOCUS> Attempt the task again."`
  with class/locus from section 3, e.g. NO_SEARCH →
  `"Your previous attempt was judged incorrect. Failure class: NO_SEARCH. You did not test values beyond n=<k>. Attempt the task again."`
  **The oracle text MUST NOT contain any ground-truth token.** Assert programmatically per
  cell (`verify_oracle_no_gt`, using `_number_present` on the full prompt) and report
  `copy_possible`. Verified offline: all 12 oracle texts leak nothing.

---

## 5. Primary endpoint and gates

* **Primary endpoint**: audited non-copy pass count per condition, using the **same strict
  SymPy audit** as ORDER_V2 (`audit_answer`: coefficient → exact integer present;
  minimality → n AND value AND both primes present). Condition A's baseline is recomputed
  from the stored outputs with the same audit.
* **KILL GATE**: if condition C produces **0 new audited passes** across all 12, the
  diagnosis-guided-retry branch is **DEAD** — report plainly and stop; do not proceed to
  model-generated diagnosis.
* **SUCCESS CRITERION**: C passes > A passes AND C passes >= B passes, with total failures
  across ALL modes not higher in C. Report McNemar exact where paired. **Guard the TOTAL,
  not one mode.** Both distinct failed cells and multi-label failure events are reported.

### What a pass does not prove
C is spoon-fed by construction: it receives the true failure class and locus. It is an
**UPPER BOUND** on diagnosis-guided retry, **not a capability claim**. No claim about model
understanding follows from C alone.

---

## 6. Budget and execution

* Max **40 calls**, max **2400 s**, min free physical **450 MB**, guarded before every call.
* Rationale: measured ORDER_V2 `47.75 s/call`; 26 planned calls ~1242 s. If A reruns all 12,
  total is 36 calls ~1719 s, still inside 40 / 2400.
* Conditions run **sequentially single-flight**: A(2) → B(12) → C(12).
* **New stores only**: `data/block15_diagnosis.sqlite3`, `data/block15_diagnosis_events.jsonl`.
* Results: `data/block15_diagnosis_results_<cond>_<timestamp>.json` — does **not** match
  `block15_round3_results_*`.
* Refuse to start if any diagnosis result file exists, if FROZEN changed, if an oracle
  leaks ground truth, or if the model digest/quantisation mismatches.

---

## 7. Protected manifest

FROZEN = the ORDER_V2 118-path baseline (verified byte-identical; new diagnosis artifacts
excluded by rule). LIVE before/after are **Git blob hashes** at `3890575` (block start)
vs report-time HEAD; new files reported as new, never "all unchanged".

## 8. Artifacts
Harness `block15/diagnosis_research.py`; prereg `PREREG_DIAGNOSIS.md`; report
`REPORT_DIAGNOSIS.md`; stores/results/summary under `data/block15_diagnosis_*`.
