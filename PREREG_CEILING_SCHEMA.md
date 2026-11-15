# PREREG_CEILING_SCHEMA - Schema field-order replication on 20 new tasks

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, before the first ceiling-study model call and before
any ceiling-study result existed.
**Upstream HEAD at freezing:** `a6942aa07b6ab6751693368daa9a5ea9cda93756`
**Upstream report:** `REPORT_RESEARCH.md`. The schema axis survived the prior
five-task study (2/5 non-copy audit passes) and Phase 0 was CLEAN.
**Scope:** fully local evaluation only. No network model API, no training, no
dependency change, no model download, no weight modification.
**Working directory:** `C:\Users\famva\Downloads\daan\daan`

This document is a commitment. The 20 task prompts, expected values, prompt
hashes, schema hashes, audit rule, copy rule, call plan and success criterion
are fixed here before generation. Any later deviation must be reported
explicitly and must not silently change the criterion.

---

## 0. Upstream state and protected artifacts

- Gate 0 passed immediately before this freeze: `HEAD =
  a6942aa07b6ab6751693368daa9a5ea9cda93756`, clean tree.
- `REPORT_RESEARCH.md` reports Phase 0 CLEAN and one surviving axis, schema
  field order: derivation-first produced 2/5 non-copy audit passes where the
  answer-first baseline produced 0/5. The other two one-axis interventions
  (`num_predict=2400` alone, `temperature=0.0` alone) produced 0/5.
- The prior result is narrow (five tasks, one call per cell, one seed). This
  experiment asks whether the schema-order effect replicates on a larger,
  independent 20-task held-out set.
- Model: `lfm3base:latest` only. Quantization `Q4_K_M`; manifest digest
  `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`.
  The run refuses to start if either changes.
- Protected artifacts: Round 3/4, existing `PREREG_*` and `REPORT_*`,
  `qresearch/`, `qbacktest/`, existing `mdl/` logic and
  `block15/heldout_research.py`. The new harness imports existing helpers
  read-only and writes only new `block15_ceiling_*` stores. It never executes
  `block15/round3_report.py`.

---

## 1. Frozen held-out tasks

Twenty fresh tasks: 12 coefficient-extraction and 8 bounded-minimality. None
is a Round 3 prompt and none reuses an H1-H5 polynomial or minimality
polynomial. Ground truth is computed by SymPy at run time and checked against
the frozen values below. The prompt SHA-256 covers the exact user prompt,
including the shared output instruction.

| # | ID | Kind | Question (shared instruction appended) | Frozen ground truth | Prompt SHA-256 |
|---|---|---|---|---|---|
| 1 | `C01_coeff_3x_minus_4_pow7_x3` | coefficient | Expand `(3x - 4)^7` and report the coefficient of `x^3`, including its sign. | `241920` | `41d7bec91e6ebc17c9cb78c0dcb360f2d367e8e3b123a5ab8c2d67ca6409d1f4` |
| 2 | `M01_minimal_n2_plus_5n_plus_1187` | minimality | Smallest `n >= 0` with `f(n) = n^2 + 5n + 1187` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 3`, `1211 = 7 * 173` | `e8f45591bb0e035027dea9cae9e8d0166850135b70491be1e8ea568b843bebf1` |
| 3 | `C02_coeff_5x_plus_2_pow8_x3` | coefficient | Expand `(5x + 2)^8` and report the coefficient of `x^3`, including its sign. | `224000` | `679986ac81decf4666c775b76d7d064f96784ec73768eab2d1c0f11b7256eff9` |
| 4 | `M02_minimal_n2_plus_n_plus_1091` | minimality | Smallest `n >= 0` with `f(n) = n^2 + n + 1091` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 4`, `1111 = 11 * 101` | `c4e03ca7bd46f4b24c775f2f9d1acc5841fada0fd90d1d26749eaff9c9f1de9e` |
| 5 | `C03_coeff_2x_plus_5_pow9_x4` | coefficient | Expand `(2x + 5)^9` and report the coefficient of `x^4`, including its sign. | `6300000` | `52a91b07834694aba3ab7e70fa204a963b97931f1c2c6d05524d2f96206dcefd` |
| 6 | `M03_minimal_n2_plus_3n_plus_1213` | minimality | Smallest `n >= 0` with `f(n) = n^2 + 3n + 1213` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 4`, `1241 = 17 * 73` | `3e7c502c5b405bbd77f07820e1116172b9246c1e46b700b605cff86d2021e150` |
| 7 | `C04_coeff_4x_minus_3_pow6_x2` | coefficient | Expand `(4x - 3)^6` and report the coefficient of `x^2`, including its sign. | `19440` | `8b7fd00732cfcd04130d6cd5945073c5d04d1ca8a553e25d3d120a9bfa6545a3` |
| 8 | `M04_minimal_3n2_plus_3n_plus_1013` | minimality | Smallest `n >= 0` with `f(n) = 3n^2 + 3n + 1013` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 4`, `1073 = 29 * 37` | `5fd82398b598a7b4e4595b553012d32ef2b5b0273bb27de765b55666fe0fa8ea` |
| 9 | `C05_coeff_3x_plus_2_pow10_x6` | coefficient | Expand `(3x + 2)^10` and report the coefficient of `x^6`, including its sign. | `2449440` | `1ba593aa6297358e1af2ea53c8392779b2c2aabd9a5f3e4069685ac3ae057097` |
| 10 | `M05_minimal_n2_plus_n_plus_1427` | minimality | Smallest `n >= 0` with `f(n) = n^2 + n + 1427` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 5`, `1457 = 31 * 47` | `d7dc4766c85f8234c62647bb718469086b8ce32d4105facff72535708edfa492` |
| 11 | `C06_coeff_6x_minus_1_pow7_x4` | coefficient | Expand `(6x - 1)^7` and report the coefficient of `x^4`, including its sign. | `-45360` | `1696cf2a1647b71b775e2af254535075a393cd8d70e67e0dfff5b40ca102d432` |
| 12 | `M06_minimal_2n2_plus_2n_plus_1447` | minimality | Smallest `n >= 0` with `f(n) = 2n^2 + 2n + 1447` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 5`, `1507 = 11 * 137` | `1b11c935af364ed06b2599de55b88e5fef2e93da15ae9498a9a8066641ec220f` |
| 13 | `C07_coeff_2x_minus_5_pow8_x3` | coefficient | Expand `(2x - 5)^8` and report the coefficient of `x^3`, including its sign. | `-1400000` | `274a2857b90d9efe4dbec1ba6501d5e6f5f6529d60e657f5f8c96dc454f1921f` |
| 14 | `M07_minimal_n2_plus_3n_plus_1279` | minimality | Smallest `n >= 0` with `f(n) = n^2 + 3n + 1279` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 6`, `1333 = 31 * 43` | `331b9f41ff6cc2278dfa100106ef4c89aeedb5aee84a5fe4e1b3cd6c55242dff` |
| 15 | `C08_coeff_5x_minus_3_pow7_x2` | coefficient | Expand `(5x - 3)^7` and report the coefficient of `x^2`, including its sign. | `-127575` | `aa34a4a3db18876ff31e6216c8e2fd2882a79a37df9ad3eba2ad70d953d83550` |
| 16 | `M08_minimal_2n2_plus_2n_plus_1009` | minimality | Smallest `n >= 0` with `f(n) = 2n^2 + 2n + 1009` composite; give `n`, `f(n)` and the complete prime factorization. | `n = 7`, `1121 = 19 * 59` | `321fa214a6f2a55362ae75a9857f1182459d5c31f2f2a58e79725846cf18a758` |
| 17 | `C09_coeff_4x_plus_1_pow9_x5` | coefficient | Expand `(4x + 1)^9` and report the coefficient of `x^5`, including its sign. | `129024` | `b21757007d0630c4fd93debd74fe9a2a760d080e5a2de362d9d07e0b2d39b923` |
| 18 | `C10_coeff_3x_plus_5_pow8_x4` | coefficient | Expand `(3x + 5)^8` and report the coefficient of `x^4`, including its sign. | `3543750` | `e2fbde95b267207aaef1951adc9840e228a9fc83ef4bf7e359b754ed497a2cd6` |
| 19 | `C11_coeff_6x_minus_5_pow6_x3` | coefficient | Expand `(6x - 5)^6` and report the coefficient of `x^3`, including its sign. | `-540000` | `f5c67a01560543a2f6b049cc50c6b80e502dca15be000136910dcb6f4c134035` |
| 20 | `C12_coeff_2x_plus_7_pow9_x6` | coefficient | Expand `(2x + 7)^9` and report the coefficient of `x^6`, including its sign. | `1843968` | `d5e7c35632d374f8eadfab161e7b44874c1c7f5d2d8d1797cd7a92695eb27f30` |

The exact user prompt for each task is the question text followed by the
shared instruction in section 1.1. The table's question column is an
abbreviation only; the harness stores the exact text and the SHA-256 above is
computed over the exact text.

### 1.1 Shared user-prompt instruction

Every task prompt is the task question followed by exactly:

```
Return a JSON object with exactly these fields: answer, confidence, derivation, uncertainty. The answer field must contain only the final answer; put all intermediate steps in derivation. Put every string on one line; do not use markdown or code fences.
```

The field list is deliberately alphabetical, so it does not cue either schema
field order.

### 1.2 System prompt

```
You are a local mathematical reasoning model. Solve each task independently from the information given. Return exactly one JSON object matching the required schema. Be concise and exact. Do not use markdown or code fences.
```

### 1.3 Frozen hashes

| Artifact | SHA-256 |
|---|---|
| Ground-truth manifest (20 tasks) | `53fd2a8b1fa5e2368b881081c67635bb284a0d04d84a7983a9abd04f5b866f46` |
| Task freeze (IDs, prompt hashes, truth) | `8d1010a7ad43dc025c903dfe026d90b5370d234a1072b512b2ad7ef8a7366204` |
| Harness `block15/ceiling_research.py` | `65334ef0d302bea063a062d7f585a20b942a1dc4f401da5509c121fcfc5da513` |
| Answer-first schema | `9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7` |
| Derivation-first schema | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` |

The two schema hashes are identical to the prior held-out study, so the
schema definitions themselves are unchanged; only the task set is new.

SymPy verification performed before freezing: every coefficient was recomputed
from the frozen expression and power; every minimality task was brute-forced
from `n = 0` upward to the first composite, checked squarefree, and factored
with `sympy.factorint`. The independent pre-freeze verification is reported in
`REPORT_CEILING.md`.

---

## 2. Experiment 1: one axis, schema field order

**Axis:** JSON Schema field order.

| | Baseline | Intervention |
|---|---|---|
| Condition key | `answer_first_1200` | `derivation_first_1200` |
| Schema order | `answer`, `derivation`, `confidence`, `uncertainty` | `derivation`, `answer`, `confidence`, `uncertainty` |
| Schema SHA-256 | `9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7` | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` |
| `num_predict` | `1200` | `1200` |
| Temperature | `0.1` | `0.1` |

Only the order of `answer` and `derivation` in `required` and `properties`
changes. The field set, field types, length limits, task prompts, system
prompt, output instruction, model, seed, `num_ctx=8192`, `think=false`,
`top_p=1.0`, `repeat_penalty=1.1`, `keep_alive=10m`, call count and scoring
are identical. No memory or previous attempt is injected.

The baseline is run first, on all 20 tasks, one call per task. The
derivation-first condition is run second, on the same 20 tasks in the same
order, one call per task. The derivation-first run is refused unless the
answer-first run is complete (20 tasks, not stopped early).

## 3. Success criterion

> Experiment 1 survives iff, over the same 20 tasks:
>
> 1. the derivation-first condition has strictly more audited non-copy passes
>    than the answer-first baseline, **and**
> 2. the derivation-first condition has no more invalid-JSON failures than the
>    answer-first baseline.
>
> A pass is `audit_passed = true` and `copy_possible = false`. An incomplete
> 20-task run is not a success.

The primary count is the strict answer-field audit in section 4, not the
exploratory raw-text near-miss count. A transport error, timeout, invalid
JSON, schema violation or length truncation is a failure for the primary
criterion; no retry or repair is made.

**Invalid-JSON failure (fixed definition):** a cell whose raw response is
absent, or from which no JSON object can be decoded by the same
fence-stripping / first-object `raw_decode` rule the client uses. Valid JSON
that fails schema validation is a separate `schema_invalid` category and is
**not** counted as invalid JSON. Both categories are reported.

## 4. Audit and copy rules

The score is the strict `audit_passed` on the validated `answer` field,
computed with SymPy at run time.

- **Coefficient tasks:** the answer field must contain exactly one distinct
  integer, equal to the SymPy coefficient of the requested power. A negative
  sign is preserved. Extra integers, including the power, fail.
- **Minimality tasks:** exponent-one notation (`^1`, `**1`, `^{1}`) is removed
  before integer extraction because it is factorization notation, not an extra
  value. The answer field's integer set must then be exactly
  `{n, f(n), p1, ..., pk}`, and SymPy must verify the squarefree
  factorization of `f(n)`. Extra integers fail.

A validated final is required for the primary audit. A response that parses as
JSON but violates the schema is a primary failure; its answer field may be
re-audited descriptively and reported as a contract-only near-miss.

No memory or previous attempt is injected. The only copy surface is the fixed
prompt. Every expected answer token is checked against the prompt with the
frozen signed-integer matcher; all 20 tasks have `copy_possible = false`
before generation, and the run refuses to start if that check fails.

## 5. Analysis plan

- Primary: per-task paired outcomes, `answer_first_1200` versus
  `derivation_first_1200`; counts of audited non-copy passes; exact two-sided
  McNemar test on the discordant pairs; risk difference with a task-level
  paired bootstrap 95% percentile interval (10,000 resamples, seed 42).
- Descriptive: per-task status, `done_reason`, eval tokens, confidence,
  answer text, invalid-JSON and schema-invalid counts, length-truncated count,
  and the near-miss category where JSON parses but schema validation fails
  while the answer field is mathematically correct.
- The McNemar p-value and interval are reported for calibration, not as a
  substitute for the fixed criterion. With n=20 and one call per cell, the
  study is descriptive and the confidence is low.

## 6. Directional prediction (not part of the criterion)

Derivation-first order may make the model commit to the final integer after
writing intermediate steps, reducing premature answers on coefficient tasks.
It may also have no effect if the model ignores schema property order. Either
outcome is reportable. A negative result means the prior 2/5 was likely noise.

## 7. Falsification

Experiment 1 dies if derivation-first does not have strictly more audited
non-copy passes than answer-first, or if it has more invalid-JSON failures, or
if either 20-task run is incomplete. A clean negative is a valid result. No
task, prompt, schema, audit rule or criterion may be changed in response to
the observed outcome.

## 8. Call plan and guards

- Experiment 1: 20 baseline calls + 20 intervention calls = 40 calls.
- Experiment 2 (separate pre-registration) adds 20 calls, for a planned total
  of 60 calls in this study.
- Cumulative limits: 80 model calls and 3600 s for this study; 1800 s per
  phase; 450 MB minimum free physical memory checked before every call.
- The run refuses to rerun a condition that already has a result file, and it
  refuses to start an intervention before its prerequisite condition is
  complete. On a guard trip the phase stops, the completed rows are kept, and
  the run is reported as incomplete; missing cells are not imputed as passes.

## 9. Limits

One call per task per condition, one model, one quantization, one seed, n=20.
The experiment tests a prompt/schema-order effect only. It cannot establish a
general reasoning improvement and makes no weight-adaptation claim. The audit
is a strict rule-based check of the answer field, not a proof of reasoning.
The task family is bounded algebra and bounded minimality; no claim is made
about other task families or other models.
