# PREREG_HELDOUT_BASELINE — Held-out bounded-math baseline

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, after the Phase 0 read-only audit returned CLEAN and
before the first held-out model call.
**Working directory:** `C:\Users\famva\Downloads\daan\daan`
**Upstream HEAD at freezing:** `86e2254e84ffbfaf893b37e84802a5b30709e25d`
**Scope:** fully local evaluation only. No network model API, no training, no
dependency change, no model download, no weight modification.

This document is a commitment. The held-out task text, expected values, prompt
hashes, schema hashes, audit rule, copy rule, call plan and success criterion
are fixed here before generation. Any later deviation must be reported
explicitly and must not silently change the criterion.

---

## 0. Upstream state

- Phase 0 audited all 13 unique C attempts in
  `data/block15_pilot_memory_results_20261115T174655Z.json` (read-only).
  No C derivation contained all of `7`, `1333`, `31` and `43`; the
  derivation-aware composite passed 0/13; `audit_passed` was never true while
  the stored composite was false. The memory pilot's NO SIGNAL stands.
- The memory pilot did not establish a non-copy success. This study asks a
  different, held-out question with fresh tasks.
- Model: `lfm3base:latest` only. Quantization `Q4_K_M`; manifest digest
  `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`.
  The run refuses to start if either changes.
- Protected artifacts: Round 3, Round 4, `PREREG_QAD.md`, `REPORT_QAD.md`,
  `PREREG_MEMORY.md`, `REPORT_MEMORY.md`, `qresearch/`, `qbacktest/` and
  existing `mdl/` logic. The harness only imports existing helpers read-only
  and writes new `block15_heldout_*` stores. `block15/round3_report.py` is
  never executed.

---

## 1. Held-out tasks

Five fresh tasks. None is a Round 3 prompt. Ground truth is computed by SymPy
in the harness at run time and cross-checked against the frozen values below.
The prompt SHA-256 covers the exact user prompt, including the shared output
instruction.

| ID | Kind | Question | Frozen ground truth | Prompt SHA-256 |
|---|---|---|---|---|
| `H1_coeff_2x_minus_3_pow7` | coefficient | Expand `(2x - 3)^7` and report the coefficient of `x^5`. | `6048` | `a75ddc7ceac90289989f90cbbf4d931581e576b83d1fd6631ef49b950250bf4e` |
| `H2_coeff_4_minus_x_pow8` | coefficient | Expand `(4 - x)^8` and report the coefficient of `x^3`, including its sign. | `-57344` | `b3379468517e0c89f7500338bf9e78a965057b30c1eb1b1583df454b6b6de797` |
| `H3_coeff_x_plus_5_pow9` | coefficient | Expand `(x + 5)^9` and report the coefficient of `x^6`. | `10500` | `20408f2a45b306a26f6714eb6b38004bcf90ac8d6361791612b7f067ad012fb9` |
| `H4_minimal_n2_plus_n_plus_1301` | minimality | Smallest `n >= 0` with `f(n) = n^2 + n + 1301` composite; give `n`, `f(n)` and its complete prime factorization. | `n = 3`, `1313 = 13 * 101` | `14fa8c1b7ff1e704e3b2ca6b41acee834f003688721bc6f3a9b98186fff1797b` |
| `H5_minimal_2n2_plus_2n_plus_1279` | minimality | Smallest `n >= 0` with `f(n) = 2n^2 + 2n + 1279` composite; give `n`, `f(n)` and its complete prime factorization. | `n = 5`, `1339 = 13 * 103` | `b33479d9bf5ff743c1cf4ba7db913194cd1a8dad38b014a94d63b4abc289f9d8` |

SymPy verification performed before freezing:

- `expand((2*x - 3)**7).coeff(x, 5) = 6048`
- `expand((4 - x)**8).coeff(x, 3) = -57344`
- `expand((x + 5)**9).coeff(x, 6) = 10500`
- For `n^2 + n + 1301`: the first composite is at `n = 3`; `1313 = 13 * 101`.
- For `2n^2 + 2n + 1279`: the first composite is at `n = 5`; `1339 = 13 * 103`.

The ground-truth manifest SHA-256 is
`211f37c5fa9c73fa662608aab2380c2aea99f5bd86552c2578b1d62ca0734646`.

### 1.1 Shared user-prompt instruction

Every task prompt is the task question followed by exactly:

```
Return a JSON object with exactly these fields: answer, confidence, derivation, uncertainty. The answer field must contain only the final answer; put all intermediate steps in derivation. Put every string on one line; do not use markdown or code fences.
```

The field list is deliberately alphabetical, so it does not cue either schema
field order used in the schema experiment.

### 1.2 System prompt

```
You are a local mathematical reasoning model. Solve each task independently from the information given. Return exactly one JSON object matching the required schema. Be concise and exact. Do not use markdown or code fences.
```

---

## 2. Baseline condition

One call per task, five calls total. Baseline uses the **answer-first** schema:

```
required: answer, derivation, confidence, uncertainty
properties: answer, derivation, confidence, uncertainty
```

Schema SHA-256:
`9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7`.

Fixed settings:

- `think = False`
- `num_ctx = 8192`
- `num_predict = 1200`
- `temperature = 0.1`
- `top_p = 1.0`
- `repeat_penalty = 1.1`
- `seed = 42`
- `keep_alive = 10m`
- sequential, single-flight
- no memory, no previous attempt, no tool, no retry, no repair

Attempt 1 is the only attempt. A transport error, timeout, invalid JSON or
schema violation counts as a failure; it is not replaced.

---

## 3. Independent audit (fixed before generation)

The audit reads only the `answer` field. The `derivation` field never changes
the score. All arithmetic is performed by SymPy at run time; the frozen values
above are cross-checks, not the audit's source.

- **Coefficient tasks:** extract distinct standalone integers from `answer`
  (thousands separators removed; Unicode minus normalized; decimals are not
  split). The audit passes iff the extracted set is exactly
  `{expected_coefficient}`. Prose is allowed only if it introduces no other
  integer.
- **Minimality tasks:** the extracted set must be exactly
  `{n, f(n), p1, ..., pk}`. SymPy must independently confirm
  `factorint(f(n))` equals the frozen squarefree factorization and that the
  product of the primes equals `f(n)`. Any extra or missing integer fails the
  audit.

`audit_passed` is the score. There is no separate loose reward that can
override it.

---

## 4. Copy-possible rule

No memory, previous attempt, hint or tool result is injected. The only copy
surface is the fixed prompt. For each task, the harness checks whether any
expected answer token occurs in the prompt as a standalone integer
(`n`, `f(n)` or a prime factor; the coefficient for coefficient tasks).
`copy_possible` is true iff at least one expected token occurs.

The frozen prompts contain none of these tokens; the harness records the
per-token result anyway. A pass with `copy_possible = true` is labelled
`COPY-POSSIBLE` and is excluded from the primary success criterion. A pass
with `copy_possible = false` is non-copy by construction.

---

## 5. Baseline failure set and primary criterion

- A task **fails the baseline** iff its baseline `audit_passed = false`.
- The **eligible set** is exactly the set of baseline-failing tasks. This
  selection rule is fixed now and is not changed after seeing results.
- If the baseline passes all five tasks, the eligible set is empty; the
  intervention question is then reported as **not testable at this baseline**,
  not as a positive result.

Intervention success criterion, used by all three pre-registered experiments:

> An experiment survives iff, on at least one task in the eligible set, its
> single pre-registered call produces `audit_passed = true` with
> `copy_possible = false`.

Passes on baseline-passing tasks are reported descriptively and do not create
the signal. A run that stops before completing all five tasks is reported as
incomplete, not as a success.

Baseline itself is descriptive/calibration; the study's positive claim, if any,
comes from an intervention that meets the criterion above.

---

## 6. Guards and call plan

- Planned calls: baseline `5` + schema `5` + num_predict `5` + temperature `5`
  = `20`.
- Hard cumulative model-call limit: `80`.
- Hard cumulative runtime limit: `3600 s`.
- Per-phase runtime limit: `900 s`.
- Minimum free physical memory before every call: `450 MB`.
- The run refuses to overwrite an existing condition result file or to rerun a
  condition. A guard stop writes partial results and is reported.
- Each phase is a separate process; the cumulative counters are read from the
  prior `data/block15_heldout_results_*.json` files.

New stores only:

- `data/block15_heldout.sqlite3`
- `data/block15_heldout_events.jsonl`
- `data/block15_heldout_results_<condition>_<ts>.json`

The results prefix does not match `block15_round3_results_*`.

---

## 7. Explicit limits

- Five tasks, one seed, one model, one quantization, one machine.
- One call per task and condition; no success@k estimate.
- The eligible set is defined by baseline failure, so the effective n for the
  intervention criterion may be smaller than five.
- The audit is a strict rule-based check of the final answer, not a proof of
  reasoning. A non-copy pass is evidence that the answer was not available in
  the prompt; it is not proof that the model reasoned correctly.
- No capability ranking, no population estimate, no weight-adaptation claim.
- No generalisation to other models, seeds, quantizations or task families.

---

## 8. Reporting plan

`REPORT_RESEARCH.md` will show Phase 0's CLEAN verdict with the C evidence;
the five prompt hashes and ground truth; per-task baseline rows (audit,
extracted integers, answer text, confidence, tokens, `done_reason`, status,
copy flag); the eligible set; each intervention's per-task result and
criterion outcome; the hypotheses that died and any that survived; limits; and
SHA-256 values for the pre-registrations, harness, result JSONs and stores.
`data/` is git-ignored, so the hashes and tables are the audit trail.
