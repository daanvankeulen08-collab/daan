# REPORT_CEILING — Schema-order replication and a sequential output-budget test

**Date:** 2026-11-16
**Model:** `lfm3base:latest`, Q4_K_M, digest
`b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`
**Pre-registration commit:** `99335a0` (both `PREREG_CEILING_*` files and the
new harness were committed before any ceiling-study generation)
**Upstream gate:** `a6942aa07b6ab6751693368daa9a5ea9cda93756`, clean tree
**Scope:** fully local. No network model API, no training, no dependency
change, no model download, no weight modification. `block15/round3_report.py`
was never executed.

---

## 0. Verdict at a glance

- **Experiment 1 — schema field order: SURVIVES narrowly.** With 20 fresh
  held-out tasks, `derivation_first_1200` produced **2 strict non-copy passes**
  (`C01`, `C11`) against **0** for `answer_first_1200`. Invalid-JSON failures
  fell from **13 to 9**, so both pre-registered conditions are met. The result
  is weak: schema-invalid failures rose from **1 to 6**, total contract
  failures went from **14 to 15**, the exact McNemar p-value is **0.5**, and
  the paired risk-difference interval **[0.0, 0.25]** includes zero.
- **Experiment 2 — `num_predict` 1200 → 2400: INCOMPLETE, not a success.**
  The cumulative 3600 s guard stopped the phase after **7/20** calls. Among the
  completed cells, the existing `C01` pass was preserved, the three
  baseline-length-truncated cells that were reached (`M01`, `M02`, `M03`) all
  closed valid JSON, but **none** produced a new audited pass. Thirteen cells,
  including the previously passing `C11`, were not run. The pre-registration
  requires a complete 20-task run; the verdict is therefore **INCOMPLETE**,
  not survival and not a clean death.
- **All 47 completed cells have `copy_possible = false`.** No expected answer
  token occurs in any prompt. The independent copy recheck found zero
  mismatches.
- **No forced positive.** The schema-order signal replicated directionally,
  but only two cells flipped; the budget question remains unresolved. Both
  facts are reported as they are.

The rest of this report gives the per-task tables, the fixed criteria, the
contract-failure accounting, the independent audit, the budget trip, and the
artifact hashes.

---

## 1. Upstream state and protected artifacts

- **Gate 0 passed immediately before freezing:** `HEAD =
  a6942aa07b6ab6751693368daa9a5ea9cda93756`, clean tree. `REPORT_RESEARCH.md`
  reports Phase 0 CLEAN; the prior five-task schema result was 2/5 non-copy
  passes, with 0/5 for the `num_predict` and `temperature` axes.
- **Protected set:** 86 paths, including Round 3/4 artifacts, every existing
  `PREREG_*` and `REPORT_*`, `qresearch/`, `qbacktest/`, existing `mdl/`
  logic, and `block15/heldout_research.py`. The sorted protected-path manifest
  SHA-256 is
  `31fd884107b529cdb870a36e09788b8aa50d7a6d5c80a89f0c48c38fb463985b`;
  its start and end hashes are identical in all three runs.
- **New artifacts only:** the new harness `block15/ceiling_research.py` and new
  `block15_ceiling_*` SQLite/JSONL stores. Existing harness logic was imported
  read-only and not modified.
- **Model check:** `lfm3base:latest`, digest
  `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`,
  quantization `Q4_K_M`. The harness refuses a digest or quantization
  mismatch.
- `data/` remains git-ignored. The hashes in section 10 plus the tables in
  this report are the audit trail.

---

## 2. Frozen held-out tasks

Twenty fresh tasks were fixed in `PREREG_CEILING_SCHEMA.md`: 12
coefficient-extraction and 8 bounded-minimality tasks, interleaved. They were
fixed as independent of the Round 3 prompts and of the prior H1–H5
polynomials. Ground truth was computed with SymPy before the freeze and
re-verified independently before generation; all 20 checks passed.

The frozen manifest has 20 tasks. The task-freeze SHA-256 is
`8d1010a7ad43dc025c903dfe026d90b5370d234a1072b512b2ad7ef8a7366204`; the
ground-truth manifest SHA-256 is
`53fd2a8b1fa5e2368b881081c67635bb284a0d04d84a7983a9abd04f5b866f46`.
Every task has `copy_possible = false`; the selfcheck and the independent audit
both agree.

| # | ID | Kind | Frozen ground truth | Prompt SHA-256 |
|---|---|---|---|---|
| 1 | `C01_coeff_3x_minus_4_pow7_x3` | coefficient | `241920` | `41d7bec91e6ebc17c9cb78c0dcb360f2d367e8e3b123a5ab8c2d67ca6409d1f4` |
| 2 | `M01_minimal_n2_plus_5n_plus_1187` | minimality | `n = 3, f(n) = 1211 = 7 * 173` | `e8f45591bb0e035027dea9cae9e8d0166850135b70491be1e8ea568b843bebf1` |
| 3 | `C02_coeff_5x_plus_2_pow8_x3` | coefficient | `224000` | `679986ac81decf4666c775b76d7d064f96784ec73768eab2d1c0f11b7256eff9` |
| 4 | `M02_minimal_n2_plus_n_plus_1091` | minimality | `n = 4, f(n) = 1111 = 11 * 101` | `c4e03ca7bd46f4b24c775f2f9d1acc5841fada0fd90d1d26749eaff9c9f1de9e` |
| 5 | `C03_coeff_2x_plus_5_pow9_x4` | coefficient | `6300000` | `52a91b07834694aba3ab7e70fa204a963b97931f1c2c6d05524d2f96206dcefd` |
| 6 | `M03_minimal_n2_plus_3n_plus_1213` | minimality | `n = 4, f(n) = 1241 = 17 * 73` | `3e7c502c5b405bbd77f07820e1116172b9246c1e46b700b605cff86d2021e150` |
| 7 | `C04_coeff_4x_minus_3_pow6_x2` | coefficient | `19440` | `8b7fd00732cfcd04130d6cd5945073c5d04d1ca8a553e25d3d120a9bfa6545a3` |
| 8 | `M04_minimal_3n2_plus_3n_plus_1013` | minimality | `n = 4, f(n) = 1073 = 29 * 37` | `5fd82398b598a7b4e4595b553012d32ef2b5b0273bb27de765b55666fe0fa8ea` |
| 9 | `C05_coeff_3x_plus_2_pow10_x6` | coefficient | `2449440` | `1ba593aa6297358e1af2ea53c8392779b2c2aabd9a5f3e4069685ac3ae057097` |
| 10 | `M05_minimal_n2_plus_n_plus_1427` | minimality | `n = 5, f(n) = 1457 = 31 * 47` | `d7dc4766c85f8234c62647bb718469086b8ce32d4105facff72535708edfa492` |
| 11 | `C06_coeff_6x_minus_1_pow7_x4` | coefficient | `-45360` | `1696cf2a1647b71b775e2af254535075a393cd8d70e67e0dfff5b40ca102d432` |
| 12 | `M06_minimal_2n2_plus_2n_plus_1447` | minimality | `n = 5, f(n) = 1507 = 11 * 137` | `1b11c935af364ed06b2599de55b88e5fef2e93da15ae9498a9a8066641ec220f` |
| 13 | `C07_coeff_2x_minus_5_pow8_x3` | coefficient | `-1400000` | `274a2857b90d9efe4dbec1ba6501d5e6f5f6529d60e657f5f8c96dc454f1921f` |
| 14 | `M07_minimal_n2_plus_3n_plus_1279` | minimality | `n = 6, f(n) = 1333 = 31 * 43` | `331b9f41ff6cc2278dfa100106ef4c89aeedb5aee84a5fe4e1b3cd6c55242dff` |
| 15 | `C08_coeff_5x_minus_3_pow7_x2` | coefficient | `-127575` | `aa34a4a3db18876ff31e6216c8e2fd2882a79a37df9ad3eba2ad70d953d83550` |
| 16 | `M08_minimal_2n2_plus_2n_plus_1009` | minimality | `n = 7, f(n) = 1121 = 19 * 59` | `321fa214a6f2a55362ae75a9857f1182459d5c31f2f2a58e79725846cf18a758` |
| 17 | `C09_coeff_4x_plus_1_pow9_x5` | coefficient | `129024` | `b21757007d0630c4fd93debd74fe9a2a760d080e5a2de362d9d07e0b2d39b923` |
| 18 | `C10_coeff_3x_plus_5_pow8_x4` | coefficient | `3543750` | `e2fbde95b267207aaef1951adc9840e228a9fc83ef4bf7e359b754ed497a2cd6` |
| 19 | `C11_coeff_6x_minus_5_pow6_x3` | coefficient | `-540000` | `f5c67a01560543a2f6b049cc50c6b80e502dca15be000136910dcb6f4c134035` |
| 20 | `C12_coeff_2x_plus_7_pow9_x6` | coefficient | `1843968` | `d5e7c35632d374f8eadfab161e7b44874c1c7f5d2d8d1797cd7a92695eb27f30` |

The prompt hash covers the exact user prompt, including the shared output
instruction. The instruction lists the fields alphabetically
(`answer, confidence, derivation, uncertainty`), so it does not cue either
schema field order. The two schema definitions are byte-identical to the prior
study: answer-first
`9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7`,
derivation-first
`841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c`.

---

## 3. Design, scoring and guards

### 3.1 One axis per experiment

| Experiment | Axis | Baseline | Intervention | Only change |
|---|---|---|---|---|
| 1 | JSON Schema field order | `answer_first_1200` | `derivation_first_1200` | `answer` and `derivation` swap order in `required` and `properties` |
| 2 | output budget | `derivation_first_1200` | `derivation_first_2400` | `num_predict` 1200 → 2400 |

All other settings were fixed: `think=false`, `num_ctx=8192`,
`temperature=0.1`, `top_p=1.0`, `repeat_penalty=1.1`, `seed=42`,
`keep_alive=10m`, one call per task, no retry, no repair, no memory, no
previous attempt. Experiment 1 ran the baseline first and the intervention
second on the same 20 tasks in the same order. Experiment 2 reused the
`derivation_first_1200` rows row-for-row as its baseline; it did not rerun
them.

### 3.2 Scoring and copy rule

The primary score is the strict `audit_passed` on the validated `answer`
field, computed with SymPy at run time.

- **Coefficient tasks:** the answer field must contain exactly one distinct
  integer, equal to the SymPy coefficient of the requested power. A negative
  sign is preserved; extra integers, including the power, fail.
- **Minimality tasks:** exponent-one notation (`^1`, `**1`, `^{1}`) is removed
  before integer extraction because it is factorization notation, not an extra
  value. The answer field's integer set must then be exactly
  `{n, f(n), p1, ..., pk}`, and SymPy must verify the squarefree
  factorization. Extra integers fail.

A validated final is required for the primary audit. A response that parses as
JSON but violates the schema is a primary failure; its answer field may be
re-audited descriptively and reported as a contract-only near-miss. The copy
rule checks every expected signed integer against the fixed prompt; all 20
tasks were `copy_possible = false` before generation, and all completed cells
remain false.

**Invalid JSON** is fixed as a cell whose raw response is absent or from which
no JSON object can be decoded by the client's fence-stripping /
first-object `raw_decode` rule. Valid JSON that fails schema validation is a
separate `schema_invalid` category and is **not** counted as invalid JSON. Both
categories and their sum are reported, because the pre-registered Experiment 1
criterion counts only invalid JSON.

### 3.3 Guards

Cumulative study limits: 80 model calls, 3600 s, 450 MB minimum free physical
memory checked before every call; 1800 s per phase. On a guard trip the phase
stops, completed rows are kept, and missing cells are not imputed as passes.
The 3600 s check is pre-call, so a call already in flight can carry the total
slightly past the nominal ceiling; that is what happened in Experiment 2 and
is quantified in section 9.

---

## 4. Experiment 1 — schema field order

**Pre-registration:** `PREREG_CEILING_SCHEMA.md`, SHA-256
`759d7c3007b564a2b946e41afe1e69fcf70aecbc4248a144a753d344de15c131`.
**Baseline:** `answer_first_1200`. **Intervention:**
`derivation_first_1200`. **Only change:** `derivation` before `answer` in the
JSON Schema; tasks, prompts, settings and scoring are identical.

**Fixed criterion.** Experiment 1 survives iff, over the same 20 tasks,
(1) derivation-first has strictly more audited non-copy passes than
answer-first, and (2) derivation-first has no more invalid-JSON failures than
answer-first. An incomplete 20-task run is not a success.

### 4.1 Condition summary

| Condition | Completed | Strict non-copy passes | Invalid JSON | Schema invalid | Length truncated | Eval tokens | Prompt tokens | Mean latency (s) | Runtime (s) | `done_reason` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `answer_first_1200` | 20/20 | 0 | 13 | 1 | 14 | 20,871 | 2,878 | 84.85 | 1,697.85 | `length` 14, `stop` 6 |
| `derivation_first_1200` | 20/20 | 2 | 9 | 6 | 9 | 18,103 | 2,878 | 72.69 | 1,454.88 | `stop` 11, `length` 9 |

The token counts are Ollama `eval_count` (generated tokens) and
`prompt_eval_count` (prompt tokens), summed over the 20 cells. Both runs are
complete and neither stopped early. Minimum free physical memory was 2005.6 MB
for the baseline and 1912.7 MB for the intervention, both above the 450 MB
guard.

### 4.2 Baseline per-task results (`answer_first_1200`)

| # | Task | Kind | Status | done | eval | Strict | Math | Copy | Conf | Answer field / failure |
|---|---|---|---|---|---:|---|---|---|---:|---|
| 1 | `C01_coeff_3x_minus_4_pow7_x3` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 2 | `M01_minimal_n2_plus_5n_plus_1187` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 3 | `C02_coeff_5x_plus_2_pow8_x3` | coefficient | ok | stop | 939 | N | N | false | 0.95 | 0 |
| 4 | `M02_minimal_n2_plus_n_plus_1091` | minimality | ok | stop | 205 | N | N | false | 0.8 | n=0, f(0)=1091, which is prime? Wait need smallest n>=0 s... |
| 5 | `C03_coeff_2x_plus_5_pow9_x4` | coefficient | ok | stop | 1053 | N | N | false | 0.99 | .-C(9,5)*5^(9-5) = -126*25? Wait compute properly. |
| 6 | `M03_minimal_n2_plus_3n_plus_1213` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 7 | `C04_coeff_4x_minus_3_pow6_x2` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 8 | `M04_minimal_3n2_plus_3n_plus_1013` | minimality | ok | stop | 269 | N | N | false | 1.0 | 1 f(1)=1107=3*3*13*? Wait compute: 3*1^2+3*1+1013=3+3+101... |
| 9 | `C05_coeff_3x_plus_2_pow10_x6` | coefficient | truncated | length | 1200 | N | N | false | 0.95 | JSON incomplete (length) |
| 10 | `M05_minimal_n2_plus_n_plus_1427` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 11 | `C06_coeff_6x_minus_1_pow7_x4` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 12 | `M06_minimal_2n2_plus_2n_plus_1447` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 13 | `C07_coeff_2x_minus_5_pow8_x3` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 14 | `M07_minimal_n2_plus_3n_plus_1279` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 15 | `C08_coeff_5x_minus_3_pow7_x2` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 16 | `M08_minimal_2n2_plus_2n_plus_1009` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 17 | `C09_coeff_4x_plus_1_pow9_x5` | coefficient | invalid | stop | 482 | N | N | false | - | ValueError: confidence must be between 0 and 1 |
| 18 | `C10_coeff_3x_plus_5_pow8_x4` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 19 | `C11_coeff_6x_minus_5_pow6_x3` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 20 | `C12_coeff_2x_plus_7_pow9_x6` | coefficient | ok | stop | 1123 | N | N | false | 0.99 | .-? Let's compute. |

### 4.3 Intervention per-task results (`derivation_first_1200`)

| # | Task | Kind | Status | done | eval | Strict | Math | Copy | Conf | Answer field / failure |
|---|---|---|---|---|---:|---|---|---|---:|---|
| 1 | `C01_coeff_3x_minus_4_pow7_x3` | coefficient | ok | stop | 544 | Y | Y | false | 1.0 | 241920 |
| 2 | `M01_minimal_n2_plus_5n_plus_1187` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 3 | `C02_coeff_5x_plus_2_pow8_x3` | coefficient | ok | stop | 955 | N | N | false | 0.95 | only final answer |
| 4 | `M02_minimal_n2_plus_n_plus_1091` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 5 | `C03_coeff_2x_plus_5_pow9_x4` | coefficient | invalid | stop | 681 | N | N | false | - | ValueError: confidence must be between 0 and 1 |
| 6 | `M03_minimal_n2_plus_3n_plus_1213` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 7 | `C04_coeff_4x_minus_3_pow6_x2` | coefficient | invalid | stop | 343 | N | Y | false | - | ValueError: confidence must be between 0 and 1 |
| 8 | `M04_minimal_3n2_plus_3n_plus_1013` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 9 | `C05_coeff_3x_plus_2_pow10_x6` | coefficient | invalid | stop | 1193 | N | Y | false | - | ValueError: confidence must be between 0 and 1 |
| 10 | `M05_minimal_n2_plus_n_plus_1427` | minimality | invalid | stop | 693 | N | N | false | - | ValueError: confidence must be between 0 and 1 |
| 11 | `C06_coeff_6x_minus_1_pow7_x4` | coefficient | invalid | stop | 352 | N | Y | false | - | ValueError: confidence must be between 0 and 1 |
| 12 | `M06_minimal_2n2_plus_2n_plus_1447` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 13 | `C07_coeff_2x_minus_5_pow8_x3` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 14 | `M07_minimal_n2_plus_3n_plus_1279` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 15 | `C08_coeff_5x_minus_3_pow7_x2` | coefficient | invalid | stop | 406 | N | Y | false | - | ValueError: confidence must be between 0 and 1 |
| 16 | `M08_minimal_2n2_plus_2n_plus_1009` | minimality | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 17 | `C09_coeff_4x_plus_1_pow9_x5` | coefficient | ok | stop | 661 | N | N | false | 0.99 | only final answer |
| 18 | `C10_coeff_3x_plus_5_pow8_x4` | coefficient | output_error | length | 1200 | N | N | false | - | no decodable JSON (length) |
| 19 | `C11_coeff_6x_minus_5_pow6_x3` | coefficient | ok | stop | 495 | Y | Y | false | 1.0 | -540000 |
| 20 | `C12_coeff_2x_plus_7_pow9_x6` | coefficient | ok | stop | 980 | N | N | false | 0.99 | The answer field must contain only the final answer; put... |

### 4.4 Paired outcome and calibration

| Paired outcome | Count |
|---|---:|
| Both fail | 18 |
| Baseline pass, intervention fail | 0 |
| Baseline fail, intervention pass | 2 |
| Both pass | 0 |

The two flips are `C01` (`241920`) and `C11` (`-540000`); both are coefficient
tasks, both have confidence `1.0`, both have `copy_possible = false`. There are
no baseline-only passes. The paired risk difference is **+0.10**, with a
task-level paired bootstrap 95% interval of **[0.0, 0.25]** (10,000 resamples,
seed 42). The exact two-sided McNemar p-value is **0.5**; the descriptive odds
ratio is infinite. With two discordant pairs, 0.5 is the smallest attainable
two-sided p-value. These statistics are calibration only: the fixed criterion,
not the p-value, decides the verdict.

**Verdict: SURVIVES narrowly.** Both fixed conditions are met: 2 > 0 passes,
and 9 < 13 invalid-JSON failures. The run is complete.

### 4.5 Near-misses and the contract-failure account

| Category | `answer_first_1200` | `derivation_first_1200` |
|---|---:|---:|
| Strict non-copy passes | 0 | 2 |
| Math-only answer-field passes (schema-blind) | 0 | 6 |
| Invalid JSON | 13 | 9 |
| Schema invalid | 1 | 6 |
| **Invalid JSON + schema invalid** | **14** | **15** |
| Length truncations | 14 | 9 |

Six derivation-first cells have a mathematically correct answer field under a
schema-blind re-audit: `C01`, `C04`, `C05`, `C06`, `C08`, `C11`. Two are the
strict passes. The other four are rejected only because confidence is outside
the schema's `[0, 1]` range: `C04` uses `100`, `C05` uses `2`, `C06` uses
`100`, and `C08` uses `100`. Their answer fields are `19440`, `2449440`,
`-45360` and `-127575`, all exactly correct. `C03` puts the placeholder
`exact integer` in the answer field, and `M05` gives `1, 1435, 5*7*41`, which
is wrong; neither is a math-only pass. The baseline has no math-only pass.

This accounting is the main caution. Derivation-first reduced invalid JSON and
length truncation, but it converted several failures into confidence-schema
violations. Under the pre-registered criterion, which counts only invalid JSON,
the intervention is better; under a broader contract-failure count it is
slightly worse, 15 versus 14. The result is therefore a narrow contract-order
effect, not a general reliability improvement.

### 4.6 Interpretation of the two wins

- **`C01`:** `(3x − 4)^7`, coefficient of `x^3`. The derivation selects
  `k=4`, computes `C(7,4) * 3^3 * (−4)^4 = 35 * 27 * 256 = 241920`, and writes
  `241920` in the answer field. `done_reason=stop`, `eval_count=544`,
  confidence `1.0`.
- **`C11`:** `(6x − 5)^6`, coefficient of `x^3`. The derivation selects
  `k=3`, computes `C(6,3) * 6^3 * (−5)^3 = 20 * 216 * (−125) = −540000`, and
  writes `-540000`. `done_reason=stop`, `eval_count=495`, confidence `1.0`.

Both wins are on coefficient tasks. No minimality task passes strictly in
either arm; the minimality cells are dominated by length truncation and, in
the intervention, by confidence-schema failures. The schema order moved two
already-derivable coefficient answers into the scored field. It did not make
the model better at arithmetic or at the minimality search.

---

## 5. Experiment 2 — sequential `num_predict`

**Pre-registration:** `PREREG_CEILING_BUDGET.md`, SHA-256
`4b3925fb9b0ae316ba29c7461e7c6343183d4e65823e1c4c7d3bc198f9e827d3`.
**Baseline:** `derivation_first_1200`, reused row-for-row from Experiment 1;
not rerun. **Intervention:** `derivation_first_2400`. **Only change:**
`num_predict` from 1200 to 2400; schema, tasks, prompts and settings are
identical.

**Fixed criterion.** Experiment 2 survives iff, over the same 20 tasks:
(1) at least one task whose `derivation_first_1200` run was length-truncated
has `audit_passed = false` at 1200 and a new audited non-copy pass at 2400;
and (2) there is no loss of existing audited non-copy passes. An incomplete
20-task run is not a success. A clean negative is valid; missing cells are not
imputed as passes.

### 5.1 Completed-cell summary (conditional on 7/20)

| Condition | Completed | Strict non-copy passes | Invalid JSON | Schema invalid | Length truncated | Eval tokens | Prompt tokens | Mean latency (s) | Runtime (s) | `done_reason` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `derivation_first_2400` | **7/20** | 1 | 0 | 2 | 0 | 7,570 | 1,009 | 64.55 | 452.09 | `stop` 7 |

These totals are conditional on the seven completed cells and are not
comparable to the full 20-cell rows above. All seven stopped normally; no cell
was length-truncated and no cell produced invalid JSON. Two cells were
schema-invalid (confidence out of range), and one was a strict pass (`C01`).

### 5.2 Per-task results (`derivation_first_2400`)

`1200 trunc = Y` marks the baseline cells that exhausted 1200 tokens. Those
are the only cells eligible for the "new pass on a truncated baseline"
criterion.

| # | Task | Kind | 1200 trunc | 2400 status | done | eval | Strict | Math | Copy | Conf | Answer field / failure |
|---|---|---|---|---|---|---:|---|---|---|---:|---|
| 1 | `C01_coeff_3x_minus_4_pow7_x3` | coefficient | N | ok | stop | 544 | Y | Y | false | 1.0 | 241920 |
| 2 | `M01_minimal_n2_plus_5n_plus_1187` | minimality | Y | ok | stop | 1219 | N | N | false | 0.95 | The answer field must contain only the final answer; put... |
| 3 | `C02_coeff_5x_plus_2_pow8_x3` | coefficient | N | ok | stop | 955 | N | N | false | 0.95 | only final answer |
| 4 | `M02_minimal_n2_plus_n_plus_1091` | minimality | Y | ok | stop | 2156 | N | N | false | 0.99 | the final answer; put all intermediate steps in derivatio... |
| 5 | `C03_coeff_2x_plus_5_pow9_x4` | coefficient | N | invalid | stop | 681 | N | N | false | - | ValueError: confidence must be between 0 and 1 |
| 6 | `M03_minimal_n2_plus_3n_plus_1213` | minimality | Y | ok | stop | 1672 | N | N | false | 0.99 | the final answer; put all intermediate steps in derivatio... |
| 7 | `C04_coeff_4x_minus_3_pow6_x2` | coefficient | N | invalid | stop | 343 | N | Y | false | - | ValueError: confidence must be between 0 and 1 |
| 8 | `M04_minimal_3n2_plus_3n_plus_1013` | minimality | Y | not run | - | - | - | - | false | - | - |
| 9 | `C05_coeff_3x_plus_2_pow10_x6` | coefficient | N | not run | - | - | - | - | false | - | - |
| 10 | `M05_minimal_n2_plus_n_plus_1427` | minimality | N | not run | - | - | - | - | false | - | - |
| 11 | `C06_coeff_6x_minus_1_pow7_x4` | coefficient | N | not run | - | - | - | - | false | - | - |
| 12 | `M06_minimal_2n2_plus_2n_plus_1447` | minimality | Y | not run | - | - | - | - | false | - | - |
| 13 | `C07_coeff_2x_minus_5_pow8_x3` | coefficient | Y | not run | - | - | - | - | false | - | - |
| 14 | `M07_minimal_n2_plus_3n_plus_1279` | minimality | Y | not run | - | - | - | - | false | - | - |
| 15 | `C08_coeff_5x_minus_3_pow7_x2` | coefficient | N | not run | - | - | - | - | false | - | - |
| 16 | `M08_minimal_2n2_plus_2n_plus_1009` | minimality | Y | not run | - | - | - | - | false | - | - |
| 17 | `C09_coeff_4x_plus_1_pow9_x5` | coefficient | N | not run | - | - | - | - | false | - | - |
| 18 | `C10_coeff_3x_plus_5_pow8_x4` | coefficient | Y | not run | - | - | - | - | false | - | - |
| 19 | `C11_coeff_6x_minus_5_pow6_x3` | coefficient | N | not run | - | - | - | - | false | - | - |
| 20 | `C12_coeff_2x_plus_7_pow9_x6` | coefficient | N | not run | - | - | - | - | false | - | - |

### 5.3 What the completed cells show

- **The existing pass is preserved.** `C01` is again `ok`, `stop`, 544 eval
  tokens, answer `241920`, strict pass, confidence `1.0`. Its raw content is
  byte-identical to the 1200 run.
- **Four of the seven completed cells are byte-identical to 1200:** `C01`,
  `C02`, `C03`, `C04`. All four had stopped naturally at 1200. Raising the
  budget changed nothing when the model had already finished.
- **The three cells that changed are exactly the three baseline
  length-truncated cells that were reached:** `M01`, `M02`, `M03`. Each now
  stops (`done_reason=stop`) at 1219, 2156 and 1672 eval tokens,
  respectively, instead of exhausting 1200. All three close valid JSON. None
  produces a strict pass, because the scored answer field is wrong:
  - `M01`: the derivation reaches the correct `n=3, f(3)=1211=7*173`, but the
    answer field contains the instruction text "The answer field must contain
    only the final answer; put all intermediate steps in derivation."
  - `M02`: the derivation reaches the correct `n=4, f(4)=1111=11*101`, but the
    answer field contains only "the final answer; put all intermediate steps
    in derivation."
  - `M03`: the answer field again contains only the instruction fragment, and
    the derivation is genuinely wrong: it computes `f(4)=1221=3*11*37`
    instead of the true `f(4)=1241=17*73`. This is an arithmetic failure, not
    a formatting near-miss.
- **`C04` remains a contract-only near-miss.** Its math-only answer field is
  correct (`19440`) at both budgets, but confidence `100` keeps the strict
  audit false. It was not baseline-length-truncated, so it is not eligible for
  the Experiment 2 criterion.

The descriptive mechanism is consistent: more output space fixes JSON
completion, not answer-field content. In all three eligible completed cells,
the larger budget produced a finished object but no new audited pass; in two
of them the correct answer is visibly present in the derivation and absent
from the scored field.

### 5.4 Budget trip and verdict

The phase stopped at **7/20** calls with the message
`cumulative runtime budget 3600s reached`. The last call began at roughly
3585 s cumulative and took 19.4 s, carrying the total to 3604.82 s. No further
call was made. Thirteen cells were not run: `M04`, `C05`, `M05`, `C06`, `M06`,
`C07`, `M07`, `C08`, `M08`, `C09`, `C10`, `C11`, `C12`.

**Verdict: INCOMPLETE, not a success.** The pre-registration requires a
complete 20-task run. Nine baseline-length-truncated tasks existed; only three
were reached. Zero additional passes were observed on those three, and the
existing `C01` pass was preserved. `C11`, a 1200-baseline pass, was not run at
2400, so its status at the larger budget is unknown.

The summary file's `lost_existing_passes = ['C11']` is a **sentinel artifact**:
the summary treats an unrun cell as a failure so that missing cells cannot be
mistaken for passes. It is not an observed loss. Among completed cells, the
observed loss count is zero. The incomplete verdict holds regardless, because
the criterion requires all 20 cells.

No paired test is reported for Experiment 2. With 13 missing cells, any
paired interval would be dominated by the imputation convention, not by an
observed budget effect.

---

## 6. Audit and integrity checks

### 6.1 Internal recheck

`--recheck` read all 47 stored rows and re-verified the stored scores, raw
hashes, prompt hashes, copy flags, protected manifest and JSONL chain.

| Check | Result |
|---|---|
| Rows checked | 47 |
| Stored strict passes | 3 (`DF1200: C01`, `DF1200: C11`, `DF2400: C01`) |
| Recomputed math-only passes | 8 |
| Audit false positives | 0 |
| Raw-hash mismatches | 0 |
| Prompt-hash mismatches | 0 |
| Copy mismatches | 0 |
| Row mismatches | 0 |
| Protected-manifest failures | 0 |
| JSONL chain | valid, 56 events, no error |

### 6.2 Independent audit

A separate script re-parsed every stored raw response, recomputed the expected
values from SymPy, reimplemented the integer extraction and set-equality
checks, and rechecked the hashes. It did not import the scoring path from the
harness.

| Check | Result |
|---|---|
| Rows audited | 47 |
| Stored strict passes | 3 |
| Recomputed strict passes | 3 |
| Recomputed math-only passes | 8 |
| False positives (stored pass, recomputed fail) | 0 |
| Contract-only false negatives | 0 |
| Raw-hash mismatches | 0 |
| Prompt-hash mismatches | 0 |
| Copy mismatches | 0 |
| Protected-manifest failures | 0 |
| `prompt_hashes_ok` / `copy_rule_ok` | true / true |
| `ok` | **true** |

The eight math-only passes are:

| Condition | Task | Why it is not a strict pass |
|---|---|---|
| `derivation_first_1200` | `C01` | strict pass |
| `derivation_first_1200` | `C04` | confidence `100` (schema invalid) |
| `derivation_first_1200` | `C05` | confidence `2` (schema invalid) |
| `derivation_first_1200` | `C06` | confidence `100` (schema invalid) |
| `derivation_first_1200` | `C08` | confidence `100` (schema invalid) |
| `derivation_first_1200` | `C11` | strict pass |
| `derivation_first_2400` | `C01` | strict pass |
| `derivation_first_2400` | `C04` | confidence `100` (schema invalid) |

No baseline cell is a math-only pass. Every schema-invalid cell in both
experiments fails for the same reason: confidence is outside `[0, 1]`. That is
a stable output-contract failure mode, not an arithmetic error.

### 6.3 Copy-possible flags

All 20 tasks were checked before generation: no expected signed integer occurs
in the prompt, so `copy_possible = false` for every task. The same flag is
false in all 47 completed rows. The independent audit recomputed the check
from the frozen prompts and found zero mismatches. A pass therefore cannot be
explained by copying an answer token from the task text.

---

## 7. Hypotheses: dead and surviving

**Survives, narrowly**

- **H-SCHEMA-CEILING:** putting `derivation` before `answer` can move an
  already-derivable coefficient answer into the scored `answer` field on fresh
  held-out tasks. Evidence: 2/20 strict, non-copy passes (`C01`, `C11`)
  against 0/20 in the answer-first baseline, with fewer invalid-JSON failures
  (9 vs 13). This replicates the direction of the prior 2/5 result. It is
  narrow: the exact McNemar p-value is 0.5, the risk-difference interval
  includes zero, schema-invalid failures rose 1 → 6, and total contract
  failures did not improve (14 → 15). It is an output-contract effect, not
  evidence of better reasoning.

**Not resolved by this run**

- **H-BUDGET-2400:** raising `num_predict` from 1200 to 2400 after
  derivation-first may rescue baseline-length-truncated tasks. Evidence is
  incomplete: only 3 of the 9 eligible baseline-truncated tasks were reached,
  and none produced a new pass. The pre-registered verdict is **INCOMPLETE**.
  This hypothesis is not counted as dead, because six eligible cells and seven
  other cells were never run; it is also not counted as surviving, because the
  criterion requires a complete run and at least one new pass.

**Dead in the completed subset (descriptive, not the pre-registered primary)**

- **H-BUDGET-SUFFICIENT:** "More output budget alone is sufficient to move the
  correct value into the scored answer field on derivation-first minimality
  tasks." In the three eligible completed cells, all three now finish
  (`M01`, `M02`, `M03`), but 0/3 produce a strict pass. `M01` and `M02` have
  the correct value in the derivation and instruction text in the answer
  field; `M03` is genuinely wrong (`1221` instead of `1241`). This subset
  falsifies sufficiency for those cells, but it is not the full Experiment 2
  criterion and does not establish a general negative.

**Observed, not tested as an axis**

- **Confidence formatting:** every schema-invalid cell in both experiments is
  a confidence value outside `[0, 1]` (`100` or `2`), not a wrong field type
  or missing field. Neither schema order nor the larger budget fixes it. A
  confidence-normalization or stricter decoding intervention would be a new
  axis and was not run.

---

## 8. Limits

- **Small, single-call design.** Twenty tasks, one call per task per condition,
  one model, one quantization, one seed, one machine. Experiment 1's positive
  is two cells; its exact p-value is 0.5 and its risk-difference interval
  includes zero. No success@k, variance estimate, or population claim follows.
- **Narrow task family.** Twelve coefficient tasks and eight bounded
  minimality tasks. No minimality task passes strictly in any condition. No
  claim is made about other algebra, other task families, other models, other
  seeds or other quantizations.
- **Contract, not reasoning.** The audit is a strict rule-based check of the
  answer field, not a proof of reasoning. The independent audit is a second
  implementation over the same stored text, not a human mathematical review.
  In several near-misses the derivation is correct while the answer field is
  not; that is evidence about field placement, not about latent capability.
- **The Experiment 1 positive is fragile.** The criterion counts invalid JSON
  only. Schema-invalid failures increased from 1 to 6; total contract failures
  went from 14 to 15. A broader contract criterion would not have called this
  a win.
- **Experiment 2 is incomplete and selected by execution order.** The seven
  completed cells are the first seven tasks in the fixed order, not a random
  sample. They include only 3 of the 9 eligible baseline-truncated tasks.
  Thirteen cells, including the baseline pass `C11`, were not run. Missing
  cells are not imputed.
- **Budget overshoot.** The nominal 3600 s ceiling was exceeded by 4.82 s
  because the guard checks before a call, not during one. No call was made
  after the trip. See section 9.
- **No generalisation.** Nothing here supports a capability ranking, a
  weight-level improvement, or a claim that the model "learned" anything. The
  model weights were not modified.

---

## 9. Budget, guards and deviations

### 9.1 Actual usage

| Phase | Calls | Runtime (s) | Eval tokens | Prompt tokens | Free min (MB) |
|---|---:|---:|---:|---:|---:|
| `answer_first_1200` | 20 | 1,697.85 | 20,871 | 2,878 | 2,005.6 |
| `derivation_first_1200` | 20 | 1,454.88 | 18,103 | 2,878 | 1,912.7 |
| `derivation_first_2400` | 7 | 452.09 | 7,570 | 1,009 | 2,249.0 |
| **Total** | **47** | **3,604.82** | **46,544** | **6,765** | **1,912.7** |

Limits were 80 calls, 3600 s cumulative, 1800 s per phase, and 450 MB free
physical memory. The call budget was not close (47/80); the runtime budget was
the binding constraint. No phase hit the 1800 s phase cap. The minimum free
memory, 1912.7 MB, stayed well above 450 MB.

### 9.2 The 4.82 s overshoot

The harness checks cumulative runtime before each call. The seventh
Experiment 2 call started at about 3585 s cumulative, under the 3600 s limit,
and ran for 19.4 s, so the run ended at 3604.82 s. This is a pre-call guard
semantics issue, not a missing guard and not a retry. No call was made after
the trip; the phase stopped with 13 tasks unrun.

### 9.3 Deviations

- **Experiment 2 is incomplete.** This is the pre-registered guard behavior,
  not a changed criterion. The run is reported as `INCOMPLETE`; the 13 missing
  cells are not imputed.
- **The summary's `lost_existing_passes = ['C11']` is a sentinel, not an
  observed loss.** The summary maps an unrun cell to a failure so that missing
  cells cannot look like passes. `C11` was not run at 2400. Among completed
  cells the observed loss count is zero.
- **The independent audit script was corrected once before its successful
  run.** A local variable named `audit` collided with the audit function; it
  was renamed to `report`. The script only reads stored artifacts and does not
  change any model output or stored score.
- No task, prompt, schema, audit rule, copy rule, budget or success criterion
  was changed in response to the observed outcomes. No retry, repair, or
  selective rerun was made. `block15/round3_report.py` was never executed.

---

## 10. Artifact SHA-256

`data/` is git-ignored. These hashes plus the tables above are the audit trail.

| Artifact | SHA-256 |
|---|---|
| `PREREG_CEILING_SCHEMA.md` | `759d7c3007b564a2b946e41afe1e69fcf70aecbc4248a144a753d344de15c131` |
| `PREREG_CEILING_BUDGET.md` | `4b3925fb9b0ae316ba29c7461e7c6343183d4e65823e1c4c7d3bc198f9e827d3` |
| `block15/ceiling_research.py` | `65334ef0d302bea063a062d7f585a20b942a1dc4f401da5509c121fcfc5da513` |
| `data/block15_ceiling_results_answer_first_1200_20261115T194214Z.json` | `1ba97edb559a96661cb806d8c53de590c100e41ac598a4c7b23cdc72f1f17cae` |
| `data/block15_ceiling_results_derivation_first_1200_20261115T201101Z.json` | `b2f7b0f39380b60a6a131591063abcd2e7b05c8aa21fe437120fe55882b9a018` |
| `data/block15_ceiling_results_derivation_first_2400_20261116T110703Z.json` | `aefac9b1350cc35e89ee11fa702b79497610ddeff2d7f9e6c74255068dbf57be` |
| `data/block15_ceiling_summary_final.json` | `c2fcbf0cc2892db551dede9252091eeca6088af45311b8df8e5bbdce939bb77e` |
| `data/ceiling_recheck_final.json` | `afbea369e04537d2e83218d5e511ff7e90c85d65ef6ffd17ce159652008f3d26` |
| `data/ceiling_independent_audit.json` | `49fa47202eecd554a8fea6855be3c95fee446154329abe1a972189c610976cde` |
| `data/ceiling_manifest.json` | `413775e561f209e3bc2731a088f8a92e641a45772923a42ef4aeb3b1e49c25e5` |
| `data/ceiling_selfcheck.json` | `de842952449fcd28171de308347c225193e85415a045cc13492030322f73f892` |
| `data/block15_ceiling.sqlite3` | `6ebd5e02fb933cf52d507bc3c61033c24c4fe31b027d70581d59f91e47821f6b` |
| `data/block15_ceiling_events.jsonl` | `494b8e8fd64cdb9dbc988bfddc68b2fdea68c1c21db5a2253940015598f64902` |
| Task-freeze manifest | `8d1010a7ad43dc025c903dfe026d90b5370d234a1072b512b2ad7ef8a7366204` |
| Ground-truth manifest | `53fd2a8b1fa5e2368b881081c67635bb284a0d04d84a7983a9abd04f5b866f46` |
| Answer-first schema | `9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7` |
| Derivation-first schema | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` |
| Protected-path manifest (86 paths) | `31fd884107b529cdb870a36e09788b8aa50d7a6d5c80a89f0c48c38fb463985b` |

---

## 11. Reproduction

From the repository root, with local Ollama running and `lfm3base:latest`
installed:

```
.venv\Scripts\python.exe -m block15.ceiling_research --manifest
.venv\Scripts\python.exe -m block15.ceiling_research --selfcheck
.venv\Scripts\python.exe -m block15.ceiling_research --condition answer_first_1200
.venv\Scripts\python.exe -m block15.ceiling_research --condition derivation_first_1200
.venv\Scripts\python.exe -m block15.ceiling_research --condition derivation_first_2400
.venv\Scripts\python.exe -m block15.ceiling_research --summarize
.venv\Scripts\python.exe -m block15.ceiling_research --recheck
```

The harness refuses to rerun a condition that already has a result file,
refuses an intervention before its prerequisite condition is complete, and
checks the model digest, quantization, frozen prompts, schema hashes and
ground-truth hashes before each phase. A fresh replication of the 2400 phase
would need a new result path and a fresh cumulative budget; the current result
file is immutable by design, and the 3600 s guard remains binding.

---

## 12. Bottom line

The schema-order effect replicated in the same direction but remains weak:
2/20 versus 0/20 strict non-copy passes, with fewer invalid-JSON failures but
more schema-invalid failures and no improvement in total contract failures.
The sequential budget question could not be answered within the fixed
3600 s budget: 7/20 cells ran, the completed subset produced no new pass on a
baseline-truncated task, and the existing pass was preserved. The honest
summary is one narrow, fragile contract-order signal and one unresolved budget
hypothesis, not a capability claim.
