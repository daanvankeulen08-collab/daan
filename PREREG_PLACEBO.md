# Pre-registration — Placebo controls for the diagnosis-guided retry branch

**Status: pre-registered before any generation. No model call has been made in this block.**

This document fixes the placebo-control design that decides whether the diagnosis branch
in the prior study carried information or merely perturbation noise. It is committed
before generation. Harness `block15/placebo_research.py`; only new `data/block15_placebo_*`
artifacts written. `block15/round3_report.py` is never executed.

---

## 0. STEP 1 — single failure-accounting convention (record fix, no generation)

One machine-computed convention is now defined in `block15/accounting.py` and used
everywhere:

* `failed_cells` = cells with no audited pass.
* `failure_flags` = per-cell list from the **FIXED** enumerated set
  {`call_error`, `parse_failed`, `schema_violation`, `truncated`, `primary_wrong`,
  `confidence_out_of_range`, `copy_possible`}.
* `failure_events` = sum of `len(failure_flags)` over **NON-PASS cells only**; passing
  cells contribute zero.

This is asserted in `tests/test_accounting.py`. No stored result cell was altered. The
recomputed totals were republished as labelled corrections in section 10 of
`REPORT_ORDER_V2.md` and `REPORT_DIAGNOSIS.md`, side by side with the old numbers:

| Study / cell group | old events | corrected failed_cells | corrected events |
|---|---:|---:|---:|
| ORDER_V2 answer_first | 30 | 30 | 30 |
| ORDER_V2 derivation_first | 16 | 12 | 16 |
| DIAG A | 14 | 12 | 16 |
| DIAG B | 15 | 10 | 20 |
| DIAG C | 12 | 10 | 14 |

The ORDER_V2 and DIAGNOSIS verdicts are unchanged under the single definition.

---

## 1. Contract (identical in all conditions)

Same 12 tasks, same order as DIAGNOSIS/ORDER_V2: `V2C02, V2M02, V2M03, V2M04, V2M06,
V2M07, V2M08, V2M09, V2M10, V2M11, V2M14, V2M15`.

Schema `DERIVATION_FIRST_V2`; shared neutral `OUTPUT_INSTRUCTION_V2` + the one schema-order
sentence; `SYSTEM_PROMPT_V2`. Sampling identical to ORDER_V2/DIAGNOSIS: `think=False`,
`num_ctx=8192`, `temperature=0.1`, `top_p=1.0`, `repeat_penalty=1.1`, `seed=42`,
`keep_alive=10m`, `num_predict=1200`. **Only appended feedback text differs.**

---

## 2. Conditions — appended text only

* **D1** (fixed): `"Please review your work carefully and attempt the task again."`
  (10 whitespace tokens). Neutral review request; no diagnostic information.
* **D2** (neutral, token-length matched to C per task): a restatement of the output-format
  requirement, with **no digits** (so no ground-truth token can appear), no failure class,
  no locus. Two fixed strings:
  - 20-token form (used where C oracle is 20 tokens):
    `"Please review the required output format before you answer. Return one JSON object with these fields: confidence, derivation, final_answer, uncertainty."`
  - 28-token form (used where C oracle is 28 tokens): the 20-token form plus
    `" Please keep every string on a single line."`
* Token lengths (whitespace split, auditable, reported per task in `--manifest`):
  B=15; C=20 for 10 tasks and 28 for 2 tasks; D1=10; D2 matched to C (20 or 28).
* **Neither placebo contains a failure class, a locus, or any GT token** — asserted
  programmatically per cell (`verify_placebo_texts`: checks class-word list, GT tokens on
  the full prompt, and absence of any digit in D1/D2 text). B and C additionally checked
  for GT-token leakage. All reported per cell.

---

## 3. Primary endpoint and criterion

* **Primary**: audited non-copy pass count per condition, same strict SymPy audit
  (`D.audited_pass`: exact coefficient / n+value+both primes), recomputed — not trusted
  from stored flags.
* Pass **SETS** and overlaps for B, C, D1, D2 are reported, not just counts.
* **Criterion**: the diagnosis branch is **INFORMATIONAL** iff
  `C_pass > max(D1_pass, D2_pass)` **AND** `C_failed_cells <= min(D1_failed_cells,
  D2_failed_cells)`; otherwise **NON-INFORMATIONAL (perturbation noise)** and diagnosis-
  text repair is declared dead on this set. `failed_cells` uses the single definition.

---

## 4. Budget and execution

* Max **30 calls**, max **1800 s**, min free physical **450 MB**, guarded before each call.
* Rationale: measured `35.3 s/call`; 24 planned calls ~847 s.
* Conditions run **sequentially single-flight**: D1(12) then D2(12).
* New stores: `data/block15_placebo.sqlite3`, `data/block15_placebo_events.jsonl`.
* Results: `data/block15_placebo_results_<cond>_<timestamp>.json` — does **not** match
  `block15_round3_results_*`.
* Refuse to start if any placebo result exists, if FROZEN changed, or if a placebo leaks
  a class/locus/GT token.

---

## 5. Protected manifest and limits

FROZEN = ORDER_V2 118-path baseline, byte-identical (placebo artifacts excluded by rule).
LIVE before/after are **Git blob hashes** at `88de741` (block start) vs report-time HEAD.

**Limits**: n=12, single seed, one schema order, one local quantisation; counts are noisy.
A 2-vs-2 tie cannot establish equivalence — it can only fail to demonstrate advantage.
The oracle (C) is spoon-fed by construction and is an upper bound, not a capability claim.

## 6. Artifacts
Harness `block15/placebo_research.py`; accounting `block15/accounting.py`;
prereg `PREREG_PLACEBO.md`; report `REPORT_PLACEBO.md`; stores/results/summary under
`data/block15_placebo_*`.
