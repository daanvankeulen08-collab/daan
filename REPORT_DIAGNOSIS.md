# Report — Diagnosis-guided retry on the 12 ORDER_V2 failures

Applies the analysis pre-registered in `PREREG_DIAGNOSIS.md` (commit `80903f2`, before generation; harness bug fix `1a9210f`, also before the successful run). Model `lfm3base:latest` (Q4_K_M, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`), local Ollama only.

## 1. Kill-gate verdict — stated first

**KILL GATE: ALIVE** — condition C produced **2 new audited passes** across the 12 failures, so the diagnosis-guided-retry branch is **not dead**. No stop was triggered.
**Determinism (condition A): PASS** — the 2 BLIND re-runs were byte-identical to the stored ORDER_V2 `raw_content` on both verified tasks (V2C02, V2M02); stored ORDER_V2 outputs were therefore used as the baseline for all 12 A cells (no extra A calls).

## 2. Failure classification of the 12 cells

First-match-wins precedence: TRUNCATION → INVALID_JSON → SCHEMA_VIOLATION → NO_SEARCH → ARITHMETIC_ERROR → CONTRACT_MISMATCH; unmatched = UNCLASSIFIED.

| Class | Count |
|---|---:|
| ARITHMETIC_ERROR | 1 |
| NO_SEARCH | 9 |
| TRUNCATION | 1 |
| UNCLASSIFIED | 1 |
| **Total** | **12** |

| Task | Class | Evidence / locus |
|---|---|---|
| V2C02_coeff_2x_minus_7_pow6_x4 | UNCLASSIFIED | no precedence rule matched (derivation ends at correct formula, no checkable false numeric claim, GT token absent from derivation) |
| V2M02_minimal_n2_plus_7n_plus_1163 | ARITHMETIC_ERROR | derivation step [4] claims f(4)=1217; SymPy f(4)=1207 |
| V2M03_minimal_n2_plus_5n_plus_1223 | NO_SEARCH | true n=3; derivation tested n in [0,1]; n=3 never tested |
| V2M04_minimal_2n2_plus_6n_plus_1031 | NO_SEARCH | true n=3; derivation tested n in [0,1]; n=3 never tested |
| V2M06_minimal_n2_plus_3n_plus_1429 | NO_SEARCH | true n=4; derivation tested n in [0,1]; n=4 never tested |
| V2M07_minimal_n2_plus_n_plus_1481 | NO_SEARCH | true n=4; derivation tested n in [0,1,2]; n=4 never tested |
| V2M08_minimal_n2_plus_n_plus_1487 | TRUNCATION | done_reason == length; unparseable at stop |
| V2M09_minimal_3n2_plus_3n_plus_1033 | NO_SEARCH | true n=6; derivation tested n in [0,1]; n=6 never tested |
| V2M10_minimal_2n2_plus_4n_plus_1483 | NO_SEARCH | true n=3; derivation tested n in [0,1,2]; n=3 never tested |
| V2M11_minimal_4n2_plus_4n_plus_1163 | NO_SEARCH | true n=3; derivation tested n in [0,1,2]; n=3 never tested |
| V2M14_minimal_5n2_plus_5n_plus_1399 | NO_SEARCH | true n=7; derivation tested n in [0,1]; n=7 never tested |
| V2M15_minimal_3n2_plus_3n_plus_1283 | NO_SEARCH | true n=4; derivation tested n in [0,1]; n=4 never tested |

**ARITHMETIC_ERROR SymPy evidence (V2M02):** the derivation step [4] claims `f(4) = 16+28+1163 = 1217`. SymPy from the task parameters `f(n)=n^2+7n+1163` gives `f(4)=1207` (`1207 = 17*71`, the true first composite). The false `1217` claim caused the model to skip n=4. This is the only cell whose numeric claim in the derivation was verifiably false; the remaining failures are search-bound or truncation issues.

## 3. Per-task table (A / B / C)

A = BLIND (stored ORDER_V2 baseline); B = LABEL; C = ORACLE. PC = audited non-copy primary pass; Own = emitted key order matches derivation-first schema; Viol = number of `validate_v2` violations; Done = `done_reason`; Tok = eval tokens; CP = copy_possible; O-hash = first 12 hex of oracle text SHA-256 (A/B: none, B uses the label text).

| Task | A:PC | A:Done | A:Tok | A:CP | B:PC | B:Own | B:Viol | B:Done | B:Tok | B:CP | C:PC | C:Own | C:Viol | C:Done | C:Tok | C:CP | C:oracle-hash |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V2C02_coeff_2x_minus_7_pow6_x4 | N | stop | 265 | N | Y | Y | 0 | stop | 319 | N | Y | Y | 0 | stop | 211 | N | 921cec4eeead |
| V2M02_minimal_n2_plus_7n_plus_1163 | N | stop | 675 | N | N | Y | 0 | stop | 529 | N | N | Y | 0 | stop | 1107 | N | 12ba23dd7275 |
| V2M03_minimal_n2_plus_5n_plus_1223 | N | stop | 158 | N | N | Y | 0 | stop | 164 | N | N | Y | 0 | stop | 144 | N | 4fb9ad4d4bf2 |
| V2M04_minimal_2n2_plus_6n_plus_1031 | N | stop | 342 | N | N | Y | 0 | stop | 504 | N | N | N | 1 | length | 1200 | N | 4fb9ad4d4bf2 |
| V2M06_minimal_n2_plus_3n_plus_1429 | N | stop | 544 | N | N | Y | 1 | stop | 1163 | N | N | Y | 0 | stop | 389 | N | 4fb9ad4d4bf2 |
| V2M07_minimal_n2_plus_n_plus_1481 | N | stop | 681 | N | Y | Y | 0 | stop | 1006 | N | N | Y | 0 | stop | 548 | N | a54df828ef4b |
| V2M08_minimal_n2_plus_n_plus_1487 | N | length | 1200 | N | N | Y | 0 | stop | 267 | N | N | Y | 0 | stop | 401 | N | d03001aefb5a |
| V2M09_minimal_3n2_plus_3n_plus_1033 | N | stop | 1041 | N | N | N | 1 | length | 1200 | N | N | Y | 0 | stop | 937 | N | 4fb9ad4d4bf2 |
| V2M10_minimal_2n2_plus_4n_plus_1483 | N | stop | 350 | N | N | Y | 0 | stop | 560 | N | Y | Y | 0 | stop | 961 | N | a54df828ef4b |
| V2M11_minimal_4n2_plus_4n_plus_1163 | N | stop | 219 | N | N | N | 1 | length | 1200 | N | N | Y | 0 | stop | 272 | N | a54df828ef4b |
| V2M14_minimal_5n2_plus_5n_plus_1399 | N | stop | 190 | N | N | Y | 0 | stop | 252 | N | N | Y | 0 | stop | 257 | N | 4fb9ad4d4bf2 |
| V2M15_minimal_3n2_plus_3n_plus_1283 | N | stop | 192 | N | N | Y | 0 | stop | 227 | N | N | Y | 0 | stop | 372 | N | 4fb9ad4d4bf2 |

## 4. Primary endpoint, paired statistics and failure partition

Primary counts: **A=0, B=2, C=2**. Paired McNemar exact: C vs A (b=0 A-only, c=2 new) p=0.5; C vs B (b=1, c=1) p=1.0. The two C passes are V2C02 and V2M10; B's two passes are V2C02 and V2M07. C ties B (2=2) and the McNemar p-values are not significant.

| Condition | Cells | Audited passes | Distinct failed cells | Total failure events | Modes |
|---|---:|---:|---:|---:|---|
| A | 12 | 0 | 12 | 14 | {'primary_wrong': 11, 'output_error': 1} |
| B | 12 | 2 | 10 | 15 | {'primary_correct': 2, 'primary_wrong': 8, 'output_error': 2} |
| C | 12 | 2 | 10 | 12 | {'primary_correct': 2, 'primary_wrong': 9, 'output_error': 1} |

Both counts are labelled: **distinct failed cells** counts cells with no audited pass; **total failure events** is the multi-label sum (one per non-pass cell, plus one each for truncation, schema violation and copy leakage where present). Success criterion: C>A (2>0) and C>=B (2>=2) and C's total failures (12) not higher than A's (14) — **met: True**.

## 5. Run conduct, provenance and budget

- 26 calls (2 A verify + 12 B + 12 C), single-flight A→B→C, one call per task per condition; ~917 s runtime, min free physical 2153.6 MB — within 40 calls / 2400 s / 450 MB.
- All cells used `protocol_variant=primary`, `schema_enforced=True`, `think_sent=False`; schema DERIVATION_FIRST_V2, sampling identical to ORDER_V2. No oracle text contained a ground-truth token (asserted per cell; all `copy_possible=False`).
- Module Git blob hash identical in all three result files: `10a3902a2e1420ac054d4e0f1f015623403c720fa7adc4b334c9cb99acd3b0e8` — no CONFOUND.

## 6. FROZEN / LIVE

FROZEN byte-identical: True (118/118 paths, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`). LIVE before/after are Git blob hashes at `3890575` vs report-time HEAD.

| LIVE path | status | before (blob) | after (blob) |
|---|---|---|---|
| block15/diagnosis_research.py | new | `None` | `10a3902a2e1420ac054d4e0f1f015623403c720fa7adc4b334c9cb99acd3b0e8` |
| block15/order_v2_research.py | changed | `26829883d0cb9e63a406e09917bd1bc5cae608424191be73b89fc9c8ae7eab32` | `8862d0cecd1121aad3b84bfe3c4e87a8d3c22f980d37dfe43c384426cfee9e51` |
| tests/test_diagnosis_research.py | new | `None` | `fb78db0a998503215bf4db60821a2c78df5262a9f0de8da885b0b111d781abed` |

The 41 unchanged LIVE paths have identical before/after blob hashes; no 'all unchanged' claim is made for LIVE.

## 7. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_diagnosis_results_A_20261116T223044Z.json | `35ad805f8780aac88094de45af144f09e0e6632a96cce66b39823f5f7f388b74` |
| data/block15_diagnosis_results_B_20261116T223044Z.json | `aa63fe32809d41093db2c4d19799c71216b0b01dfb51757df3c6433854642323` |
| data/block15_diagnosis_results_C_20261116T223044Z.json | `6937f5186ea8d3664f8c041576723da16bd7279662adb136570f9747711f00b3` |
| data/block15_diagnosis_summary.json | `a5afd4afc4473d9c6544d885cf47519f02d2cbb924c93777c3740b55e377d1d0` |

## 8. Limits — what a pass does not prove

C is spoon-fed the true failure class and locus, so it is an **upper bound** on diagnosis-guided retry, not a capability claim. No claim about model understanding follows from C alone. This is 12 tasks (the ORDER_V2 failures only), one seed, one schema order, one local quantisation. C ties B at 2 passes with non-significant McNemar p-values, so the oracle provides no demonstrated advantage over a generic 'incorrect' label on this set. The single seed and small n make all counts noisy.

## 9. Mandatory deviation and objection report

### a) Deviations from this spec

- Two harness bugs were fixed before the successful run with no model calls in the crashed attempts: the `guard` closure was not stored in runner state (`KeyError: 'guard'`), and the FROZEN new-artifact exclusion did not cover `block15_diagnosis_*`. Both are infrastructure fixes (commits `1a9210f`) that touch no prompt, schema, sampling or audit logic; the partial store files from the crash were removed and no partial arm reused.
- STEP 0 corrected a pre-existing factual error in `REPORT_ORDER_V2.md` (pass split and the mistaken '15/15, 3/15' line) and added the strict-diagnostic count; these are record fixes, not changes to any result cell.
- The oracle text for the ARITHMETIC_ERROR cell names the class and locus generically ('recheck the arithmetic where you evaluate f(n)') rather than the specific f(4) step, because naming `n=4` would leak a ground-truth token (4) for that task. This preserves the no-GT-token requirement at the cost of a less specific locus.

### b) Deviations from the reference contract

- Uses DERIVATION_FIRST_V2 and the ORDER_V2 instruction/system prompt unchanged, as required. No schema or sampling change from ORDER_V2. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded

- Condition A reuses stored ORDER_V2 outputs as the baseline after only a 2-task byte-identity check; a determinism failure on the other 10 tasks would go undetected. This is the pre-registered design, not a verified property of all 12.
- The oracle is computed from the model's own derivation and the stored ground truth, so its 'diagnosis' is machine-derived, not model-generated; C measures the value of being told the answer locus, not of producing it.
- One of the 12 original failures (V2M08) was a truncation and the other 11 were wrong-answer cells; appending feedback lengthens prompts, which can itself change truncation rates (B and C each had one new length-truncated cell). Total-failure guard is reported, but condition effects are noisy at n=12.
- UNCLASSIFIED (V2C02) was deliberately not forced into a class; the classifier found no checkable false claim and no GT token in its derivation.

### d) What I could not verify

- Server-side schema-enforcement internals; only local Ollama `format=dict` was used.
- Whether the 10 non-verified A tasks would reproduce byte-identically (see c).
- Generalisation beyond these 12 tasks, one seed and one quantisation.
- Historical git blob for the new diagnosis files at the baseline commit (absent by construction; reported as `new`).

---

## 10. Correction — single failure-accounting convention (added in STEP 1 of the placebo task)

Under the single convention in `block15/accounting.py` (`failed_cells` = no audited pass;
`failure_flags` from a FIXED enumerated set; `failure_events` = sum of flag counts over
NON-PASS cells only; passing cells contribute zero), the DIAGNOSIS totals change. The
original summary's `total_failure_events` used an ad-hoc flag formula that counted some
flags on passing cells and omitted others, so it is superseded. No stored result cell was
altered — flags are re-derived from raw fields via a fresh parse.

| Condition | old total events | corrected failed_cells | corrected failure_events | corrected partition (non-pass cells) |
|---|---:|---:|---:|---|
| A (BLIND) | 14 | 12 | 16 | primary_wrong=12, call_error=1, parse_failed=1, truncated=1, confidence_out_of_range=1 |
| B (LABEL) | 15 | 10 | 20 | primary_wrong=10, call_error=2, parse_failed=2, schema_violation=1, truncated=2, confidence_out_of_range=3 |
| C (ORACLE) | 12 | 10 | 14 | primary_wrong=10, call_error=1, parse_failed=1, truncated=1, confidence_out_of_range=1 |

The ordering used by the success criterion is unchanged: corrected C failed_cells (10) <=
corrected A failed_cells (12), and corrected C total events (14) <= corrected A (16), so
the prior "success criterion met" verdict still holds under the corrected accounting. This
section is a labelled correction, not a rewrite of stored data.

