# PREREG_QAD — Pre-registration of the QAD comparison (Round 4)

**Status:** FIXED BEFORE ANY GENERATION
**Fixed on:** 2026-11-14, before the first Round 4 model call and before any
result, assessment or report file for Round 4 existed.
**Working directory:** `C:\Users\famva\Downloads\daan\daan`
**Upstream gate:** PASSED (quantization, renderer, parser, template source,
embedding length and both manifest digests verified; frozen ground-truth
SHA-256 verified; `git status --porcelain` empty at gate time).

This document is a commitment. It is written before any Round 4 generation.
Nothing in the run may deviate from it without a new, separately committed
pre-registration version.

---

## 1. Arms

### Arm A — `lfm3:latest` (baseline, RE-RUN)

| Field | Value |
|---|---|
| Tag | `lfm3:latest` |
| Quantization | Q4_K_M |
| Manifest sha256 | `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d` |
| GGUF `file_type` | 15 |
| Finetune tag | none (`general.finetune` absent) |
| Tensor pattern | mixed Q4_K / Q6_K (token embedding and selected `ffn_down` / `attn_v` tensors Q6_K, remaining block weights Q4_K, norm weights F32) |
| Model layer size | 1,099,627,808 B |

### Arm B — `lfm3qad:latest` (QAD)

| Field | Value |
|---|---|
| Tag | `lfm3qad:latest` (alias of `lfm3:1.7b-qad-q4_0`; identical manifest digest) |
| Quantization | Q4_0 |
| Manifest sha256 | `765f7bd04f18c4774e31755fde29fc72c2f63686b9f6a935c411334f2b0e3ad4` |
| GGUF `file_type` | 2 |
| Finetune tag | `general.finetune = QAD` |
| Tensor pattern | uniform Q4_0 block tensors with Q6_K `token_embd` (norm weights F32) |
| Model layer size | 1,049,615,680 B |

## 2. Verified IDENTICAL between the arms

- renderer: `lfm3`
- parser: `lfm3`
- template source: `renderer_parser`
- embedding length: `2048`
- context length: `262144`
- parameter_count: `1.7288016e+09`
- top_p: `1`
- top_k: `50`
- temperature: `0.1`
- repeat_penalty: `1.1`
- architecture `lfm3`, block count 24, requires Ollama `0.40.13`

The only intended difference between the arms is the weight artifact itself
(Q4_K_M baseline vs QAD-distilled Q4_0).

## 3. Confound statement (limitation — read before interpreting any result)

**Arm B is a QAD-distilled weight set, not arm A requantized.** This experiment
compares two released 4-bit artifacts. It CANNOT isolate whether QAD recovers
quantization loss, because neither a plain Q4_0 build nor a high-precision
reference is included. Any observed difference between the arms is a difference
between two released artifacts that differ in both quantization scheme and
weight provenance; it must not be attributed to quantization alone.

## 4. Execution knobs (identical to Round 3)

- `think = False`
- `num_ctx = 8192`
- `temperature = 0.1`
- `top_p = 1.0`
- `repeat_penalty = 1.1`
- `seed = 42`
- `keep_alive = 10m`
- `num_predict`: 300 (decision calls) / 1200 (final-answer calls)

## 5. Task set, order and stop rules

- Same 12 tasks as Round 3, same frozen `RUN_ORDER` from
  `block15/round3_tasks.py`.
- Same stop rules: 16 calls total / 420 s hard runtime / 360 s task-start
  cutoff / 390 s call-start cutoff / 450 MB minimum free physical memory.
- Sequential, single-flight execution (one call at a time, one task at a
  time).
- Arm order: A then B.
- **Arm A is a RE-RUN. Round 3 numbers are NOT reused.** Arm A results come
  only from a fresh run in this comparison; the Round 3 report is used solely
  as design provenance.

## 6. Success criteria

- 12/12 tasks completed per arm.
- JSON validity recorded per call.
- `done_reason = length` count recorded per arm.
- Per-task latency and eval token counts recorded.
- Objective pass/fail against the frozen SymPy facts
  (`block15.round3.independent_check`, unmodified).
- Repeat task (`R3A1_coefficient_protocol_B_repeat`) byte-identical within its
  arm.

## 7. Reporting rules

- Per-task deltas only; both arms shown; single seed; n = 12.
- NO aggregate capability ranking.
- NO claim that QAD recovers quantization loss (see section 3).
- **R3B (`R3B_counterexample_minimality`):** report BOTH the strict status
  (`final_answer`-only, Round 3 comparable, as stored by
  `block15.round3.independent_check`) AND the combined status
  (`final_answer` + derivation, computed by `block15.round4_scoring`). The
  strict result is never overwritten by the combined reading.
- C and F keyword flags (`R3C_hypothesis_falsification`,
  `R3F_numerical_trend_noise`) stay `manual_review_required`; they are never
  auto-promoted to pass or fail.

## 8. Stores

Round 4 runs use separable stores, resolved in `block15/round3.py` by
`_round3_store_paths()`:

- Defaults (both environment variables unset), byte-identical to the previous
  hard-coded Round 3 behaviour: `data/block15_round3.sqlite3` and
  `data/block15_round3_events.jsonl`.
- `BLOCK15_DB_PATH` / `BLOCK15_JSONL_PATH` override the store file per arm
  (relative names stay under `data/`, absolute paths are honoured), so arm A
  and arm B write to separate SQLite and JSONL stores.
- The frozen ground truth `data/block15_round3_ground_truth.json`
  (SHA-256 `4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd`)
  is read-only input and is never regenerated.

No Round 3 or Round 4 store, result, assessment or report file was written by
this pre-registration commit.