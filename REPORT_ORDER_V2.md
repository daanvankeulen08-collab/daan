# Report — Order V2: `final_answer` before versus after the `derivation` array

This report applies the analysis pre-registered in `PREREG_ORDER_V2.md` (commit `9dac3e4`, made before any generation). The run used local Ollama only, model `lfm3base:latest` (Q4_K_M, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`).

## 1. Validity gates — verdicts first

**G1 manipulation: PASS** — answer_first: 100% matches_own_schema / 0% matches_other_schema (30/30 parseable); derivation_first: 100% own / 0% other (29/29 parseable). Threshold: >=90% own and <=10% other in each arm. Both arms pass.

**G2 length: PASS** — answer_first truncation-invalid 0/30 = 0.00%; derivation_first 1/30 = 3.33%. Threshold: <=20% per arm. Both arms pass.

Both gates pass; the comparison may be attributed to schema field order under the pre-registered design. Failing either gate would have made the run INVALID with the stated label, not null.

## 2. Primary endpoint and paired analysis

- Primary count, answer_first: **0 / 30**
- Primary count, derivation_first: **18 / 30**
  - Verified breakdown of the 18 passes (STEP 0 check): **13 bare integers + 1 verbose (V2C12, whose derivation correctly computes 188160) + 4 minimality (V2M01, V2M05, V2M12, V2M13) = 18**. The 14 coefficient passes are 13 bare + 1 verbose; the 4 minimality passes are all bare-in-structure answers.
  - Strict-diagnostic check: **17 of the 18** also pass the stored stricter diagnostic (`strict_single_int` for coefficient, `strict_set_equal` for minimality). The single exception is V2C12, whose verbose multi-integer `final_answer` cannot be a single integer. This is only 1 lower than 18, i.e. not materially lower; the primary endpoint is presence-based as pre-registered.
- Difference (derivation - answer): **+18** tasks
- Risk difference: **+0.6000** (paired bootstrap 95% CI [0.4333, 0.7667])
- Discordant pairs: answer-only correct b=0; derivation-only correct c=18
- McNemar two-sided exact p: **0.000008** (p < 0.05, so the pre-registered significance threshold is met)
- Total failures across ALL modes: answer_first 30, derivation_first 16 (not higher in derivation_first)
- **Success criterion met: True** (derivation count higher, total failures not higher, G1 and G2 both pass, run complete)

Contract-compliance rate is reported separately and is NOT the primary endpoint: answer_first 100.00% (30/30), derivation_first 96.67% (29/30). The single derivation_first non-compliant cell is a truncation (`done_reason=length`, unparseable), whose raw confidence is `None`: its `confidence_out_of_range` flag reflects a missing value, not a numeric confidence outside [0,1]. No parseable cell emitted a numeric confidence outside [0,1]. Confidence values were persisted raw but never used to filter the primary count.

## 3. Per-task table (both arms)

Columns: PC = primary correct; Own/Oth = emitted key order matches own / other schema; Viol = number of `validate_v2` violations; Done = `done_reason`; Tok = eval tokens; Conf = raw confidence; CP = copy_possible. Emitted order is abbreviated: f=final_answer, d=derivation, u=uncertainty, c=confidence.

| Task | A:PC | A:order | A:Viol | A:Done | A:Tok | A:Conf | A:CP | D:PC | D:order | D:Viol | D:Done | D:Tok | D:Conf | D:CP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V2C01_coeff_x_plus_4_pow8_x5 | N | fduc | 0 | stop | 187 | 1 | N | Y | dfuc | 0 | stop | 185 | 1 | N |
| V2C02_coeff_2x_minus_7_pow6_x4 | N | fduc | 0 | stop | 411 | 0.9 | N | N | dfuc | 0 | stop | 265 | 1 | N |
| V2C03_coeff_5x_minus_2_pow7_x3 | N | fduc | 0 | stop | 404 | 0.9 | N | Y | dfuc | 0 | stop | 293 | 0.95 | N |
| V2C04_coeff_x_minus_6_pow9_x7 | N | fduc | 0 | stop | 609 | 0.99 | N | Y | dfuc | 0 | stop | 166 | 1 | N |
| V2C05_coeff_4x_plus_3_pow7_x2 | N | fduc | 0 | stop | 360 | 0.9 | N | Y | dfuc | 0 | stop | 298 | 0.99 | N |
| V2C06_coeff_7x_minus_2_pow6_x5 | N | fduc | 0 | stop | 435 | 0.9 | N | Y | dfuc | 0 | stop | 326 | 1 | N |
| V2C07_coeff_2x_plus_9_pow8_x6 | N | fduc | 0 | stop | 575 | 1 | N | Y | dfuc | 0 | stop | 386 | 0.95 | N |
| V2C08_coeff_3x_minus_5_pow8_x5 | N | fduc | 0 | stop | 233 | 1 | N | Y | dfuc | 0 | stop | 309 | 0.95 | N |
| V2C09_coeff_6x_plus_5_pow6_x2 | N | fduc | 0 | stop | 246 | 0.95 | N | Y | dfuc | 0 | stop | 309 | 0.95 | N |
| V2C10_coeff_x_plus_8_pow10_x8 | N | fduc | 0 | stop | 338 | 1 | N | Y | dfuc | 0 | stop | 211 | 1 | N |
| V2C11_coeff_5x_plus_4_pow7_x3 | N | fduc | 0 | stop | 385 | 0.9 | N | Y | dfuc | 0 | stop | 258 | 0.95 | N |
| V2C12_coeff_4x_minus_7_pow6_x4 | N | fduc | 0 | stop | 319 | 0.95 | N | Y | dfuc | 0 | stop | 551 | 0.99 | N |
| V2C13_coeff_7x_plus_3_pow6_x3 | N | fduc | 0 | stop | 254 | 0.95 | N | Y | dfuc | 0 | stop | 321 | 0.95 | N |
| V2C14_coeff_3x_plus_6_pow8_x6 | N | fduc | 0 | stop | 175 | 1 | N | Y | dfuc | 0 | stop | 261 | 0.95 | N |
| V2C15_coeff_6x_minus_7_pow6_x2 | N | fduc | 0 | stop | 431 | 1 | N | Y | dfuc | 0 | stop | 464 | 0.95 | N |
| V2M01_minimal_n2_plus_5n_plus_1217 | N | fduc | 0 | stop | 156 | 1 | N | Y | dfuc | 0 | stop | 289 | 1 | N |
| V2M02_minimal_n2_plus_7n_plus_1163 | N | fduc | 0 | stop | 156 | 1 | N | N | dfuc | 0 | stop | 675 | 0.99 | N |
| V2M03_minimal_n2_plus_5n_plus_1223 | N | fduc | 0 | stop | 257 | 1 | N | N | dfuc | 0 | stop | 158 | 1 | N |
| V2M04_minimal_2n2_plus_6n_plus_1031 | N | fduc | 0 | stop | 654 | 0.92 | N | N | dfuc | 0 | stop | 342 | 0.95 | N |
| V2M05_minimal_4n2_plus_2n_plus_1013 | N | fduc | 0 | stop | 334 | 0.99 | N | Y | dfuc | 0 | stop | 531 | 1 | N |
| V2M06_minimal_n2_plus_3n_plus_1429 | N | fduc | 0 | stop | 292 | 0.75 | N | N | dfuc | 0 | stop | 544 | 0.99 | N |
| V2M07_minimal_n2_plus_n_plus_1481 | N | fduc | 0 | stop | 558 | 0.95 | N | N | dfuc | 0 | stop | 681 | 0.95 | N |
| V2M08_minimal_n2_plus_n_plus_1487 | N | fduc | 0 | stop | 300 | 0.95 | N | N | - | 1 | length | 1200 | n/a | N |
| V2M09_minimal_3n2_plus_3n_plus_1033 | N | fduc | 0 | stop | 719 | 0.85 | N | N | dfuc | 0 | stop | 1041 | 0.85 | N |
| V2M10_minimal_2n2_plus_4n_plus_1483 | N | fduc | 0 | stop | 389 | 1 | N | N | dfuc | 0 | stop | 350 | 0.99 | N |
| V2M11_minimal_4n2_plus_4n_plus_1163 | N | fduc | 0 | stop | 214 | 1 | N | N | dfuc | 0 | stop | 219 | 1 | N |
| V2M12_minimal_5n2_plus_5n_plus_1021 | N | fduc | 0 | stop | 450 | 0.95 | N | Y | dfuc | 0 | stop | 527 | 1 | N |
| V2M13_minimal_2n2_plus_6n_plus_1193 | N | fduc | 0 | stop | 512 | 0.95 | N | Y | dfuc | 0 | stop | 288 | 1 | N |
| V2M14_minimal_5n2_plus_5n_plus_1399 | N | fduc | 0 | stop | 605 | 0.95 | N | N | dfuc | 0 | stop | 190 | 1 | N |
| V2M15_minimal_3n2_plus_3n_plus_1283 | N | fduc | 0 | stop | 533 | 0.99 | N | N | dfuc | 0 | stop | 192 | 1 | N |

## 4. Failure-mode partition (mutually exclusive, totals included)

| Failure mode | answer_first | derivation_first |
|---|---:|---:|
| output_error | 0 | 1 |
| primary_correct | 0 | 18 |
| primary_wrong | 30 | 11 |
| **Total cells** | **30** | **30** |

Multi-label failure flags (a cell may carry several), used for the 'total failures across ALL modes' guard:

| Flag | answer_first | derivation_first |
|---|---:|---:|
| call_error | 0 | 1 |
| confidence_out_of_range | 0 | 1 |
| parse_failed | 0 | 1 |
| primary_wrong | 30 | 12 |
| truncated | 0 | 1 |
| **Total failure events** | **30** | **16** |

Cells with at least one failure flag: answer_first 30, derivation_first 12.

## 5. Run conduct, provenance and budget

- **answer_first** (block15_order_v2_results_answer_first_20261116T214049Z.json): 30 calls, 709.26 s, stopped_early=False; protocol_variant=primary on 30/30 cells, schema_enforced=True on 30/30, think_sent=False on 30/30; free physical MB start/min/end 2054.9/1750.3/1746.5; prompt tokens 6791, eval tokens 11491.
- **derivation_first** (block15_order_v2_results_derivation_first_20261116T214049Z.json): 30 calls, 1432.5 s, stopped_early=False; protocol_variant=primary on 30/30 cells, schema_enforced=True on 30/30, think_sent=False on 30/30; free physical MB start/min/end 2054.9/1719.0/1856.7; prompt tokens 6791, eval tokens 11830.
- Both arms ran sequentially in one process, answer_first then derivation_first, one call per task per arm, single-flight via the client lock. No retries, repairs, teacher hints, memory injection, training, dependency change, network model API or model download.
- Budget: 70-call / 5400 s / 450 MB guards were active before every call; 60 planned calls executed, ~2142 s total runtime, minimum free physical memory 1719 MB — all within limits. Round 3 (22.9 s/call) and ceiling (76.7 s/call) rationale is recorded in the pre-registration.

## 6. FROZEN verification and LIVE before/after hashes

FROZEN: 118 paths verified byte-identical against the 118-path baseline; `frozen_byte_identical = True`. Manifest SHA-256 matches the pre-registered baseline: `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`.

LIVE: 42 paths; 38 unchanged, 4 changed or new. No claim of 'all unchanged' is made. Before hashes are git blobs at the GATE commit `6c788a5`; `None` means the file did not exist at baseline.

| LIVE path | status | before | after |
|---|---|---|---|
| block15/contract_v2.py | changed | `2ce7280c42eb2284230002f69e1ccf5e54e224f81057ea1d75dc4894ec880c0e` | `9f2f44732fccbead616387cde108efd4cb8950e5b6b509b6bde795f0b0bc03b4` |
| block15/order_v2_research.py | new | `None` | `a6fcbcdeaf4fdb5ffa4befb68ceb628eb1acbdbf4d679b69fde4cc28019a663a` |
| tests/test_contract_v2.py | changed | `0a1c2c1ef726754b2c2d02f18646989f6290a839d13ac919e467dab8031944d2` | `3d8230a020255324b47e44d0b2a6eddc7e87ad8ee2523cafe9495972871907a2` |
| tests/test_order_v2_research.py | new | `None` | `e6064b38b4d98dcc869434bc9a52fdd728ae4521dc1a848a329c8fecc93e97f7` |

The 38 unchanged LIVE paths (all `mdl/*.py` and the remaining `tests/*.py`) have identical before/after hashes and are enumerated in `data/block15_order_v2_summary.json` under `protected_manifest.live_rows`.

## 7. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_order_v2.sqlite3 | `19b0ee824d6c00f38205535ea821f9af04485d5be8a8520bb4a7ca4516248e56` |
| data/block15_order_v2_events.jsonl | `c5a7f8916ec60dd9e569c3e2e1a5665d1c747b5ae607bfe36dd330d8d995f585` |
| data/block15_order_v2_results_answer_first_20261116T214049Z.json | `49b708007e910f85c79fe2c2a6c2c904fa7e50731b29d6fdfe6f2b04ed462721` |
| data/block15_order_v2_results_derivation_first_20261116T214049Z.json | `825d3138b35429911fab04e921d456205ac975cb02283fa3179a563e85c3c058` |
| PREREG_ORDER_V2.md | `afa9a00d39e0a6440fe338e4fed568665841e381ce8d1a42796e60f6c2ceb1f4` |
| block15/order_v2_research.py (module at summarize time) | `a6fcbcdeaf4fdb5ffa4befb68ceb628eb1acbdbf4d679b69fde4cc28019a663a` |
| data/block15_order_v2_summary.json | `d04c85aefb6b414191de962b82657d167d662e9eed04d615c96beaab9e127056` |

## 8. Limits — what a pass does not prove

A pass does not prove general capability, generalisation beyond this one positional swap, server-side enforcement internals, or model understanding. This is a single seed (42), n=30, one positional swap (final_answer first vs derivation first), one local model quantisation. The exact task set and prompt text are pre-registered; the task mix (15 coefficient, 15 minimality) is narrow. The effect may be specific to forced-order JSON decoding on this model. Confidence values are self-reported by the model and are not calibrated. The derivation-first arm's 18 primary passes are 14 coefficient tasks (13 bare integers plus the verbose V2C12) and 4 minimality tasks (V2M01, V2M05, V2M12, V2M13) — i.e. 14/15 coefficient and 4/15 minimality — so the effect is not uniform across task kinds.

## 9. Mandatory deviation and objection report

### a) Deviations from the task specification

- One generation call was made in a first attempt that crashed before any result was persisted: `log_step` was called with an experiment id that had not been registered, raising an SQLite foreign-key error after the first `chat_json` response was received but before it was stored. The orphan partial store files were removed and the harness was fixed (commit `589bfbb`, `store.create_experiment(...)` before logging). The crashed call produced no auditable cell and is excluded from all 60 reported cells; total generation calls in this block are therefore 61, still within the 70-call budget. No result, endpoint or gate was altered by the fix — it is store-logging infrastructure only.
- A second post-run edit corrected the FROZEN exclusion prefix from `block15_order_v2_` to `block15_order_v2` so the store DB `data/block15_order_v2.sqlite3` is recognised as a NEW artifact rather than counted as FROZEN. This aligns the implementation with the pre-registered rule that all `data/block15_order_v2_*` new artifacts are excluded from FROZEN. It changes only the read-only verification/enumeration helper; no result cell, endpoint, gate or sampling value changed. Re-running the read-only `--summarize` after this fix produced the FROZEN numbers in section 6 (118/118, manifest hash matching baseline).
- The report is committed after the run, as specified; the pre-registration commit (`9dac3e4`) predates all generation.
- STEP 0 correction: the `module_sha256` quoted in section 7 (`a6fcbcde…`) was the worktree CRLF hash; the canonical **Git blob** hash of the module at the report commit is `26829883d0cb9e63a406e09917bd1bc5cae608424191be73b89fc9c8ae7eab32`, and at the generating commit `589bfbb` it is `fa40c0f3356c0c1b0ef104ef4dcb5678a8eb2c568346572950427d3aeb72243a`. An additive helper (`git_blob_sha256`) now records the blob hash per arm in future result files. This does not change any result cell.

### b) Deviations from the reference contract

- The effective instruction adds the pre-registered schema-order sentence on top of the shared neutral `OUTPUT_INSTRUCTION_V2`. This is required by the task, not a deviation from it. `DERIVATION_FIRST_V2` remains byte-identical to Round 3's `EXPERIMENTAL_SCHEMA`; `SYSTEM_PROMPT_V2` remains Round 3's `SYSTEM_PROMPT`.
- This study's two schemas use contract v2's `final_answer`/`derivation`-array shape rather than Round 3's `answer`/`derivation`-string shape; that is the pre-registered single-shape contract, not an unreported change.

### c) Where the design is wrong or still confounded

- The added sentence instructs the model to follow schema order. It is identical in both arms and points at the manipulated variable, but it means the measured effect is 'schema order when the model is told to follow it', not a pure implicit-order effect.
- With `final_answer` constrained to the first property in one arm, the model must commit to a value before producing supporting derivation. The large effect is consistent with that forced-commitment mechanism, but this study does not isolate it from a generic 'answer before reasoning' penalty because only the first two positions swap; uncertainty and confidence remain last in both arms.
- `matches_own_schema` is order-only: it does not assert the values or types are correct. It is persisted alongside `validate_v2`, never as a substitute for it.
- Truncation is not fully eliminated: one derivation_first cell hit `done_reason=length`. G2 passes at 3.33%, but a tighter budget might change that.
- The primary endpoint uses presence of the exact coefficient (or n, value and both primes), per the pre-registration; a verbose wrong answer that happens to contain the right integer would pass. A stricter `strict_single_int` / `strict_set_equal` diagnostic is stored per cell but is not the primary measure.
- Contradicting pre-registered expectations, the answer_first arm scored 0/30. This may reflect a floor effect for this model on forced-answer-first decoding rather than a clean linear ordering effect; the size of the difference should not be extrapolated.

### d) What I could not verify

- Server-side schema-enforcement internals: `schema_enforced=True` and `protocol_variant=primary` mean the accepted payload carried the schema dict and the primary HTTP variant succeeded, not that llama.cpp enforced every keyword. No network model API was used; only local Ollama.
- Model understanding or any generalisation beyond these 30 prompts and one seed.
- Whether the single discarded crashed-attempt call would have changed any result (it was never persisted and cannot be audited).
- A historical pre-block hash for files that did not exist at `6c788a5`; those LIVE rows are reported as `new` with `before=None`.

---

## 10. Correction — single failure-accounting convention (added in STEP 1 of the placebo task)

A single machine-computed convention is now defined in `block15/accounting.py` and used
everywhere: `failed_cells` = cells with no audited pass; `failure_flags` = a per-cell list
from the FIXED enumerated set {call_error, parse_failed, schema_violation, truncated,
primary_wrong, confidence_out_of_range, copy_possible}; `failure_events` = sum of
`len(failure_flags)` over NON-PASS cells only (passing cells contribute zero). No stored
result cell was altered — flags are re-derived from raw fields via a fresh parse.

ORDER_V2 totals, old vs corrected:

| Arm | old total events | corrected failed_cells | corrected failure_events | corrected partition (non-pass cells) |
|---|---:|---:|---:|---|
| answer_first | 30 | 30 | 30 | primary_wrong=30 |
| derivation_first | 16 | 12 | 16 | primary_wrong=12, call_error=1, parse_failed=1, truncated=1, confidence_out_of_range=1 |

The ORDER_V2 numbers are unchanged under the new convention (its old `total_failure_events`
already summed only non-pass cells). The correction changes the DIAGNOSIS totals — see
section 10 of `REPORT_DIAGNOSIS.md`. The ORDER_V2 success criterion (30 vs 16) is unaffected.

