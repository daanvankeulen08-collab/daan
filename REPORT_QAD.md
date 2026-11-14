# REPORT_QAD — QAD comparison execution report (Round 4)

**Status:** COMPLETED
**Executed:** 2026-11-14, 21:55–22:07 UTC
**Pre-registration:** `PREREG_QAD.md`, committed as `cddc594` ("QAD Phase 1: pre-registration, separable stores, derivation-aware R3B scorer"). This report was generated only after both arms had run; no number in it was fixed in advance except through that pre-registration.
**Upstream gate:** PASSED (quantization, renderer, parser, template source, embedding length, both manifest digests, frozen ground-truth SHA-256, clean `git status`).
**Scope:** evaluation only. No training, no dataset creation, no market data, no trading prediction.

---

## 0. Pre-run record protection (STEP 0)

### 0a. Round 3 artifact hashes recorded before any generation

| Artifact | SHA-256 (pre-run) |
|---|---|
| `data/block15_round3.sqlite3` | `EC1BFAB2E10156E4D9148ECE4703153DD5D8CA7F6A12C1C71A76E093343AF542` |
| `data/block15_round3_events.jsonl` | `D923E8C0A45674A98DC16F5AD47AA4F372F69D633C4D2FAF4B674E5374D7136E` |
| `data/block15_round3_ground_truth.json` | `4239F09C454D5D7ACFC544600F5B28C073D03A69E512FFCF663837EA0C7F45CD` |
| `data/block15_round3_assessments.json` | `75D711633F94743420BE1F7BDC071E34843E18B89623688C6ABD7E2AC6BE4511` |
| `data/block15_round3_results_round3_20261111T143825Z.json` | `8EBB5899304602BE17C945CB7769378CFF8FA5A7776956EC332F0730DF7CF87E` |
| `BLOCK15_ROUND3_REPORT.md` | `283EB0C07163FCF0889B8435480E9B3ABB0CDF4D392DF78DAF127F01C4CDD382` |

### 0b. `block15/round3_report.py` inspection (read only, never executed)

`round3_report.py` discovers results files **by glob**: line 18
`sorted(glob.glob(str(DATA_DIR / pattern)))[-1]`, called at line 193 with
`pattern = "block15_round3_results_*.json"`. It sorts the matches and takes the
**last** one. **A new `block15_round3_results_*.json` file with a later
timestamp would be picked up by it.** This is why every Round 4 results file
was renamed immediately after its run to `block15_round4_arm_*_results_*.json`,
which does not match that glob pattern. The renamed files are the audit trail;
the old Round 3 result file remains the only match of the pattern.
`round3_report.py` was not executed at any point in this task.

### 0c. Arm-A alias (verification result)

Alias `lfm3base:latest` created from `lfm3:latest` (single authorized alias).
Note on method: the prescribed temp Modelfile could not be written outside the
repository (the harness denies writes outside the working directory), so a
repo-local temp Modelfile was used and deleted immediately; `ollama create`
re-serialized the manifest and produced a different digest (`36fe936662c9`),
so the alias was replaced with `ollama cp lfm3:latest lfm3base:latest`, which
preserves the digest. The weight blob, config digest and params digest are
identical to `lfm3:latest` in both cases.

Verified before generation:

- `ollama show lfm3base:latest` → quantization **Q4_K_M**, renderer `lfm3`,
  parser `lfm3`, template source `renderer_parser`, embedding 2048, context
  262144 — identical to `lfm3:latest`.
- Digest: **`b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`**
  — matches the expected manifest digest. (No abort condition.)

---

## 1. Execution summary

| Item | Arm A | Arm B |
|---|---|---|
| Alias/tag used (`MDL_MODEL`) | `lfm3base:latest` | `lfm3qad:latest` |
| Recorded `model_digest` | `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d` | `765f7bd04f18c4774e31755fde29fc72c2f63686b9f6a935c411334f2b0e3ad4` |
| Digest assertion | **PASS** (expected `b36a103fe2f8fbe9…`) | **PASS** (expected `765f7bd04f18c477…`) |
| run_id (recorded) | `round3_20261114T215552Z` | `round3_20261114T220133Z` |
| Store (SQLite) | `data/block15_round4_arm_a.sqlite3` | `data/block15_round4_arm_b.sqlite3` |
| Store (JSONL) | `data/block15_round4_arm_a_events.jsonl` | `data/block15_round4_arm_b_events.jsonl` |
| Results file (renamed) | `data/block15_round4_arm_a_results_round3_20261114T215552Z.json` | `data/block15_round4_arm_b_results_round3_20261114T220133Z.json` |
| Results SHA-256 | `d6f39e7dde69561c9ab00a0404c815a3d03ded94c9b86c581c793dfd3aa734d8` | `6d24f3b2e412ae0e2b805c9888da3518bb219e6c5a00ea84ee1acfe2e1950f6d` |
| Runtime | 300.16 s | 311.44 s |
| Model calls | 14 | 13 |
| Completed / failed | 12 / 0 | 10 / 2 |
| Prompt / eval tokens | 3589 / 4184 | 2992 / 2926 |
| `done_reason=length` events | 0 | 0 |
| Free MB start / min / end | 3542.7 / 2384.7 / 2533.4 | 3750.9 / 2592.1 / 2594.8 |
| Stopped early | no | no |

Settings recorded per run (identical to Round 3 and to the pre-registration):
`think=false, num_ctx=8192, temperature=0.1, top_p=1.0, repeat_penalty=1.1,
seed=42, keep_alive=10m, num_predict_decision=300, num_predict_final=1200,
single_flight=true, sequential=true`. Same 12 tasks in the same `RUN_ORDER`,
same stop rules (16 calls / 420 s / 360 s / 390 s / 450 MB). Arm order was A
then B; arm A is a fresh re-run, not reused Round 3 numbers.

**Execution deviations from the pre-registration, reported explicitly:**
arm B did **not** meet the pre-registered 12/12 success criterion: 10/12
completed. Two tasks failed with `ModelOutputError: model response is not
valid JSON: Unterminated string …` (char 35 and char 52 respectively) — the
model emitted truncated JSON and the existing runner recorded the failure
without a retry or recovery run. Both are model-output failures
(`incomplete=false`), not runner errors. No fix, re-run, or adjustment was
performed, per the pre-registration.

---

## 2. Per-task results, both arms side by side

Status / latency / eval tokens / `done_reason` / answer-derivation consistency
(stored automated value; blank where the check registers no such field).

| Task | A: status | A: lat | A: eval | A: done_reason | A: A/D consistency | B: status | B: lat | B: eval | B: done_reason | B: A/D consistency |
|---|---|---|---:|---|---|---|---:|---|---|---|
| `R3A1_coefficient_protocol_A` | completed | 52.8s | 753 | stop | `derivation_only` | **failed** | 74.4s | 0 | n/a | n/a |
| `R3A1_coefficient_protocol_B` | completed | 13.9s | 193 | stop | `consistent` | completed | 16.8s | 235 | stop | `consistent` |
| `R3A2_divisibility_protocol_A` | completed | 20.6s | 315 | stop | n/a | completed | 15.6s | 225 | stop | n/a |
| `R3A2_divisibility_protocol_B` | completed | 13.6s | 187 | stop | n/a | completed | 16.1s | 225 | stop | n/a |
| `R3B_counterexample_minimality` | completed | 14.4s | 193 | stop | n/a | completed | 23.7s | 345 | stop | n/a |
| `R3C_hypothesis_falsification` | completed | 33.5s | 479 | stop | n/a | completed | 41.4s | 629 | stop | n/a |
| `R3D1_tool_voluntary` | completed | 48.6s | 741 | stop, stop | `consistent` | **failed** | 19.9s | 0 | n/a | n/a |
| `R3D2_tool_required` | completed | 24.1s | 196 | stop, stop | `consistent` | completed | 29.0s | 228 | stop, stop | `consistent` |
| `R3E1_uncertainty_determinate` | completed | 13.0s | 177 | stop | n/a | completed | 14.6s | 197 | stop | n/a |
| `R3E2_uncertainty_underdetermined` | completed | 14.1s | 191 | stop | n/a | completed | 13.8s | 175 | stop | n/a |
| `R3F_numerical_trend_noise` | completed | 37.4s | 566 | stop | n/a | completed | 29.1s | 432 | stop | n/a |
| `R3A1_coefficient_protocol_B_repeat` | completed | 13.9s | 193 | stop | `consistent` | completed | 16.6s | 235 | stop | `consistent` |

Stored automated check statuses: A1A — A `objective_fail` (final answer `-21`
while the derivation reaches 4860, the same contradiction observed in Round 3);
A1B, D1, D2, G(repeat) — `objective_pass` in both arms; A2A/A2B, C, E1, E2,
F — `manual_review_required` in both arms. Tool records: D2 in both arms
requested `(2*x + 3)**7`, the orchestrator executed it and the existing
verifier passed (difference 0). Arm A's D1 declined the tool
(`use_tool=false`, expression field `(3*x - 2)**12`, `not_used`) and still
answered correctly; arm B's D1 failed before any tool decision was recorded.

## 3. R3B — strict and combined (both readings, both arms)

Scored with `block15.round4_scoring.r3b_derivation_aware` applied to the stored
`final_answer` object of each arm. The strict reading is the Round 3 rule
(final_answer-only); the combined reading adds the derivation text. The strict
result is never overwritten.

| Arm | strict_status | combined_status |
|---|---|---|
| A (`lfm3base:latest`) | `objective_fail` | `objective_partial` |
| B (`lfm3qad:latest`) | `objective_fail` | `objective_partial` |

Strict flags (final answer only; final answer is `4` in both arms):

| Flag | A | B |
|---|---|---|
| `final_contains_first_n` (4) | true | true |
| `final_contains_counterexample_value` (121) | false | false |
| `final_contains_factorization` | false | false |
| `derivation_contains_first_n` (4) | true | true |
| `mentions_all_preceding_values` | true | true |
| `mentions_minimality_language` | true | true |

Combined flags (final answer + derivation):

| Flag | A | B |
|---|---|---|
| `final_contains_first_n` (4) | true | true |
| `final_contains_counterexample_value` (121) | true | true |
| `final_contains_factorization` | true | true |
| `derivation_contains_first_n` (4) | true | true |
| `mentions_all_preceding_values` | true | true |
| `mentions_minimality_language` | true | true |

Both arms produced `final_answer="4"` (confidence 1.0) and derivations that
check f(0)=101, f(1)=103, f(2)=107, f(3)=113, then f(4)=121. Arm A's
derivation step 5 contains `121=11*11`; arm B's derivation step 6 contains
`121=11×11` (U+00D7 multiplication sign), so its combined factorization hit
comes from the `11` + `=` fallback rather than a literal `11*11` match (see
the instrument limitation in section 8). The stored automated strict status is
the Round 3 value `objective_fail` for both arms and is unchanged.

## 4. C and F keyword flags — `manual_review_required`, never auto-promoted

Both tasks remain `manual_review_required` in both arms. The keyword hits are
reported as stored; no flag was promoted to pass or fail.

**`R3C_hypothesis_falsification`**

| Flag | A | B |
|---|---|---|
| `final_contains_first_n` (7) | false | false |
| `final_contains_counterexample_value` (1333) | false | false |
| `final_contains_factors_31_43` | false | false |
| `mentions_all_preceding_values` | false | false |
| `denies_universal_prime_claim` | false | **true** |
| `mentions_minimality_language` | false | **true** |

**`R3F_numerical_trend_noise`**

| Flag | A | B |
|---|---|---|
| `trend_upward` | true | true |
| `mentions_fluctuations` | true | true |
| `denies_exact_deterministic_rule` | false | false |
| `mentions_continuation_caution` | false | false |
| `mentions_more_observations` | true | false |

As in Round 3, these conservative keyword checks are not ground truth; arm A
hit fewer C flags than arm B, and the flags do not establish task success or
failure by themselves.

## 5. Repeat-task byte-identity within each arm

`R3A1_coefficient_protocol_B` versus `R3A1_coefficient_protocol_B_repeat`:

| Arm | raw_content | parsed | messages | schema | done_reason | prompt/eval tokens | Verdict |
|---|---|---|---|---|---|---|---|
| A | identical | identical | identical | identical | identical | identical | **byte-identical** |
| B | identical | identical | identical | identical | identical | identical | **byte-identical** |

Latency differs in both arms, as expected: A 13783.41 ms vs 13780.98 ms;
B 16670.25 ms vs 16484.35 ms. One repeat per arm, single seed — content
determinism observed for this compact task only.

## 6. Truncation and schema caps, named

- `done_reason=length`: **0 in both arms**; every recorded call ended with
  `done_reason=stop`.
- 500-character per-step derivation cap, arms:
  - A: `R3C_hypothesis_falsification` step 4 (exactly 500) and
    `R3D1_tool_voluntary` step 8 (exactly 500) — the same two cap contacts
    observed in Round 3.
  - B: none.
- 8-item derivation array maximum:
  - A: `R3A1_coefficient_protocol_B`, `R3D1_tool_voluntary`,
    `R3F_numerical_trend_noise`, `R3A1_coefficient_protocol_B_repeat` at 8
    items.
  - B: none (maximum 7 items).
- Arm B's two failures produced invalid truncated JSON (unterminated string),
  a model-output failure rather than a token-level `done_reason=length`
  truncation of a recorded call; the failing raws are retained in the stored
  error message and store.

## 7. No-contamination verification (STEP 3)

All six Round 3 artifacts re-hashed after both runs:

| Artifact | Pre-run | Post-run | Result |
|---|---|---|---|
| `data/block15_round3.sqlite3` | `EC1BFAB2…43AF542` | identical | **unchanged** |
| `data/block15_round3_events.jsonl` | `D923E8C0…4D7136E` | identical | **unchanged** |
| `data/block15_round3_ground_truth.json` | `4239F09C…0C7F45CD` | identical | **unchanged** |
| `data/block15_round3_assessments.json` | `75D71163…6BE4511` | identical | **unchanged** |
| `data/block15_round3_results_round3_20261111T143825Z.json` | `8EBB5899…7CF87E` | identical | **unchanged** |
| `BLOCK15_ROUND3_REPORT.md` | `283EB0C0…CDD382` | identical | **unchanged** |

**ALL ROUND 3 ARTIFACTS UNCHANGED: true.** No Round 3 artifact was written,
moved or deleted. The produced Round 4 results files were renamed (not copied),
so `block15_round3_results_*.json` still matches exactly one file — the
original Round 3 result. `round3_report.py` was never executed.

## 8. Confound statement, instrument limitation and provenance caveat

**PROVENANCE CAVEAT.** The runner hard-codes the `run_id` prefix `round3_`
(`run_id = "round3_" + timestamp`) and `record["round"] = 3`. Round 4 arm
identity is therefore established by four independent artifacts, not by the
run id: the alias tag actually used (`lfm3base:latest` / `lfm3qad:latest`),
the recorded `model_digest` (asserted equal to the pre-registered manifest
digests), the store filenames (`block15_round4_arm_a/b.sqlite3` and
`…_events.jsonl`), and the renamed results files
(`block15_round4_arm_a/b_results_<run_id>.json`).

**INSTRUMENT LIMITATION.** The R3B factorization check accepts the presence of
`11` together with a `=` sign in the scanned text, in both the strict and
combined readings. This is inherited from Round 3 deliberately, for
comparability with the stored Round 3 flags, and it is why arm B's combined
factorization hit (derivation `121=11×11`, U+00D7) still passes. The check is
a conservative objective screen, not a proof that the factorization was
rendered correctly.

**CONFOUND STATEMENT, restated verbatim from `PREREG_QAD.md` section 3:**

> Arm B is a QAD-distilled weight set, not arm A requantized. This experiment
> compares two released 4-bit artifacts. It CANNOT isolate whether QAD
> recovers quantization loss, because neither a plain Q4_0 build nor a
> high-precision reference is included. Any observed difference between the
> arms is a difference between two released artifacts that differ in both
> quantization scheme and weight provenance; it must not be attributed to
> quantization alone.

**LIMITS.** Single seed (42), n = 12 tasks, one run per arm, one repeat per
arm. This report makes no aggregate capability ranking and makes no claim
that QAD recovers quantization loss. Per-task values are reported for both
arms; differences are observations, not causal attributions. Arm B's 10/12
completion (two invalid-JSON task failures) is a property of this run and is
recorded, not smoothed over.

## 9. Audit trail

- Results JSONs live in gitignored `data/` and cannot be committed; their
  SHA-256 digests (section 1) plus this report are the audit trail.
- Stores (`data/block15_round4_arm_a.sqlite3`, `…_arm_a_events.jsonl`,
  `…_arm_b.sqlite3`, `…_arm_b_events.jsonl`) are likewise gitignored and
  remain on disk unmodified by this commit.
- One local Ollama alias was created and retained, as authorized:
  `lfm3base:latest` (digest `b36a103fe2f8…`, identical weights to
  `lfm3:latest`).
- No dependency, model download, `mdl/`, `qresearch/`, `qbacktest/`,
  `block15/` source, or Round 3 artifact was changed. `PREREG_QAD.md`,
  `block15/round3.py`, `block15/round4_scoring.py` are unchanged since
  `cddc594`.