# PREREG_HELDOUT_NUMPREDICT — Output-budget experiment

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, before the first held-out model call and before any
held-out result existed.
**Parent pre-registration:** `PREREG_HELDOUT_BASELINE.md` fixes the five
held-out tasks, prompts, SymPy ground truth, audit rule, copy rule, guards and
baseline condition. This document adds exactly one experiment.

---

## 1. One axis

**Axis:** `num_predict` (maximum generated tokens).

| | Baseline | Intervention |
|---|---|---|
| `num_predict` | `1200` | `2400` |
| Everything else | fixed | identical |

The schema stays answer-first (SHA-256
`9c2955901190dc653fb1d7e411e7cc51884117ae9e929c60c04ee9ef824802d7`). Task
prompts, system prompt, output instruction, model, seed, `num_ctx`,
temperature `0.1`, `top_p`, `repeat_penalty`, `keep_alive`, call count and
scoring are identical to the baseline. No memory is injected.

## 2. Baseline

The baseline is the five-task, answer-first condition defined and committed in
`PREREG_HELDOUT_BASELINE.md`, with `num_predict = 1200`. The baseline is run
before this condition. Its per-task `audit_passed` values define the eligible
set: every task whose baseline audit fails.

This experiment runs on all five tasks, one call per task, regardless of the
baseline outcome. Only baseline-failing tasks count toward the criterion.

## 3. Success criterion

> This experiment survives iff, on at least one task whose baseline
> `audit_passed = false`, the `num_predict = 2400` condition produces
> `audit_passed = true` with `copy_possible = false`.

A pass on a task that already passed the baseline is descriptive only and does
not satisfy the criterion. A transport error, timeout, invalid JSON or schema
violation is a failure; no retry or repair is made. An incomplete run is not a
success.

## 4. Directional prediction (not part of the criterion)

If baseline responses hit the `1200`-token cap (`done_reason = "length"`) or
run out of room before closing the JSON object, the larger budget may allow a
complete derivation and answer. If every baseline response already stops
normally, this experiment is a pre-registered no-op test and is expected to
change nothing. The baseline `done_reason` values are reported as the
diagnostic.

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

One call per task, one model, one seed, one quantization. Larger output budget
cannot add task knowledge or correct a wrong arithmetic strategy; it can only
remove a length constraint. No capability ranking or weight-adaptation claim
is made.
