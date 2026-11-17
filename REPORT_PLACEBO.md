# Report — Placebo controls for the diagnosis-guided retry branch

Applies the pre-registered criterion in `PREREG_PLACEBO.md` (commit `2c74a89`, before generation). Model `lfm3base:latest` (Q4_K_M, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`), local Ollama only.

## 1. Verdict — stated first

**NON-INFORMATIONAL.** C (ORACLE) produced **2** audited passes, which does **not** exceed max(D1,D2) = **3** (D1=3, D2=1). The second clause also fails: C failed_cells=10 is not <= min(D1,D2) failed_cells=9. Both required clauses are false, so the diagnosis branch is **NON-INFORMATIONAL**: the effect is consistent with perturbation noise, and diagnosis-text repair is declared **dead on this set**. No model-generated diagnosis is warranted.

## 2. Pass sets and overlaps (B / C / D1 / D2)

| Condition | Pass count | Pass set |
|---|---:|---|
| B | 2 | V2C02, V2M07 |
| C | 2 | V2C02, V2M10 |
| D1 | 3 | V2C02, V2M04, V2M07 |
| D2 | 1 | V2M07 |

Pairwise overlaps (task ids):

| Overlap | Tasks |
|---|---|
| B&C | V2C02 |
| B&D1 | V2C02, V2M07 |
| B&D2 | V2M07 |
| C&D1 | V2C02 |
| C&D2 | ∅ |
| D1&D2 | V2M07 |

D1's pass set is a strict superset of B's (V2C02, V2M07 plus V2M04); the oracle C passes V2C02 and V2M10 and shares no pass with D2. A single neutral 'review your work' sentence (D1) produced more passes than the oracle, reinforcing the non-informational verdict.

## 3. Per-task table (appended-text lengths, copy flags, outcomes)

Toks = whitespace token length of appended text (B=15, C=20/28, D1=10, D2 matched to C). CP = copy_possible (all asserted False). O-hash = first 12 hex of appended-text SHA-256. PC = audited non-copy pass; Own = emitted order matches derivation-first schema; Viol = validate_v2 violations; Done = done_reason; Eval = eval tokens.

| Task | C-len | D2-len | B:PC | C:PC | D1:PC | D1:Done | D1:Own | D1:Viol | D1:CP | D1:O-hash | D2:PC | D2:Done | D2:Own | D2:Viol | D2:CP | D2:O-hash |
|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V2C02_coeff_2x_minus_7_pow6_x4 | 20 | 20 | Y | Y | Y | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M02_minimal_n2_plus_7n_plus_1163 | 28 | 28 | N | N | N | length | N | 1 | N | 277c47fbbeea | N | stop | Y | 0 | N | 4bf3f768da47 |
| V2M03_minimal_n2_plus_5n_plus_1223 | 20 | 20 | N | N | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M04_minimal_2n2_plus_6n_plus_1031 | 20 | 20 | N | N | Y | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M06_minimal_n2_plus_3n_plus_1429 | 20 | 20 | N | N | N | length | N | 1 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M07_minimal_n2_plus_n_plus_1481 | 20 | 20 | Y | N | Y | stop | Y | 0 | N | 277c47fbbeea | Y | stop | Y | 0 | N | 687aa68acdce |
| V2M08_minimal_n2_plus_n_plus_1487 | 28 | 28 | N | N | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 4bf3f768da47 |
| V2M09_minimal_3n2_plus_3n_plus_1033 | 20 | 20 | N | N | N | length | N | 1 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M10_minimal_2n2_plus_4n_plus_1483 | 20 | 20 | N | Y | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M11_minimal_4n2_plus_4n_plus_1163 | 20 | 20 | N | N | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M14_minimal_5n2_plus_5n_plus_1399 | 20 | 20 | N | N | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |
| V2M15_minimal_3n2_plus_3n_plus_1283 | 20 | 20 | N | N | N | stop | Y | 0 | N | 277c47fbbeea | N | stop | Y | 0 | N | 687aa68acdce |

D2 length matches C on every task (20 for 10 tasks, 28 for 2). All copy flags are False; D1/D2 texts were asserted to contain no failure class, no locus and no ground-truth token.

## 4. Recomputed failure partition — single definition

Single convention (`block15/accounting.py`): failed_cells = no audited pass; failure_flags from a FIXED set; failure_events = sum of flag counts over NON-PASS cells only (passes contribute zero).

| Condition | Cells | Audited passes | failed_cells | failure_events | Flag partition (non-pass cells) |
|---|---:|---:|---:|---:|---|
| C | 12 | 2 | 10 | 14 | {'call_error': 1, 'confidence_out_of_range': 1, 'parse_failed': 1, 'primary_wrong': 10, 'truncated': 1} |
| D1 | 12 | 3 | 9 | 21 | {'call_error': 3, 'confidence_out_of_range': 3, 'parse_failed': 3, 'primary_wrong': 9, 'truncated': 3} |
| D2 | 12 | 1 | 11 | 11 | {'primary_wrong': 11} |

Criterion inputs under the single definition: C_pass=2 vs max(D1,D2)=3; C failed_cells=10 vs min(D1,D2)=9 — both clauses fail. (B's full partition is in `REPORT_DIAGNOSIS.md` §10 correction; B pass set is reported above.)

## 5. Run conduct, provenance and budget

- 24 calls (12 D1 + 12 D2), single-flight D1→D2, one call per task per condition; ~722 s, min free physical 2015.3 MB — within 30 calls / 1800 s / 450 MB.
- All cells used `protocol_variant=primary`, `schema_enforced=True`, `think_sent=False`; schema DERIVATION_FIRST_V2, sampling identical to ORDER_V2/DIAGNOSIS. Module git-blob hash identical in both result files (`d5a24a81d1ed3317a5cdcd0f426a42e21181d6341c2542a38b72a7fea2471b75`) — no CONFOUND.

## 6. FROZEN / LIVE

FROZEN byte-identical: True (118/118 paths, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`). LIVE before/after are Git blob hashes at `88de741` (block start) vs report-time HEAD.

| LIVE path | status | before (blob) | after (blob) |
|---|---|---|---|
| block15/order_v2_research.py | changed | `8862d0cecd1121aad3b84bfe3c4e87a8d3c22f980d37dfe43c384426cfee9e51` | `f71052c5794ac7a24ea0e2ae89cef270630cefeef80fd980a27f4e056255e475` |
| block15/placebo_research.py | new | `None` | `d5a24a81d1ed3317a5cdcd0f426a42e21181d6341c2542a38b72a7fea2471b75` |
| tests/test_accounting.py | new | `None` | `dd2922b22a7cba2e3635d7b0f5a541a4df5ec4b11d2181a422395f09e03eba28` |
| tests/test_placebo_research.py | new | `None` | `ae0c5f306eff01844fe191e98e9a67ad6e83e662c87ef396e9faed42823ca398` |

The 43 unchanged LIVE paths have identical before/after blob hashes; no 'all unchanged' claim is made for LIVE.

## 7. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_placebo_results_D1_20261117T142846Z.json | `9cf5e76200082017b03ab7bd7c06d7b1b0f9a2ac28c287552d3bbf71e0358fa2` |
| data/block15_placebo_results_D2_20261117T142846Z.json | `83e422680589cfc58f40d1657bee1acdf7ea026460d4df15280327506b4fccc6` |
| data/block15_placebo_summary.json | `5bc787b110a97e77f2f8cee5863d9b1b6d85c31fe49d432933496bd019eabfe0` |

## 8. Limits

n=12, single seed, one schema order, one local quantisation; counts are noisy. A 2-vs-3 difference cannot establish equivalence or non-equivalence — it is a failure to demonstrate the oracle's advantage. The oracle (C) is spoon-fed by construction and is an upper bound, not a capability claim. A neutral one-sentence placebo (D1) matched or exceeded the oracle, so any apparent DIAGNOSIS gain is indistinguishable from perturbing the prompt.

## 9. Mandatory deviation and objection report

### a) Deviations from this spec

- None in the run itself. The STEP 1 accounting correction changed two report files (`REPORT_ORDER_V2.md`, `REPORT_DIAGNOSIS.md`) and added `block15/accounting.py`; no stored result cell was altered. All changes were committed before generation (`2c74a89`).
- D2 is implemented as two fixed neutral strings (20 and 28 tokens) selected to match the oracle text length per task, rather than a dynamically generated filler. This satisfies the matched-length requirement exactly and keeps the text trivially auditable.

### b) Deviations from the reference contract

- Uses DERIVATION_FIRST_V2 and ORDER_V2 instruction/system prompt/sampling unchanged, as required. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded

- D1 (10 tokens) and D2 (20/28 tokens) are not length-matched to each other or to B (15 tokens); only D2 is matched to C. Comparisons between D1 and D2 therefore conflate content and length. The criterion compares C only to `max(D1,D2)`, so this does not affect the verdict, but it limits interpretation.
- B and C pass sets are reused from the stored DIAGNOSIS run with passes recomputed under the strict audit; they were not re-run here, so any cross-block nondeterminism in the model would not be visible. The prior DIAGNOSIS determinism check passed on 2 tasks.
- With n=12 and 1-3 passes per condition, all counts are dominated by noise; the criterion is a conservative gate, not a powered equivalence test.

### d) What I could not verify

- Server-side schema-enforcement internals; only local Ollama `format=dict` was used.
- Whether the neutral texts are semantically 'matched' — only token length and absence of class/locus/GT tokens were verified.
- Generalisation beyond these 12 tasks, one seed and one quantisation.

