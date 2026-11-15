# PREREG_MEMORY — Pre-registration of the memory-retry pilot

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-15, before the first memory-pilot model call and before
any pilot result, event-log line or report existed.
**Working directory:** `C:\Users\famva\Downloads\daan\daan`
**Scope:** fully local evaluation only. No network model API, no training, no
dependency change, no model download, no weight modification.

This document is a commitment. Nothing in the pilot run may deviate from it
without a new, separately committed pre-registration version. The report must
report any deviation explicitly and must not silently adjust the criterion.

---

## 0. Upstream gate (passed before this document was committed)

- `HEAD = f95b7377d7be8e00f0bf10c59e7858bb28043856`, clean work tree.
- Model: `lfm3base:latest` only. `ollama show` reports quantization `Q4_K_M`;
  manifest digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`.
  The QAD model `lfm3qad:latest` is not used by this pilot.
- Frozen ground truth `data/block15_round3_ground_truth.json`:
  SHA-256 `4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd`.
  The `prompt_sha256` of `R3A1_coefficient_protocol_A` and
  `R3C_hypothesis_falsification` match the frozen `RUN_ORDER` task prompts.
- `block15/round3_report.py` is never executed.
- Six Round 3 artifacts, four Round 4 arm stores and both Round 4 results
  JSONs are record-protected. Their pre-run SHA-256 values are recorded in the
  execution log and in the pilot results JSON; they are never written by this
  pilot.

---

## 1. Tasks

Exactly two frozen Round 3 tasks, selected from the unchanged `RUN_ORDER` in
`block15/round3_tasks.py`:

| Task | Protocol | Expected |
|---|---|---|
| `R3A1_coefficient_protocol_A` | `A_round1_answer_reasoning` | `4860` |
| `R3C_hypothesis_falsification` | `B_derivation_first` | `n = 7`, `1333 = 31*43` |

No other task is run. The task prompts, `SYSTEM_PROMPT`, `ANSWER_SCHEMA`,
`EXPERIMENTAL_SCHEMA`, `_validate_answer`, `_validate_experimental`,
`_answer_text`, `_derivation_text`, `_number_present` and
`independent_check` are reused unchanged. No existing function is modified.

---

## 2. Conditions

Six conditions per task, run in this fixed order: `N`, `0`, `1`, `2`, `3`, `4`.

| Condition | Injected content |
|---|---|
| `N` | nothing; prompt byte-identical to attempt 1 |
| `0` | label sentence only; no `<previous_attempt>` block |
| `1` | previous answer field |
| `2` | previous answer field + `"\n"` + last 200 characters of the previous derivation |
| `3` | previous answer field + `"\n"` + previous full derivation |
| `4` | full raw JSON text of the previous response (the exact model `content`, not the Ollama envelope) |

The compressor is deterministic and model-free. For a previous response with
`prev_final = _answer_text(prev)` and `prev_deriv = _derivation_text(prev)`:

```
N : ""
0 : ""
1 : prev_final
2 : prev_final + "\n" + prev_deriv[-200:]
3 : prev_final + "\n" + prev_deriv
4 : previous raw content, byte-for-byte
```

No expected answer, SymPy fact or hint is ever added by the harness.

### 2.1 Memory source when an attempt fails

The memory for retry `t` is built from the immediately preceding attempt in
the same condition. If that attempt produced no validated final:

- level `4` uses that attempt's raw content, which exists even for a JSON
  parse failure (this is why the failure-path instrumentation was added);
- levels `1`–`3` fall back to the most recent validated final in the same
  condition; if none exists, the memory string is empty;
- `N` and `0` are unaffected.

This fallback is part of the pre-registration and is recorded per attempt.

---

## 3. Fixed injection wording

Levels `1`–`4` append the same wrapper, with no wording changes:

```
Your previous attempt was judged incorrect. No further information is available.
<previous_attempt>
{memory}
</previous_attempt>
Attempt the task again.
```

Level `0` appends only:

```
Your previous attempt was judged incorrect.
```

Level `N` appends nothing.

The wrapper is appended to the original task prompt with exactly two newline
characters as separator: `task_prompt + "\n\n" + block`. For `N`, the prompt
is exactly `task_prompt`, so attempt 1 and both `N` retries are byte-identical.

---

## 4. Retry loop and call economy

- Fixed `k = 3` attempts per condition.
- Attempt 1 is run **once per task** and shared by all six conditions. It is
  deterministic and uses the identical original prompt.
- Condition `N` then makes 2 additional identical-prompt calls to verify
  byte-identity.
- Conditions `0`–`4` each make 2 retries, built from the preceding attempt as
  specified above.
- Calls per task: `1 + 6 * 2 = 13`. Total: `2 * 13 = 26`.
- Sequential, single-flight execution. No retry, repair or extra call is made
  after a failure beyond the six pre-registered conditions.

Per-attempt log fields (success and failure): `raw_content`, `done_reason`,
`prompt_eval_count`, `eval_count`, `confidence`, `injected_memory_sha256`,
`answer_present_in_memory` (boolean), latency. The prompt SHA-256, full
memory string, parse/validation status and error text are also stored so the
audit trail is reproducible. `injected_memory_sha256` is the SHA-256 of the
`{memory}` text inside `<previous_attempt>`; it is `null` for attempt 1, `N`
and `0`, which inject no memory block.

---

## 5. Binary reward (fixed before generation)

Reward is binary per attempt, derived only from stored data.

- **A1A:** reward = the stored `independent_check` status equals
  `objective_pass`.
- **C:** reward = the new pre-registered composite, computed from the stored
  flags:
  `final_contains_first_n AND final_contains_counterexample_value AND
  final_contains_factors_31_43`.
  C's stored status is always `manual_review_required`; it is reported next to
  the composite and is *not* the reward.

The reward is never overwritten by the stricter audit.

`success@3` for a condition = at least one of its three attempts (shared
attempt 1 plus its two retries) has `binary_reward = true`.

---

## 6. Stricter independent audit (on every success)

The audit is stored separately as `audit_passed`; it never changes the binary
reward. It runs only when an attempt produced a validated final. Failed
attempts have `audit_passed = false` with a note.

- **A1A:** extract standalone integers from the `answer` field only
  (thousands separators removed; a decimal such as `4860.0` is not split).
  The audit passes iff the set of distinct extracted integers is exactly
  `{4860}`, the SymPy coefficient of `x^4` in `(3x - 2)^6`. Prose is allowed;
  ambiguity or any other integer fails the audit.
- **C:** the `answer` field must contain `7`, `1333`, `31` and `43` as exact
  integers, and SymPy must independently verify
  `1333 = 31 * 43` (`factorint(1333) == {31: 1, 43: 1}` and
  `31 * 43 == 1333`).

A combined event "reward and audit" is reported per attempt. It is the event
used by the C success criterion.

---

## 7. Copy-possible rule

For each retry, `answer_present_in_memory` is true iff the ground-truth token
of that task (`4860` for A1A, `1333` for C) occurs as an exact integer in the
injected memory block. `N` and `0` inject no memory and are always false.
`13330` does not count as `1333`; `1,333` does count as `1333`.

**A pass with `answer_present_in_memory = true` must be labelled
`COPY-POSSIBLE` in the report.** The label is descriptive; it does not change
the binary reward. This matters especially for level 2–4 memories built from a
derivation that reached the right number while the final answer did not.

---

## 8. Settings (identical to Round 3)

- `think = False`
- `num_ctx = 8192`
- `temperature = 0.1`
- `top_p = 1.0`
- `repeat_penalty = 1.1`
- `seed = 42`
- `keep_alive = 10m`
- `num_predict = 1200`
- Sequential, single-flight. Sampling and the client fallback chain are not
  varied.

---

## 9. Guards

- Maximum 30 model calls (planned 26).
- Maximum runtime 2400 s.
- Minimum free physical memory 450 MB, checked before every call.
- The model must be `lfm3base:latest`, `Q4_K_M`, digest
  `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`;
  otherwise the run refuses to start.
- The frozen ground-truth SHA-256 and both task prompt hashes are re-verified
  at startup; mismatch aborts before generation.
- The pilot refuses to overwrite an existing store or results file.

If a guard stops the run, partial results are written and the report states
which task/condition/attempt was not run. No replacement run is made under
this pre-registration.

---

## 10. Stores and results

New files only:

- `data/block15_pilot_memory.sqlite3`
- `data/block15_pilot_memory_events.jsonl`
- `data/block15_pilot_memory_results_<ts>.json`

The results filename deliberately does **not** match
`block15_round3_results_*.json`, so `block15/round3_report.py`'s glob cannot
pick it up. `block15/round3_report.py` is never executed.

---

## 11. Success criterion

The pre-registered criterion is:

> "Signal exists iff at least one compression level yields a C composite pass
> with audit_passed=true while condition N fails all 3 attempts."

Operational reading, fixed now:

- "C composite pass" means the pre-registered composite in section 5.
- "with audit_passed=true" means the same attempt also passes the stricter C
  audit in section 6.
- "condition N fails all 3 attempts" means all three `N` rewards are false.
- The compression levels are `1`, `2`, `3`, `4`. Level `0` (label only) and
  `N` (no injection) are controls and cannot create the signal. A sensitivity
  reading that also counts level `0` is reported separately without changing
  the primary verdict.

A1A is reported for descriptive and calibration purposes; the success
criterion is defined on C only.

---

## 12. Explicit limits

- Only 2 tasks, single seed, single model (`lfm3base:latest`), single machine.
- n is very small; per-condition success@3 is descriptive, not a population
  estimate.
- No capability claim about the model, and no claim that the model adapted at
  the weight level. Any improvement is in-context retry behaviour only.
- No generalisation to other tasks, other models, other seeds or other
  quantization levels.
- The stricter audit guards against a known-loose keyword checker, but it is
  still a rule-based check, not a proof of reasoning.
- A `COPY-POSSIBLE` label means the answer token was available in the injected
  memory; it does not prove copying occurred, and an unlabelled pass does not
  prove independent reasoning.

---

## 13. Reporting plan

`REPORT_MEMORY.md` will show, per task × condition × attempt: binary reward,
`audit_passed`, `answer_present_in_memory`, confidence, eval tokens and
`done_reason`; the `N` byte-identity verdict; success@3 per condition;
`COPY-POSSIBLE` labels; both C stored status and composite; a
confidence-versus-correctness table; the success criterion and SIGNAL / NO
SIGNAL verdict; limits; and artifact SHA-256 values. `data/` is git-ignored, so
the hashes plus the report table are the audit trail.
