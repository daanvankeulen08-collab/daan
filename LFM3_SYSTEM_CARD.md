# LFM3 system card — lfm3base:latest

Read-only synthesis. Source of model facts: `ollama show lfm3base:latest --verbose` and
`--modelfile` (no generation, no network model API), plus committed reports. Each item
is marked CONFIRMED (observed directly), INFERRED (reasoned from observed fields), or
UNKNOWN (not available). GGUF structured metadata beyond what `ollama show` prints was
not parsed; absent fields are UNKNOWN, not filled by assumption.

## Identity
- **CONFIRMED** architecture `lfm3`; params `1.7B` (`general.parameter_count` 1.7288016e9);
  context length 262144; embedding length 2048; quantization `Q4_K_M`; file_type 15;
  `requires 0.40.13`.
- **CONFIRMED** renderer `lfm3`, parser `lfm3`, template source `renderer_parser`;
  Modelfile `TEMPLATE {{ .Prompt }}`, `RENDERER lfm3`, `PARSER lfm3`.
- **CONFIRMED** capabilities: completion, tools, thinking (levels true/false, default
  true). Capabilities are registered; the local harness sent `think=False` explicitly
  in every study.
- **CONFIRMED** baked sampling defaults (Modelfile + Metadata): temperature 0.1,
  top_k 50, top_p 1, repeat_penalty 1.1, repeat_last_n -1. Base model
  `LFM3 1.7B Base` (LiquidAI), repo `LiquidAI/LFM3-1.7B-Base`, license `lfm1.0`
  (LFM Open License v1.0).
- **UNKNOWN** whether system prompt is baked into weights (Modelfile carries no SYSTEM
  line; all study system prompts were supplied externally).

## Hybrid block map
- **CONFIRMED** `block_count` 24; `attention.head_count` 16; `head_count_kv =
  [0 0 4 …]` (per-block list, truncated in `ollama show` display); `key_length` 128;
  `value_length` 128; `rope.dimension_count` 128; `feed_forward_length` 7680.
- **CONFIRMED** `shortconv.l_cache` 7; blocks 0,1,3,5,… expose `shortconv.conv/in_proj/
  out_proj` weights with `conv` shape `[7,2048]`; blocks 2,4,… expose `attn_gate/k/q/v`
  weights (`attn_k` `[2048,512]` = 4 kv heads × 128).
- **CONFIRMED** `attention.sliding_window` 256; `sliding_window_pattern = [false,…]`
  (per-block, truncated in display); rope bases `freq_base` 1e6 and `freq_base_swa`
  10000.
- **INFERRED** the architecture interleaves short-convolution blocks and attention
  blocks (weight namespaces alternate by block index in the observed tensor list).
- **UNKNOWN** the exact per-block SWA/global split (full `head_count_kv` and
  `sliding_window_pattern` arrays are elided by `ollama show` with "+21/+23 more").
  No SWA/global assignment is asserted.

## Quantization
- **CONFIRMED** `lfm3base:latest` = Q4_K_M mixed tensor map: `token_embd.weight` Q6_K
  `[2048,128000]`; `ffn_down` and `attn_v` Q6_K; `ffn_gate/up`, `attn_q/k`,
  `shortconv.in_proj/out_proj` Q4_K; `*_norm`, `rope_freqs`, `shortconv.conv` F32.
  `ollama list` size 1.1 GB; blob ≈1.1 GB. Digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`.
- **CONFIRMED** `lfm3qad:latest` = Q4_0 with `general.finetune = QAD`: shortconv in/out
  proj and other linears Q4_0, `token_embd.weight` still Q6_K `[2048,128000]`;
  `ollama list` size 1.0 GB, digest `765f7bd04f18…` (alias `lfm3:1.7b-qad-q4_0`).
- **CONFIRMED** confound statement in `REPORT_QAD.md` §8: arm B is a QAD-distilled
  weight set, not arm A requantized; the comparison cannot isolate whether QAD
  recovers quantization loss. All capability findings used `lfm3base:latest` only.
- **UNKNOWN** exact per-tensor byte totals (not computed).

## Runtime envelope
- **CONFIRMED** (reports) all studies single local Ollama; `protocol_variant=primary`,
  `schema_enforced=True`, `think_sent=False` on essentially all cells (e.g.
  `REPORT_ORDER_V2.md`, `REPORT_DIAGNOSIS.md`).
- **CONFIRMED** truncation occurs at `done_reason=length` (e.g. ORDER_V2 1/30; ceiling
  study truncated cells — `REPORT_CEILING.md`). More num_predict fixed JSON validity but
  not answer commitment (`REPORT_RESEARCH.md` §6, 2400-token arm DIES).
- **CONFIRMED** schema-enforcement caveat (`REPORT_ORDER_V2.md` objection d):
  `schema_enforced=True` means the primary HTTP variant carried the schema dict, not
  that llama.cpp enforced every keyword; format-variant provenance is the client's
  primary→json fallback chain (`mdl/ollama_client.py`), not verified server internals.
- **CONFIRMED** memory floors held: e.g. ORDER_V2 min free 1750.3 MB, diagnosis
  2153.6 MB, memory study 1703.3 MB — all above the 450 MB floor.
- **UNKNOWN** measured tokens/s (no single committed tok/s figure; per-study latencies
  and eval tokens exist but a rate is not asserted).

## Operational modes

| Mode | Evidence (committed) | Use when | Avoid when | Set by |
|---|---|---|---|---|
| derivation-first array contract (`DERIVATION_FIRST_V2`) | ORDER_V2 18/30 vs 0/30 answer-first | Need auditable multi-step answers | Token budget too small (truncation) | Controller (schema order) |
| answer-first (`ANSWER_FIRST_V2`) | ORDER_V2 0/30 primary | Contract-compliance checks only | Any accuracy goal | Controller |
| answer-before-reasoning (Round 3 native) | `REPORT_RESEARCH.md` forced-commitment mechanism | Diagnosing commitment order | Scoring unaided accuracy | Model self-set under schema |
| num_predict 1200 | ORDER_V2 / heldout baseline | Standard studies | — | Controller |
| num_predict 2400 | `REPORT_RESEARCH.md` §6 DIES | Testing truncation only | — | Controller |
| tool request (REAL/SHAM) | `REPORT_TOOL_TRANSFER_V3.md` | Selection+parameterisation | Refraining claims | Controller supplies schema; model self-selects request |
| tool-result integration | `REPORT_INTEGRATION_V2.md`, `REPORT_SMOOTH.md` | Integration discrimination | Capability/unaided claims | Controller injects result |
| think=False | all studies | Deterministic short outputs | Need reasoning trace | Controller |
| temperature 0.0 | `REPORT_RESEARCH.md` §7 DIES | Diagnostic only | Production (did not repair answer) | Controller |
| repeat_last_n -1 | Modelfile default | — | — | Model default (UNKNOWN effect) |

## Known failure modes and validated fixes
- Forced commitment (answer before derivation): mitigate with derivation-first array
  contract (ORDER_V2 +18). Fix is controller-side schema order.
- Truncation (`done_reason=length`): raise num_predict; fixes JSON validity, not answer
  placement (`REPORT_RESEARCH.md` §6).
- Confidence out of range: single accounting convention; missing value flagged, not
  coerced (`REPORT_ORDER_V2.md` §10).
- Newline-in-string: schema minLength/maxLength and one-line instruction; never repaired
  model-side.
- Tool deference (answer quotes tool status, e.g. TFM04/TFM13): recorded as tool-hurt
  cells; not fixed (parameter binding only).
- Request compulsion (false-alarm 1.0): negative/faded cards did not change it
  (`REPORT_M2_CARD.md`); no validated fix.

## Explicit limits
- This is **not mechanistic interpretability**: block structure is tensor metadata,
  not a causal account of behaviour.
- No claim the model can self-regulate from this card; all tested controls were
  controller-set (prompt/schema/result injection).
- UNKNOWN fields (SWA/global split, exact tok/s, baked system prompt, repeat_last_n
  effect) are not filled by inference beyond what is marked INFERRED.
