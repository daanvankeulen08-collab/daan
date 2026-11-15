# PREREG_HELDOUT_SCHEMA — Schema field-order experiment

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, before the first held-out model call and before any
held-out result existed.
**Parent pre-registration:** `PREREG_HELDOUT_BASELINE.md` fixes the five
held-out tasks, prompts, SymPy ground truth, audit rule, copy rule, guards and
baseline condition. This document adds exactly one experiment.

---

## 1. One axis

**Axis:** JSON Schema field order.

| | Baseline | Intervention |
|---|---|---|
| Schema order | `answer`, `derivation`, `confidence`, `uncertainty` | `derivation`, `answer`, `confidence`, `uncertainty` |
| Schema SHA-256 | `9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7` | `841cf27b6c159f1d48b5c4f3f45b095a2197f0d737b837fc4fb0c2e392bb386c` |

Only the order of `answer` and `derivation` in `required` and `properties`
changes. The field set, field types, length limits, task prompts, system
prompt, output instruction, model, seed, `num_ctx`, `num_predict`, temperature,
`top_p`, `repeat_penalty`, `keep_alive`, call count and scoring are identical
to the baseline. No memory is injected.

The shared user instruction lists the fields alphabetically
(`answer, confidence, derivation, uncertainty`), so it does not cue either
order.

## 2. Baseline

The baseline is the five-task, answer-first condition defined and committed in
`PREREG_HELDOUT_BASELINE.md`. The baseline is run before this condition. Its
per-task `audit_passed` values define the eligible set: every task whose
baseline audit fails.

This experiment runs on all five tasks, one call per task, regardless of the
baseline outcome. Only baseline-failing tasks count toward the criterion.

## 3. Success criterion

> This experiment survives iff, on at least one task whose baseline
> `audit_passed = false`, the derivation-first condition produces
> `audit_passed = true` with `copy_possible = false`.

A pass on a task that already passed the baseline is descriptive only and does
not satisfy the criterion. A transport error, timeout, invalid JSON or schema
violation is a failure; no retry or repair is made. An incomplete run is not a
success.

## 4. Directional prediction (not part of the criterion)

Derivation-first order may make the model commit to the final integer only
after writing intermediate steps, which could reduce premature answers on the
coefficient tasks. It may also have no effect if the model ignores schema
property order. Either outcome is reportable.

## 5. Falsification

The hypothesis dies if the condition produces zero non-copy audit passes on
the eligible set, or if every pass is `COPY-POSSIBLE`, or if the run stops
before all five tasks. A clean negative is a valid result.

## 6. Call plan and guards

Five calls in this phase. Cumulative limits, per-phase runtime, memory floor,
new-store policy and the no-rerun rule are those in
`PREREG_HELDOUT_BASELINE.md`: 80 calls and 3600 s overall, 900 s for this
phase, 450 MB free physical memory.

## 7. Limits

One call per task, one model, one seed, one quantization. The experiment tests
a prompt/schema-order effect only; it cannot establish a general reasoning
improvement, and it makes no weight-adaptation claim.
