# REPORT_MEMORY — Memory-retry pilot (binary reward)

**Status:** COMPLETED
**Executed:** 2026-11-15, 17:46:55–18:01:27 UTC
**Pre-registration:** `PREREG_MEMORY.md`, committed as `c196dc1`
("Memory pilot: pre-registration, failure-path instrumentation, retry
harness") **before** the first pilot call and before any pilot store or result
existed.
**Scope:** fully local. No network model API, no NVIDIA/OpenAI/Anthropic key,
no training, no dependency change, no model download, no weight modification.
**Model:** `lfm3base:latest` only (QAD model not used).

---

## 0. Gates, model check and record protection

### 0a. Git gate

- HEAD at Gate 0: `f95b7377d7be8e00f0bf10c59e7858bb28043856`.
- Work tree clean at Gate 0. Nothing was reset, restored, stashed or cleaned.
- Phase 1 commit: `c196dc1`; pushed to `origin/main` before generation.

### 0b. Model gate

`ollama show lfm3base:latest` reported:

| Field | Value |
|---|---|
| Quantization | `Q4_K_M` |
| Manifest digest | `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d` |
| Context length | 262144 |
| Embedding length | 2048 |
| Renderer / parser | `lfm3` / `lfm3` |

`ollama stop lfm3qad:latest` was executed before the run and `ollama ps`
showed no loaded model. The pilot runner also refused to start unless the
model was exactly `lfm3base:latest`, `Q4_K_M`, with the digest above. That gate
passed.

### 0c. Frozen ground truth

`data/block15_round3_ground_truth.json` SHA-256:
`4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd`.

The runner re-verified this hash and the `prompt_sha256` of both selected
tasks against the frozen `RUN_ORDER` before generation:

| Task | Prompt SHA-256 | Match |
|---|---|---|
| `R3A1_coefficient_protocol_A` | `05efcd84f82175ce801158947022c79073b4f9d8aca0ee559935333e2df44dd7` | yes |
| `R3C_hypothesis_falsification` | `369363d86fc587aa81240f7cfe68b5fd470985d6cae3ec4169f1380ba6519cc2` | yes |

`block15/round3_report.py` was never executed.

### 0d. Protected-artifact hashes, re-hashed after the run

All twelve hashes below are identical to the pre-run baseline. **No protected
artifact changed.** This was also checked independently a second time after
the run, outside the pilot process.

| Artifact | SHA-256 (pre-run = post-run) |
|---|---|
| `data/block15_round3.sqlite3` | `ec1bfab2e10156e4d9148ece4703153dd5d8ca7f6a12c1c71a76e093343af542` |
| `data/block15_round3_events.jsonl` | `d923e8c0a45674a98dc16f5ad47aa4f372f69d633c4d2faf4b674e5374d7136e` |
| `data/block15_round3_ground_truth.json` | `4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd` |
| `data/block15_round3_assessments.json` | `75d711633f94743420be1f7bdc071e34843e18b89623688c6abd7e2ac6be4511` |
| `data/block15_round3_results_round3_20261111T143825Z.json` | `8ebb5899304602be17c945cb7769378cff8fa5a7776956ec332f0730df7cf87e` |
| `BLOCK15_ROUND3_REPORT.md` | `283eb0c07163fcf0889b8435480e9b3abb0cdf4d392df78daf127f01c4cdd382` |
| `data/block15_round4_arm_a.sqlite3` | `7563eae8cd692f5779614389c07a5cd040b0bb970dc1b1e378c54793a90afb16` |
| `data/block15_round4_arm_a_events.jsonl` | `68877cdae62296bb6667e5600ef169580633ad248e3c4684860adfe40ff57fe5` |
| `data/block15_round4_arm_b.sqlite3` | `d985e8ffd6d684dca15e70ab3d93f2734f77744a1b619c6cc9bc272a6a4cf82a` |
| `data/block15_round4_arm_b_events.jsonl` | `710fc7f02df6f6fcafebe6938559b766bda31f034b4c30bd8e68b9375287d9a4` |
| `data/block15_round4_arm_a_results_round3_20261114T215552Z.json` | `d6f39e7dde69561c9ab00a0404c815a3d03ded94c9b86c581c793dfd3aa734d8` |
| `data/block15_round4_arm_b_results_round3_20261114T220133Z.json` | `6d24f3b2e412ae0e2b805c9888da3518bb219e6c5a00ea84ee1acfe2e1950f6d` |

---

## 1. Execution summary

| Item | Value |
|---|---|
| Run id | `memory_20261115T174655Z` |
| Tasks | 2: A1A and C |
| Conditions | 6: `N, 0, 1, 2, 3, 4` |
| Attempts per condition | 3 (attempt 1 shared) |
| Planned calls | 26 (13 per task) |
| Calls used | **26** (limit 30) |
| Completed calls | 25 |
| Failed calls | 1 (A1A, condition 1, attempt 3: invalid JSON) |
| Runtime | 871.67 s (limit 2400 s) |
| Stopped early | no; no guard tripped |
| Free physical MB start / min / end | 2797.7 / 1703.3 / 1794.5 (minimum 450) |
| Prompt tokens total | 11,504 |
| Eval tokens total | 11,885 |
| `done_reason=length` | 0 |

Settings, identical to Round 3:
`think=false, num_ctx=8192, temperature=0.1, top_p=1.0,
repeat_penalty=1.1, seed=42, keep_alive=10m, num_predict=1200`,
sequential, single-flight. No sampling or fallback-chain change.

Store integrity: the new JSONL chain verifies (`valid=true`, 32 events). The
two task experiments are present in the new SQLite store.

**Deviation:** one of the 26 calls (A1A, condition `1`, attempt 3) failed with
`ModelOutputError: model response is not valid JSON: Invalid control character
at: line 3 column 1553 (char 1573)`. The model emitted a literal control
character inside a JSON string. `done_reason` was `stop` and 630 eval tokens
were produced; this is a model-output failure with no truncation. The
failure-path instrumentation preserved the raw content and metadata. No
replacement call or replacement run was made, per the pre-registration. The
attempt is shown as `failed` below and counts as reward false, audit false.

---

## 1a. Phase 1 verification (before generation)

- `pytest -q -m "not live" -o addopts=""`: **394 passed, 1 deselected,
  0 failed** (355 pre-existing + 39 new pilot/instrumentation tests).
- `uv pip check`: all 26 installed packages compatible.
- `uv pip freeze` unchanged; `pyproject.toml` and `uv.lock` were not modified.
- `git status --porcelain -- qresearch qbacktest`: empty.
- Phase 1 commit `c196dc1` pushed to `origin/main` before the run.

---

## 2. Per-task × condition × attempt results

Legend: `reward` = pre-registered binary reward; `audit` = stricter
independent audit; `mem` = `answer_present_in_memory`; `copy` = COPY-POSSIBLE
(reward true and `mem` true). `stored` is the status returned by the unchanged
`independent_check`. A1A reward is the stored `objective_pass`; C reward is the
new composite, not the stored status.

### 2a. `R3A1_coefficient_protocol_A`

| Cond | Att | Status | reward | audit | mem | copy | conf | eval | done | stored |
|---|---|---|---:|---:|---|---|---:|---|---|
| N | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| N | 2 | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| N | 3 | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 0 | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 0 | 2 | ok | false | false | false | false | 1.00 | 498 | stop | objective_fail |
| 0 | 3 | ok | false | false | false | false | 1.00 | 498 | stop | objective_fail |
| 1 | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 1 | 2 | ok | false | false | false | false | 0.99 | 855 | stop | objective_fail |
| 1 | 3 | **failed** | false | false | false | false | — | 630 | stop | — |
| 2 | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 2 | 2 | ok | false | false | false | false | 1.00 | 369 | stop | objective_fail |
| 2 | 3 | ok | **true** | **true** | true | **COPY-POSSIBLE** | 1.00 | 147 | stop | objective_pass |
| 3 | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 3 | 2 | ok | **true** | **true** | true | **COPY-POSSIBLE** | 0.99 | 132 | stop | objective_pass |
| 3 | 3 | ok | **true** | **true** | true | **COPY-POSSIBLE** | 1.00 | 124 | stop | objective_pass |
| 4 | 1 (shared) | ok | false | false | false | false | 0.99 | 753 | stop | objective_fail |
| 4 | 2 | ok | **true** | **true** | true | **COPY-POSSIBLE** | 0.99 | 143 | stop | objective_pass |
| 4 | 3 | ok | **true** | **true** | true | **COPY-POSSIBLE** | 0.99 | 100 | stop | objective_pass |

All five A1A passes are **COPY-POSSIBLE**. There is no A1A pass whose memory
did not contain `4860`; the A1A improvement cannot be attributed to
independent reasoning from this pilot.

The answers illustrate the failure mode: the shared attempt derives `4860`
correctly in its reasoning but returns `-21`; condition N reproduces that
exactly. Condition 0 returns `84` with confidence 1.00. Condition 1 returns
`-126`, then fails to parse on the last retry. Condition 2 first returns
`-126`, then its injected tail contains the previous derivation's `4860` and
the third attempt answers `4860`. Conditions 3 and 4 inject the full prior
derivation and answer `4860`.

### 2b. `R3C_hypothesis_falsification`

For C the stored status is `manual_review_required` for every attempt. The
reward is the new pre-registered composite:
`final_contains_first_n AND final_contains_counterexample_value AND
final_contains_factors_31_43`. The composite flags column is
`first_n / 1333 / 31&43`; the reward is true only if all three are true.

| Cond | Att | Status | reward | audit | mem | copy | conf | eval | done | stored | composite flags |
|---|---|---|---:|---:|---|---|---:|---|---|---|---|
| N | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| N | 2 | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| N | 3 | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 0 | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 0 | 2 | ok | false | false | false | false | 0.85 | 296 | stop | manual_review_required | F / F / F |
| 0 | 3 | ok | false | false | false | false | 0.85 | 296 | stop | manual_review_required | F / F / F |
| 1 | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 1 | 2 | ok | false | false | false | false | 0.85 | 340 | stop | manual_review_required | F / F / F |
| 1 | 3 | ok | false | false | false | false | 0.85 | 294 | stop | manual_review_required | F / F / F |
| 2 | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 2 | 2 | ok | false | false | false | false | 0.75 | 717 | stop | manual_review_required | F / F / F |
| 2 | 3 | ok | false | false | false | false | 0.95 | 878 | stop | manual_review_required | **T / F / F** |
| 3 | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 3 | 2 | ok | false | false | false | false | 0.85 | 539 | stop | manual_review_required | F / F / F |
| 3 | 3 | ok | false | false | false | false | 0.85 | 359 | stop | manual_review_required | F / F / F |
| 4 | 1 (shared) | ok | false | false | false | false | 0.85 | 479 | stop | manual_review_required | F / F / F |
| 4 | 2 | ok | false | false | false | false | 0.75 | 472 | stop | manual_review_required | F / F / F |
| 4 | 3 | ok | false | false | false | false | 0.98 | 502 | stop | manual_review_required | F / F / F |

C was answered incorrectly under every condition. The closest attempt
(condition 2, attempt 3) found `7` and `31` somewhere in a long answer but
never produced `1333` or `43`, so the composite and the stricter audit both
failed. Other attempts proposed wrong counterexamples (`n=12`, `n=??`,
`n=6` with an incorrect value) and often still expressed high confidence. No
C memory contained `1333`, so there is no COPY-POSSIBLE C pass.

### 2c. Stored status vs composite for C

| Quantity | Result |
|---|---|
| C stored `independent_check` statuses | 13/13 `manual_review_required` |
| C composite rewards | 0/13 true |
| C stricter audits | 0/13 true |
| C attempts with any composite flag true | 1 (condition 2, attempt 3: only `first_n`) |

The stored status is reported exactly as stored. It is not the reward and was
never used to promote or overwrite the composite.

---

## 3. Condition N byte-identity

| Task | Prompt SHA-256 (attempt 1 = N attempt 2 = N attempt 3) | Verdict |
|---|---|---|
| A1A | `05efcd84f82175ce801158947022c79073b4f9d8aca0ee559935333e2df44dd7` | **byte-identical** |
| C | `369363d86fc587aa81240f7cfe68b5fd470985d6cae3ec4169f1380ba6519cc2` | **byte-identical** |

Descriptive extra: the three N outputs were also byte-identical per task:
A1A 753 eval tokens each (raw length 1875 characters), C 479 eval tokens each
(raw length 1120 characters). This is consistent with deterministic local
decoding at the frozen settings; the pre-registered verdict concerns the
prompt bytes.

---

## 4. Success@3 per condition and task

`success@3` counts the shared attempt 1 plus the two retries.

| Condition | A1A success@3 | A1A audit success@3 | A1A COPY-POSSIBLE passes | C success@3 | C audit success@3 | C COPY-POSSIBLE passes |
|---|---|---|---:|---|---:|---:|
| N | false | false | 0 | false | false | 0 |
| 0 | false | false | 0 | false | false | 0 |
| 1 | false | false | 0 | false | false | 0 |
| 2 | **true** | **true** | 1 | false | false | 0 |
| 3 | **true** | **true** | 2 | false | false | 0 |
| 4 | **true** | **true** | 2 | false | false | 0 |

A1A condition 2/3/4 gains are real under the pre-registered reward, but every
one of those passes is COPY-POSSIBLE and there are zero non-copy passes. C
has no pass under any condition.

---

## 5. Pre-registered success criterion and verdict

The criterion fixed in `PREREG_MEMORY.md`:

> "Signal exists iff at least one compression level yields a C composite pass
> with audit_passed=true while condition N fails all 3 attempts."

Operational facts:

- Condition N C rewards: `[false, false, false]` - N fails all 3.
- C compression levels 1–4 with a composite pass and `audit_passed=true`: none.
- Level 0 (label-only control): no composite pass.
- Sensitivity including level 0: false.

### VERDICT: **NO SIGNAL**

The N control failed as required, but no memory condition produced a C
composite pass, with or without the stricter audit. The pilot therefore does
not establish the pre-registered memory-retry signal. This is a negative
result, not a runner failure: all 13 C calls completed, and the C attempts
were scored under the fixed rule.

A1A is outside the success criterion. Its conditions 2–4 did produce passes,
but all of them are COPY-POSSIBLE; no claim of improved reasoning is made.

---

## 6. Confidence vs correctness (free calibration data)

Unique calls only (shared attempt 1 counted once; the one failed A1A call has
no confidence and is excluded). "Correct" means `binary_reward = true`.

| Confidence bucket | Attempts | Correct | Pass rate |
|---|---:|---:|---:|
| 0.70–0.79 | 2 | 0 | 0.0% |
| 0.80–0.89 | 9 | 0 | 0.0% |
| 0.90–0.94 | 0 | 0 | — |
| 0.95–0.99 | 9 | 3 | 33.3% |
| 1.00 | 5 | 2 | 40.0% |
| **Total** | **25** | **5** | **20.0%** |

Per task:

| Task | Unique successful calls | Correct | Mean confidence |
|---|---:|---:|---:|
| A1A | 12 | 5 (all COPY-POSSIBLE) | 0.994 |
| C | 13 | 0 | 0.852 |

The model was highly confident on many incorrect answers: A1A condition 0
answered `84` at confidence 1.00; C condition 4 attempt 3 asserted a wrong
smallest counterexample (`n=6`) at confidence 0.98. Confidence is not
calibrated in this small sample, and the C task in particular produced
confident errors.

---

## 7. Failure-path instrumentation check

The single failed call is direct evidence that the Phase 1 instrumentation
works as intended:

- The model returned HTTP success with `done_reason=stop`.
- `_extract_json` failed on an unescaped control character inside a JSON
  string (`Invalid control character ... char 1573`).
- The raised `ModelOutputError` carried `raw_content` (starting with
  `{"answer": "-42", ...`), `done_reason="stop"`, `prompt_eval_count=222` and
  `eval_count=630`.
- Those values are present in the pilot results and event log.

No existing non-failure behaviour changed: the full non-live suite passed
before generation, including the new instrumentation tests.

---

## 8. Limits

- Only **2 tasks**, a **single seed**, a **single model**
  (`lfm3base:latest`), and a single machine.
- `n` is very small. The per-condition `success@3` values are descriptive,
  not population estimates.
- **No capability claim** about the model is made.
- **No weight-level adaptation claim** is made. Any change is in-context retry
  behaviour only.
- No generalisation to other tasks, models, seeds, quantizations or prompts.
- The stricter audit is rule-based, not a proof of reasoning. A
  COPY-POSSIBLE label means the answer token was available in the injected
  memory; it does not prove copying occurred, and its absence would not prove
  independent reasoning.
- The C task's stored `manual_review_required` status remains a manual-review
  question; the composite is a separate pre-registered operational criterion.
- Only one seed means the N condition's byte-identical outputs are a
  determinism observation, not an estimate of sampling variance.

---

## 9. Pilot artifact SHA-256 (data/ is git-ignored)

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `data/block15_pilot_memory.sqlite3` | 430,080 | `8d49d2746d08ff3d7c4a5f2c797a8e3cff74e3764971f6d9da81233631c7a02f` |
| `data/block15_pilot_memory_events.jsonl` | 155,588 | `57a59d883a3c9e096439407e19585a3478285b12b65a4f0bb08e9bf2b4105b21` |
| `data/block15_pilot_memory_results_20261115T174655Z.json` | 205,406 | `8de84c44f7dbf38d85e762354084600bb8d87248002bfcfd2dc00da4a98b52f6` |

The results filename does **not** match `block15_round3_results_*.json`;
`block15/round3_report.py` cannot discover it and was not executed. The 12
protected-artifact hashes in section 0d are the record-protection trail. The
SQLite store contains the two task experiments and all 26 attempt records; the
JSONL hash chain verifies with 32 events.
