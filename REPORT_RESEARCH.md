# REPORT_RESEARCH — Held-out bounded-math study

**Date:** 2026-11-15
**Model:** `lfm3base:latest`, Q4_K_M, digest
`b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`
**Pre-registration commit:** `64ef88a` (four new `PREREG_HELDOUT_*.md` files
and the harness, committed before any generation)
**Scope:** fully local, no training, no dependency change, no model download,
no network model API.

---

## 0. Verdict at a glance

- **Phase 0: CLEAN.** No C derivation contains all of `7`, `1333`, `31`, `43`;
  the derivation-aware composite passes `0/13`; `audit_passed` was never true
  while the stored composite was false. The memory pilot's NO SIGNAL stands.
- **Phase 1: SIGNAL on one axis.** With five fresh held-out tasks, the
  baseline fails all five. Changing only the JSON Schema field order
  (`derivation` before `answer`) produces **two non-copy, audit-passed
  successes**: H1 (`6048`) and H3 (`10500`). The other two axes,
  `num_predict = 2400` and `temperature = 0.0`, produce **0/5** each.
- **Ceiling:** the model's raw text reaches the correct answer in 16 of 20
  cells. The dominant failure is output-contract compliance, not arithmetic:
  the baseline commits an early wrong `answer`, then derives the correct value
  in `derivation`, and either truncates or closes the JSON with the early
  value. The schema-order axis fixes this for the short coefficient tasks; it
  does not fix the two minimality tasks (one length failure, one genuine
  arithmetic error).
- **Primary result is narrow:** 2/5 tasks, one call per cell, one seed, one
  model. It is evidence that field order can make an existing derivation land
  in the scored answer field. It is **not** evidence of improved reasoning,
  capability, or weight adaptation.

---

## 1. Upstream state and protected artifacts

- Gate 0 passed before Phase 0: `HEAD =
  86e2254e84ffbfaf893b37e84802a5b30709e25d`, clean tree.
- Phase 0 read-only source:
  `data/block15_pilot_memory_results_20261115T174655Z.json`
  (SHA-256 `8de84c44f7dbf38d85e762354084600bb8d87248002bfcfd2dc00da4a98b52f6`).
- Frozen Round 3 ground truth:
  SHA-256 `4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd`.
- The harness imports existing helpers read-only and writes only new
  `block15_heldout_*` stores. `block15/round3_report.py` was never executed.
- All four phase result files record `protected_artifacts_unchanged = true`
  across 33 protected paths. The sorted protected-path hash manifest is
  `e9097088e14360a8e74ab96473d3f9d0193e577e2adb44fdc1bc4303db8280ad`
  in every phase.

---

## 2. Phase 0 — CLEAN, with C derivation evidence

The memory pilot's C task was re-read from the stored results. There are 13
unique C attempts: the shared first attempt plus two retries in each of six
conditions (`N`, `0`, `1`, `2`, `3`, `4`).

| Check | Result |
|---|---|
| Attempts whose **derivation** contains all of `7`, `1333`, `31`, `43` | `0/13` |
| Derivation-aware composite passes | `0/13` |
| Cases where derivation-aware composite passes while stored composite fails | `0` |
| Cases where `audit_passed = true` while the stored composite = false | `0` |

The only partial hit was condition `2`, attempt 3: its **answer** field
contained `7` and `31`, but not `1333` or `43`; its derivation contained none
of the four facts. No derivation reached the complete fact set. The
final-answer-only false-negative condition was therefore not met, no
derivation-aware re-score extension was triggered, and the pilot's NO SIGNAL
stands.

---

## 3. Phase 1 design

### 3.1 Held-out tasks

Five fresh tasks, independent of the Round 3 prompts. Ground truth was
computed with SymPy before the pre-registration and re-verified at every run.

| ID | Kind | Frozen ground truth | Prompt SHA-256 |
|---|---|---|---|
| `H1_coeff_2x_minus_3_pow7` | coefficient | `6048` | `a75ddc7ceac90289989f90cbbf4d931581e576b83d1fd6631ef49b950250bf4e` |
| `H2_coeff_4_minus_x_pow8` | coefficient | `-57344` | `b3379468517e0c89f7500338bf9e78a965057b30c1eb1b1583df454b6b6de797` |
| `H3_coeff_x_plus_5_pow9` | coefficient | `10500` | `20408f2a45b306a26f6714eb6b38004bcf90ac8d6361791612b7f067ad012fb9` |
| `H4_minimal_n2_plus_n_plus_1301` | minimality | `n=3`, `1313=13*101` | `14fa8c1b7ff1e704e3b2ca6b41acee834f003688721bc6f3a9b98186fff1797b` |
| `H5_minimal_2n2_plus_2n_plus_1279` | minimality | `n=5`, `1339=13*103` | `b33479d9bf5ff743c1cf4ba7db913194cd1a8dad38b014a94d63b4abc289f9d8` |

The ground-truth manifest SHA-256 is
`211f37c5fa9c73fa662608aab2380c2aea99f5bd86552c2578b1d62ca0734646`.

### 3.2 Conditions and one-axis interventions

| Condition | Axis | Baseline | Intervention |
|---|---|---|---|
| `baseline` | reference | — | answer-first schema, `num_predict=1200`, `temperature=0.1` |
| `schema` | schema field order | `answer, derivation, confidence, uncertainty` | `derivation, answer, confidence, uncertainty` |
| `numpredict` | output budget | `num_predict=1200` | `num_predict=2400` |
| `temperature` | sampling | `temperature=0.1` | `temperature=0.0` |

All other settings were fixed: `think=False`, `num_ctx=8192`,
`top_p=1.0`, `repeat_penalty=1.1`, `seed=42`, `keep_alive=10m`, one call per
task, no memory, no retry, no repair. The shared user instruction lists the
fields alphabetically, so it does not cue either schema order.

### 3.3 Scoring and copy rule

The score is the strict `audit_passed` on the `answer` field, computed with
SymPy at run time:

- **Coefficient tasks:** the answer field must contain exactly one distinct
  integer, equal to the coefficient.
- **Minimality tasks:** the answer field's integer set must be exactly
  `{n, f(n), p1, ..., pk}`, and SymPy must verify the squarefree
  factorization.

A validated final is required. A transport error, timeout, invalid JSON or
schema violation is a failure. No memory or previous attempt was injected; the
only copy surface is the fixed prompt. No expected answer token occurs in any
prompt, so every pass reported here is `copy_possible = false`.

The baseline-failing set was fixed by the baseline run: all five tasks failed
the baseline audit. The success criterion for each intervention was fixed in
its pre-registration: at least one non-copy audit pass on a baseline-failing
task.

### 3.4 Budget and guards

Planned and actual: 20 calls total, 1173.81 s total, 18,566 eval tokens,
2,832 prompt tokens, minimum free physical memory 1602.2 MB. Limits were 80
calls, 3600 s, and 450 MB. No phase stopped early.

| Phase | Calls | Runtime (s) | Eval tokens | Free min (MB) |
|---|---:|---:|---:|---:|
| baseline | 5 | 336.50 | 5,193 | 1602.2 |
| schema | 5 | 197.92 | 3,166 | 2056.8 |
| numpredict | 5 | 370.22 | 5,884 | 2050.6 |
| temperature | 5 | 269.17 | 4,323 | 2109.4 |
| **total** | **20** | **1173.81** | **18,566** | — |

---

## 4. Baseline results

Baseline schema: answer-first. All five tasks failed; the eligible set is all
five tasks.

| Task | Status | done | eval | Answer field / failure | Audit | Copy | Conf |
|---|---|---|---:|---|---|---|---|
| H1 | `output_error` | `length` | 1200 | no parsed answer; raw answer field `-56`, raw derivation reaches `6048` | false | false | — |
| H2 | `output_error` | `length` | 1200 | no parsed answer; raw answer field `,-70`, raw derivation reaches `-57344` | false | false | — |
| H3 | `ok` | `stop` | 393 | answer field is a derivation; `derivation` field reaches `10500` | false | false | 1.0 |
| H4 | `output_error` | `length` | 1200 | no parsed answer; raw derivation reaches `n=3, 1313=13*101` | false | false | — |
| H5 | `output_error` | `length` | 1200 | no parsed answer; raw derivation is wrong: `n=4, 1325=5^2*53` | false | false | — |

The baseline failure mode is already visible: four calls exhausted the
1200-token budget; the fifth closed valid JSON but put the derivation in the
answer field. H1, H2 and H4 had the correct value in the raw derivation; H3
had it in the `derivation` field. H5 was a genuine arithmetic error.

---

## 5. Experiment 1 — schema field order (SURVIVES)

**Pre-registration:** `PREREG_HELDOUT_SCHEMA.md`, SHA-256
`f0791a23a840049b58eec901882faa1fca60bcdd957e121db8f2d66ac31e7291`.
**Only change:** `derivation` before `answer` in the JSON Schema `required` and
`properties`; everything else fixed.

| Task | Status | done | eval | Answer field | Audit | Copy | Conf |
|---|---|---|---:|---|---|---|---|
| H1 | `ok` | `stop` | 278 | `6048` | **true** | false | 1.0 |
| H2 | `invalid` | `stop` | 269 | `-57344` | false* | false | 100 (invalid) |
| H3 | `ok` | `stop` | 219 | `10500` | **true** | false | 1.0 |
| H4 | `output_error` | `length` | 1200 | no parsed answer; raw derivation reaches `n=3, 1313=13*101`, truncated before the answer | false | false | — |
| H5 | `output_error` | `length` | 1200 | no parsed answer; raw derivation is wrong: `n=4, 1325=5^2*53` | false | false | — |

`*` H2 is a **contract-only near-miss**: the answer is exactly `-57344`, but
`confidence: 100` violates the schema's `maximum: 1`, so validation — and
therefore the pre-registered audit — fails. A math-only re-audit would pass
it; the primary criterion does not count it.

**Primary passes:** H1, H3 = **2/5**. Both are non-copy, valid JSON, exact
answer-field matches. **Verdict: SURVIVES.**

The two winning responses:

- H1 answer: `6048`. Derivation: binomial theorem with `k=2`;
  `C(7,2)=21`, `2^5=32`, `21*32*9=6048`; "Therefore the coefficient of x^5 is
  6048."
- H3 answer: `10500`. Derivation: binomial theorem with `k=3`;
  `C(9,3)=84`, `5^3=125`, `84*125=10500`; "So coefficient is 10500."

The independent re-audit recomputed both coefficients with SymPy and extracted
exactly `{6048}` and `{10500}` from the answer fields. No other integer was
present. Copy-token checks for `6048` and `10500` against the fixed prompts
were false.

---

## 6. Experiment 2 — `num_predict = 2400` (DIES)

**Pre-registration:** `PREREG_HELDOUT_NUMPREDICT.md`, SHA-256
`ca3eb4cc4fc9ed676155f06ebee6fbf285c329182730ccf39aea9c3626d2b492`.
**Only change:** `num_predict` from `1200` to `2400`; everything else fixed.

| Task | Status | done | eval | Answer field | Audit | Copy | Conf |
|---|---|---|---:|---|---|---|---|
| H1 | `ok` | `stop` | 1597 | `-56` (derivation reaches `6048`) | false | false | 0.95 |
| H2 | `ok` | `stop` | 1253 | `,-70` (derivation reaches `-57344`) | false | false | 0.90 |
| H3 | `ok` | `stop` | 393 | answer field is a derivation; `derivation` reaches `10500` | false | false | 1.0 |
| H4 | `ok` | `stop` | 1230 | answer field is exploration beginning `n=0`; `derivation` reaches `n=3, 1313=13*101` | false | false | 0.99 |
| H5 | `ok` | `stop` | 1411 | `1`; derivation is wrong: `n=4, 1325=5^2*53` | false | false | 0.95 |

**Primary passes:** **0/5**. **Verdict: DIES.**

This is the diagnostic result of the study. The larger budget let every
response close valid JSON, but it did **not** move the correct value into the
answer field. H1, H2 and H4 still carried the early wrong guess or exploration
in `answer` while the `derivation` field reached the right value. H3 still put
the derivation in the answer field. More output space fixed the truncation,
not the answer-commitment order. H5 remained genuinely wrong.

---

## 7. Experiment 3 — `temperature = 0.0` (DIES)

**Pre-registration:** `PREREG_HELDOUT_TEMPERATURE.md`, SHA-256
`c030a675c1a3e25250360e93fcf722d17ac643de87647232c7e3df228887fa3f`.
**Only change:** `temperature` from `0.1` to `0.0`; everything else fixed.

| Task | Status | done | eval | Answer field | Audit | Copy | Conf |
|---|---|---|---:|---|---|---|---|
| H1 | `invalid` | `stop` | 1156 | `-56`; confidence out of range | false | false | invalid |
| H2 | `ok` | `stop` | 832 | `,-70` (derivation reaches `-57344`) | false | false | 0.99 |
| H3 | `ok` | `stop` | 393 | answer field is a derivation; `derivation` reaches `10500` | false | false | 1.0 |
| H4 | `ok` | `stop` | 742 | answer field is exploration beginning `n=0`; `derivation` reaches `n=3, 1313=13*101` | false | false | 1.0 |
| H5 | `output_error` | `length` | 1200 | no parsed answer | false | false | — |

**Primary passes:** **0/5**. **Verdict: DIES.**

Greedy decoding did not repair the answer field. H2 and H4 still wrote the
early wrong/exploratory value into `answer`; H3 still wrote the derivation
there; H1 hit the confidence validation; H5 still truncated and remained
wrong.

---

## 8. Independent audit and the near-miss ceiling

Every stored raw response was independently re-parsed with a separate script.
The expected values were recomputed from SymPy; the integer extraction and
set-equality checks were reimplemented in that script; the stored raw SHA-256
was rechecked.

- 20 rows re-audited.
- 2 stored audit passes (schema H1, H3); both recomputed true.
- 3 recomputed math-only passes (schema H1, H2, H3); the extra one is H2,
  excluded by `confidence: 100`.
- 1 stored-vs-recomputed mismatch: schema H2, explained by validation, not by
  a math error.
- 0 stored passes failed independent re-audit, i.e. **no false positives**.
- All 20 raw SHA-256 values matched; all protected-artifact manifests were
  unchanged.

### 8.1 Exploratory near-miss table (not the pre-registered score)

"Answer has all" means the answer field contains every expected integer;
"Derivation has all" means the derivation field does; "Raw has all" means
anywhere in the raw response. For parse failures the first two are unavailable
(false), while "Raw has all" can still be true.

| Condition | Task | Status | done | Stored audit | Answer has all | Derivation has all | Raw has all |
|---|---|---|---|---|---|---|---|
| baseline | H1 | output_error | length | false | false | false | true |
| baseline | H2 | output_error | length | false | false | false | true |
| baseline | H3 | ok | stop | false | false | true | true |
| baseline | H4 | output_error | length | false | false | false | true |
| baseline | H5 | output_error | length | false | false | false | false |
| numpredict | H1 | ok | stop | false | false | true | true |
| numpredict | H2 | ok | stop | false | false | true | true |
| numpredict | H3 | ok | stop | false | false | true | true |
| numpredict | H4 | ok | stop | false | false | true | true |
| numpredict | H5 | ok | stop | false | false | false | false |
| schema | H1 | ok | stop | true | true | true | true |
| schema | H2 | invalid | stop | false | true | true | true |
| schema | H3 | ok | stop | true | true | true | true |
| schema | H4 | output_error | length | false | false | false | true |
| schema | H5 | output_error | length | false | false | false | false |
| temperature | H1 | invalid | stop | false | false | true | true |
| temperature | H2 | ok | stop | false | false | true | true |
| temperature | H3 | ok | stop | false | false | true | true |
| temperature | H4 | ok | stop | false | false | true | true |
| temperature | H5 | output_error | length | false | false | false | false |

The raw text reaches the complete correct answer in **16/20** cells. The
answer field reaches it in **3/20**, all in the schema condition. This is the
ceiling: the model usually knows the answer but does not put it in the field
the contract scores.

### 8.2 What the three failures that remain in the schema condition mean

- **H2** is not a math failure. The answer field is exactly `-57344`; the
  response is invalid only because `confidence: 100` exceeds the schema's
  `maximum: 1`. This is a schema/format near-miss, not a reasoning failure.
- **H4** is not a math failure. The derivation-first response reaches
  `n=3, 1313=13*101`, but the 1200-token budget expires before it writes the
  answer field. The ordering fix worked; the length budget did not.
- **H5** is a genuine arithmetic failure. The model computes
  `f(4) = 2*16 + 8 + 1279 = 1319`, but writes `1325` and factors
  `1325 = 5^2*53`. The true first composite is `n=5`,
  `f(5)=1339=13*103`, which the model never reaches in any condition.

The obvious next hypothesis is the **combination** of derivation-first schema
and a larger `num_predict`: it would address H4 and possibly H2's confidence
format. It is deliberately **not** run here because it changes two axes at
once, and the three-experiment pre-registration is complete.

---

## 9. Hypotheses: dead and surviving

**Survived**

- **H-SCHEMA:** Reordering the JSON Schema so `derivation` precedes `answer`
  can produce non-copy, audit-passed successes on held-out coefficient tasks
  where the answer-first baseline fails. Evidence: H1 and H3, 2/5 primary
  passes, both valid, exact, and non-copy. Secondary: H2 is math-correct but
  fails confidence validation.

**Died**

- **H-NUMPREDICT:** Raising `num_predict` from 1200 to 2400 alone does not
  produce a non-copy audit pass. Evidence: 0/5; it fixes truncation but not
  the answer-field commitment.
- **H-TEMPERATURE:** Lowering temperature from 0.1 to 0.0 alone does not
  produce a non-copy audit pass. Evidence: 0/5.

**Not tested**

- The two-axis combination (derivation-first + larger budget). It is a
  surviving hypothesis for future work, not a result of this study.
- Minimality tasks under any single axis: H4 is a length failure, H5 a genuine
  arithmetic failure.
- Any normalization of percentage-style confidence values; adding one would
  be a new scoring decision.

**Stands**

- The memory pilot's NO SIGNAL stands (Phase 0 CLEAN).

---

## 10. Limits

- Five tasks, one seed, one model, one quantization, one machine. The primary
  positive is two tasks.
- One call per task and condition. No success@k, variance estimate, or
  population claim.
- The baseline-failing set is all five tasks, so the effective n is five; the
  primary pass count is two.
- The audit is a strict rule-based check of the answer field, not a proof of
  reasoning. The independent re-audit is a second implementation over the same
  stored text, not a human mathematical review.
- The exploratory "raw has all" count is not the pre-registered score. It is
  reported to explain the ceiling, not to relabel failures as successes.
- No capability ranking, no claim that the model improved at the weight level,
  no generalisation to other models, seeds, quantizations or task families.
- A non-copy pass means the expected answer token was absent from the prompt.
  It does not prove that the model reasoned independently; the derivation
  text is the evidence for how the answer was reached.
- The schema win is an output-contract effect: in the baseline, the same
  derivations already reached the correct values. The intervention changed
  where the answer was placed, not whether the model could derive it.

---

## 11. Artifact SHA-256

`data/` is git-ignored. These hashes plus the tables above are the audit trail.

| Artifact | SHA-256 |
|---|---|
| `PREREG_HELDOUT_BASELINE.md` | `2838a90ddc3b39ebaa123e1bddadc56ce0a618f71e1e3f4a56f38c5912ccaa20` |
| `PREREG_HELDOUT_SCHEMA.md` | `f0791a23a840049b58eec901882faa1fca60bcdd957e121db8f2d66ac31e7291` |
| `PREREG_HELDOUT_NUMPREDICT.md` | `ca3eb4cc4fc9ed676155f06ebee6fbf285c329182730ccf39aea9c3626d2b492` |
| `PREREG_HELDOUT_TEMPERATURE.md` | `c030a675c1a3e25250360e93fcf722d17ac643de87647232c7e3df228887fa3f` |
| `block15/heldout_research.py` | `396e44b1e5446d2600da5d7f2ea0258a5024c3a9ff403b3612f649959ea07488` |
| `data/block15_heldout_results_baseline_20261115T185523Z.json` | `cea477ebb8b1e3228fa6325f657822afe031649739aa8e22b21886c0f9bf8fcf` |
| `data/block15_heldout_results_schema_20261115T190224Z.json` | `92a6bc19c1fb3897d8378b422cbd3c257a8ace9b5c745e59a5c1cf7cd068d90b` |
| `data/block15_heldout_results_numpredict_20261115T190551Z.json` | `3bc516bccb2062d43fc54d45a22f49e32bd37cde36acb0607e017a34084ea21e` |
| `data/block15_heldout_results_temperature_20261115T191207Z.json` | `05ffcb2088452525cb0fef9a9cf6486117f4bf2c11a340cd84e0767809ce74e4` |
| `data/block15_heldout.sqlite3` | `e6516b01816d362bb0defa012170371dca71e9206ab96246b28a2bcc1520be87` |
| `data/block15_heldout_events.jsonl` | `5eba5fcf5b3dad61bd1ac733a9fddde882efd3e6e4e21515350e99e39f01a28b` |
| Ground-truth manifest | `211f37c5fa9c73fa662608aab2380c2aea99f5bd86552c2578b1d62ca0734646` |
| Protected-path manifest (33 paths, all phases) | `e9097088e14360a8e74ab96473d3f9d0193e577e2adb44fdc1bc4303db8280ad` |
| Memory pilot results (Phase 0 source) | `8de84c44f7dbf38d85e762354084600bb8d87248002bfcfd2dc00da4a98b52f6` |
| Round 3 frozen ground truth (protected) | `4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd` |

---

## 12. Reproduction

From the repository root, with local Ollama running and `lfm3base:latest`
installed:

```
.venv\Scripts\python.exe -m block15.heldout_research --manifest
.venv\Scripts\python.exe -m block15.heldout_research --condition baseline
.venv\Scripts\python.exe -m block15.heldout_research --condition schema
.venv\Scripts\python.exe -m block15.heldout_research --condition numpredict
.venv\Scripts\python.exe -m block15.heldout_research --condition temperature
.venv\Scripts\python.exe -m block15.heldout_research --summarize
```

The harness refuses to rerun an existing condition, refuses a model digest or
quantization mismatch, verifies the frozen prompt, schema and ground-truth
hashes before each phase, and enforces the cumulative call, runtime and
free-memory guards. `block15/round3_report.py` is not part of this study and
was never executed.

---

## 13. Deviations

None. The pre-registered conditions, tasks, prompts, schemas, audit rule,
copy rule and success criteria were run as committed. The independent
re-audit and the exploratory near-miss table were read-only, did not change
any stored score, and are reported separately from the primary criterion. The
temporary analysis scripts used for Phase 0 evidence and the independent
re-audit were deleted before the final commit; `data/` remains untracked.
