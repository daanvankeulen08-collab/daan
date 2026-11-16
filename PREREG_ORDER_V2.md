# Pre-registration — Order V2: `final_answer` before versus after the `derivation` array

**Status: pre-registered before any generation. No model calls had been made in this block when this file was created.**

This document fixes the claim, arms, task set, endpoint, gates, analysis and budget for the
order-v2 study. Generation happens only after this file is committed. The harness is
`block15/order_v2_research.py`; results are written only to new `data/block15_order_v2_*`
artifacts. `block15/round3_report.py` is never executed.

---

## 0. Scope and code changes made before registration

Two additive fixes were applied before this pre-registration (STEP 1 of the task):

1. **`validate_v2` annotation-keyword exemption.** The guard now accepts the six
   annotation-only keywords `title`, `description`, `$schema`, `$comment`, `default`,
   `examples` at any schema depth, because they cannot change a validation outcome.
   It still raises `ValueError` on unimplemented *assertion* keywords (`pattern`,
   `enum`, `$ref`, `exclusiveMinimum`, `anyOf`, `format`, ...). Tests cover both
   behaviours. This study's two schemas contain no annotation keywords, so the change
   does not affect either arm's validation.
2. **FROZEN/LIVE protected-manifest split.** The protected manifest is split into
   FROZEN (pre-existing protected artifacts) and LIVE (code that this block may
   change). FROZEN must be byte-identical before and after the run; LIVE is reported
   with explicit before/after hashes and is never claimed "all unchanged".

---

## 1. Claim (narrow label)

> **The effect of placing `final_answer` before versus after the `derivation` array,
> holding schema shape, system prompt, instruction text, sampling and budget constant.**

This is a positional-ordering claim only. It is not a capability claim, not a
generalisation claim, and not a claim about why the model behaves as it does.

---

## 2. Arms and constants

| Quantity | Value |
|---|---|
| Arms | `ANSWER_FIRST_V2` vs `DERIVATION_FIRST_V2` |
| `answer_first` required order | `final_answer, derivation, uncertainty, confidence` |
| `derivation_first` required order | `derivation, final_answer, uncertainty, confidence` |
| Schema shape | Identical in both arms: object, `additionalProperties=false`, same four property rules; only insertion order of `required`/`properties` differs |
| Shared instruction | `OUTPUT_INSTRUCTION_V2` (contract v2 neutral constant, alphabetical field listing, no ordering language) |
| Added sentence (one, identical in both arms) | `Emit the fields in the order required by the schema, not in the order they are listed here.` |
| Effective instruction SHA-256 | `b262289dc20b5fe03c9ec5c6512630676c926ac39c3f572a99fd2d392d740980` |
| System prompt | `SYSTEM_PROMPT_V2` (Round 3's verbatim, unchanged) |
| System prompt SHA-256 | `ee09cc7bc5a939cb6638e5d33c9505e7e9b20f327274f2360be2a7e4e9152710` |
| `ANSWER_FIRST_V2` SHA-256 | `e9c52676497c7cbd5a882aecdc23f602e1e432e3641155bd069d5b220267dbd1` |
| `DERIVATION_FIRST_V2` SHA-256 | `7ca06e0060d04bd42c13ec7bf232404217acb0963f10f2af467cabe17ab7ef53` |

The neutral instruction is unchanged from the previous block; the experiment adds
exactly one sentence (no other words). The added sentence is constant across arms and
does not itself name a field order — it directs the model to the schema, which is the
manipulated variable.

### Sampling (identical in both arms)

`num_predict=1200`, `think=False`, `num_ctx=8192`, `temperature=0.1`, `top_p=1.0`,
`repeat_penalty=1.1`, `seed=42`, `keep_alive=10m`.

The client sends the arm's schema as the `format` dict, with the normal one-shot
fallbacks (`json_fallback`, `json_without_think`) only on HTTP rejection. The accepted
payload variant is recorded per cell as `protocol_variant` / `schema_enforced`, so a
fallback is visible rather than hidden. No retry, repair, teacher hint, memory
injection, training, dependency change, network model API or model download occurs.

---

## 3. Tasks — 30 new bounded-math tasks

15 coefficient-extraction tasks (`V2C01`–`V2C15`) and 15 bounded-minimality tasks
(`V2M01`–`V2M15`). All are independent of Round 3 (A1–F2, R3A1–R3G), H1–H5 and
C01–C12 / M01–M08: different expressions, different polynomial coefficients, different question
text (verified by `tests/test_order_v2_research.py::test_tasks_independent_of_round3_h1_h5_and_c01_m08`).

* Ground truth is computed by SymPy at run time from each task's stored parameters
  and checked against the frozen expected value; a mismatch aborts the run.
* Minimality tasks are squarefree first composites with exactly two prime factors,
  searched over `n = 0..200`, and independently re-verified by SymPy factorisation.
* Ground-truth manifest SHA-256: `b0c4d70424d6a678ca840c43bae66afee3116d2637e94ff072abc041743c95f0`.
* Every prompt is SHA-256 hashed and frozen in the harness (`FROZEN_PROMPT_SHA256`).
* **Copy guard:** before any call, the harness asserts that no ground-truth integer
  token appears in any prompt. All 30 tasks pass (verified again offline in tests).
  A failure aborts the run.

The full frozen task table (id, kind, question, prompt hash, expected display,
parameters and SymPy ground truth) is printed by
`python -m block15.order_v2_research --manifest`.

---

## 4. Primary endpoint

**Count of tasks whose `final_answer` is numerically correct under independent SymPy
audit, non-copy.**

* Coefficient tasks: the exact SymPy coefficient must be *present* among the integers
  extracted from `final_answer` (presence, not exact set equality — recorded alongside
  a stricter `strict_single_int` diagnostic).
* Minimality tasks: `n` AND the composite value `f(n)` AND both prime factors must all
  be present in `final_answer`, and SymPy must independently verify the factorisation.
* A cell is counted only if `copy_possible` is false for its task (all are false by
  construction).
* **Confidence-range violations do not disqualify the primary endpoint.** The audit
  reads `final_answer` only; raw confidence is persisted but never used to filter the
  primary count. Contract compliance is reported separately.

---

## 5. Per-cell persisted fields

For every (task, arm) cell the runner persists:

* `emitted_key_order` — from a **fresh parse of `raw_content`**, never re-serialized;
* `matches_own_schema`, `matches_other_schema` — order-only comparison against each
  arm's required order;
* `validate_v2_ok`, `validate_v2_violations`;
* `protocol_variant`, `schema_enforced`, `think_sent`;
* `done_reason`, `prompt_eval_count`, `eval_count`;
* `confidence_raw` (raw value, unclamped);
* `copy_possible` (and token detail);
* `latency_ms`;
* `answer_text`, `audit`, `audit_passed`, `primary_correct`;
* `status`, `error`, `failure_mode`, `failure_flags`, `truncation_invalid`;
* `raw_content` and its SHA-256, prompt/schema hashes, task id/kind, arm, call index.

The fresh parse is independent of the client's parse: it re-parses `raw_content`
from scratch and preserves the wire key order.

---

## 6. Validity gates — failing a gate makes the run INVALID, not null

* **G1 manipulation:** among parseable cells, `>=90%` `matches_own_schema` in **each**
  arm AND `<=10%` `matches_other_schema` in each arm. Otherwise
  **INVALID MANIPULATION**.
* **G2 length:** `<=20%` truncation-invalid cells per arm, where a cell is
  truncation-invalid iff `done_reason == "length"` and it is unparseable or fails
  `validate_v2`. Otherwise **LENGTH-CONFOUNDED** and the comparison may not be
  attributed to ordering.

Both verdicts are stated first in the report with the actual percentages.

---

## 7. Success criterion and analysis

`derivation_first` primary count **>** `answer_first` primary count
**AND** total failures across *all* modes not higher in `derivation_first`
**AND** G1 and G2 both pass.

* "Total failures across all modes" is the sum of all per-cell multi-label failure
  flags (`call_error`, `parse_failed`, `schema_violation`, `truncated`, `primary_wrong`,
  `confidence_out_of_range`, `copy_possible`) over the arm — guarding the **total**,
  not any single failure mode. The mutually exclusive failure-mode partition and its
  total are also reported.
* McNemar two-sided exact p on the paired primary-correctness counts (30 pairs);
  significance is claimed only at `p<0.05`.
* Risk difference `(derivation - answer)/30`, with a paired bootstrap 95% interval.
* Contract-compliance rate (`validate_v2_ok` share) reported separately from the
  primary endpoint.
* If a run stops early on a guard, completeness is false and the success criterion
  cannot be met.

### What a pass does not prove

It does not prove general capability, generalisation beyond this one positional swap,
server-side enforcement internals, or model understanding. It is one seed (`42`), one
task set (`n=30`), one positional swap, and one local model quantisation.

---

## 8. Budget and execution

* **Max 70 model calls, max 5400 s, min free physical 450 MB**, enforced cumulatively
  inside the single run process before every call.
* Rationale: Round 3 measured `22.9 s/call`; the ceiling study measured `76.7 s/call`.
  The 60 planned calls span roughly `1375–4602 s`, inside 5400 s with headroom.
* Both arms run **sequentially, single-flight**, arm order `answer_first` then
  `derivation_first`, one call per task per arm, 60 calls total. The client's
  process-wide lock serialises generations.
* **New stores only:** `data/block15_order_v2.sqlite3`,
  `data/block15_order_v2_events.jsonl`.
* Result files: `data/block15_order_v2_results_<arm>_<timestamp>.json` — the filename
  does **not** match `block15_round3_results_*`.
* The run refuses to start if any order-v2 result file already exists (no reruns),
  if FROZEN verification fails, if the copy guard fails, or if the model digest /
  quantisation does not match `lfm3base:latest` / `Q4_K_M` /
  `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`.

---

## 9. FROZEN / LIVE protected manifest

* **FROZEN** (118 paths, manifest SHA-256 `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`):
  pre-existing `data/*`, `BLOCK15_*.md`, `PREREG_*.md`, `REPORT_*.md`, `README_*.md`,
  `block15/ceiling_research.py`, `block15/heldout_research.py`, `block15/round*.py`,
  `block15/memory_pilot.py`, `block15/tasks.py`, `block15/run_benchmark.py`,
  `qresearch/`, `qbacktest/`, `pyproject.toml`, `uv.lock`, `.python-version`.
  New this-block artifacts (`PREREG_ORDER_V2.md`, `REPORT_ORDER_V2.md`,
  `data/block15_order_v2_*`) and Python caches are excluded by rule and reported
  separately. FROZEN must be byte-identical before and after the run.
* **LIVE** (41 paths): `mdl/`, `block15/contract_v2.py`, new `block15/*_research.py`
  modules, `tests/`. LIVE changes are reported with explicit before/after hashes. The
  before hashes are taken from commit `6c788a5` (the GATE commit); new files have no
  before hash and are reported as new. **No claim of "all unchanged" is made for LIVE.**

---

## 10. Artifact names

| Artifact | Path |
|---|---|
| Harness | `block15/order_v2_research.py` |
| Pre-registration | `PREREG_ORDER_V2.md` |
| Report (after run) | `REPORT_ORDER_V2.md` |
| Stores | `data/block15_order_v2.sqlite3`, `data/block15_order_v2_events.jsonl` |
| Per-arm results | `data/block15_order_v2_results_<arm>_<timestamp>.json` |
| Summary | `data/block15_order_v2_summary.json` |
