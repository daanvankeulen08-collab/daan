# PREREG_CEILING_BUDGET - Sequential `num_predict` test on derivation-first

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, before the first ceiling-study model call and before
any ceiling-study result existed.
**Upstream HEAD at freezing:** `a6942aa07b6ab6751693368daa9a5ea9cda93756`
**Parent pre-registration:** `PREREG_CEILING_SCHEMA.md` fixes the 20 held-out
tasks, prompts, SymPy ground truth, audit rule, copy rule, schema definitions,
sampling settings and guards. This document adds exactly one sequential
experiment on top of the derivation-first condition.
**Scope:** fully local evaluation only. No network model API, no training, no
dependency change, no model download, no weight modification.

---

## 1. One axis

**Axis:** `num_predict` (output budget).

| | Baseline | Intervention |
|---|---|---|
| Condition key | `derivation_first_1200` | `derivation_first_2400` |
| Schema order | `derivation`, `answer`, `confidence`, `uncertainty` | `derivation`, `answer`, `confidence`, `uncertainty` |
| Schema SHA-256 | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` |
| `num_predict` | `1200` | `2400` |
| Temperature | `0.1` | `0.1` |

Only `num_predict` changes. The schema, tasks, prompts, system prompt, output
instruction, model, digest, quantization, seed, `num_ctx=8192`, `think=false`,
`top_p=1.0`, `repeat_penalty=1.1`, `keep_alive=10m`, one-call-per-task rule
and scoring are identical to the derivation-first condition in Experiment 1.

The baseline is **the Experiment 1 `derivation_first_1200` run itself**, reused
row-for-row. It is not rerun. The intervention is a new
`derivation_first_2400` run on the same 20 tasks in the same order, one call
per task.

## 2. Sequential execution

Experiment 2 is run after Experiment 1. The harness refuses to start
`derivation_first_2400` unless a complete 20-task `derivation_first_1200`
result exists and that run did not stop early. The baseline rows are exactly
the Experiment 1 intervention rows; no row is regenerated, selected or
discarded.

Experiment 2 is executed regardless of Experiment 1's primary verdict. If
Experiment 1 dies, Experiment 2 still measures the budget axis on the same
condition, but it cannot restore the schema hypothesis and is reported as a
descriptive budget result, not as evidence that field order helps.

## 3. Success criterion

> Experiment 2 survives iff, over the same 20 tasks:
>
> 1. at least one task whose `derivation_first_1200` run was
>    **length-truncated** has `audit_passed = false` at 1200 and a new
>    audited non-copy pass at 2400, **and**
> 2. there is **no loss** of existing audited non-copy passes: every task that
>    passed at 1200 also passes at 2400.
>
> An incomplete 20-task run is not a success.

A pass is `audit_passed = true` and `copy_possible = false`, using the same
strict answer-field audit as Experiment 1.

**Length-truncated (fixed definition):** the baseline cell's Ollama
`done_reason` is `length`. This includes both a truncated response that still
parses as JSON and a truncated response whose JSON is incomplete. It does not
include a response that stopped for another reason. The per-task
`done_reason` is stored for every cell.

If no baseline task was length-truncated, the pre-registered conclusion is
that the budget hypothesis cannot be tested on this task set; report that and
stop. The hypothesis dies in that case; it is not replaced with a different
subset or a different budget.

## 4. Audit, copy and scoring

The audit and copy rules are exactly those in `PREREG_CEILING_SCHEMA.md`
section 4. No new normalization, extraction, scoring rule or copy surface is
introduced. The 20 tasks have `copy_possible = false` before generation. A
transport error, timeout, invalid JSON, schema violation or length truncation
is a failure for the primary criterion; no retry or repair is made.

## 5. Analysis plan

- Primary: per-task paired outcomes for `derivation_first_1200` versus
  `derivation_first_2400`; the list of baseline length-truncated tasks; the
  list of additional non-copy passes on those tasks; the list of lost passes.
- Secondary: total audited non-copy passes, invalid-JSON counts, schema-invalid
  counts, `done_reason` counts, eval tokens, confidence and latency per
  condition; exact two-sided McNemar test on the discordant pairs and a
  task-level paired bootstrap 95% interval for the risk difference (10,000
  resamples, seed 42), reported descriptively.
- The fixed criterion is the primary decision. The statistical summaries are
  calibration only, with n=20 and one call per cell.

## 6. Falsification

Experiment 2 dies if there is no length-truncated baseline task, or if no such
task gains an audited non-copy pass at 2400, or if any existing non-copy pass
is lost, or if either run is incomplete. A clean negative is a valid result.
No task, prompt, schema, audit rule, budget or criterion may be changed in
response to the observed outcome.

## 7. Call plan and guards

- Experiment 2: 20 new calls, one per task at `derivation_first_2400`.
- Planned study total: 40 calls in Experiment 1 plus 20 in Experiment 2 = 60
  calls.
- Cumulative limits: 80 model calls and 3600 s for this study; 1800 s per
  phase; 450 MB minimum free physical memory checked before every call.
- The run refuses to rerun a condition that already has a result file. On a
  guard trip the phase stops, the completed rows are kept, and the run is
  reported as incomplete; missing cells are not imputed as passes.

## 8. Limits

One call per task per condition, one model, one quantization, one seed, n=20.
This experiment tests an output-budget effect under one schema order. It
cannot establish a general capability or reasoning improvement, cannot
attribute any change to model weights, and cannot rescue a failed Experiment 1.
The audit is a strict rule-based check of the answer field, not a proof of
reasoning.
