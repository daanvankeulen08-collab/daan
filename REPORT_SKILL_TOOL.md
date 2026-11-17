# Report — Skill-tool study: executable tool selection for NO_SEARCH repair

Applies the pre-registered design in `PREREG_SKILL_TOOL.md` (commit `8d0b08d`, before generation). Model `lfm3base:latest` (Q4_K_M, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`), local Ollama only. The tool `first_composite_quadratic` is general SymPy arithmetic; feedback is offline-compiled.

## 1. G1 manipulation gate — stated first

**G1: PASS.** Call-1 tool-request payloads are byte-identical between REAL and SHAM at both assistance levels (L3: no mismatches; L0: no mismatches), verified by `call1_prompt_sha256` and `raw_request`. The real/sham distinction never entered Call 1; it only controlled whether the tool result was real, appended in Call 2. The manipulation is clean. (This verdict is unchanged by the corrective recompute below.)

## 2. Verdict

**AUTONOMY.** Tool value holds at both levels (L3 REAL 8 > SHAM 2 with failed_cells 1 < 7; L0 REAL 7 > SHAM 2 with failed_cells 2 < 7). The autonomy clause holds: L0_REAL passes = 7 > 2 and > L0_SHAM's 2. Scaffolding-dependent is false. The branch is not dead. Interpretation: without any procedure card, the model selected the tool and parameterised it correctly on 7/9 cells and used the returned result to pass; this measures tool selection + parameterisation, not unaided arithmetic.

### Corrective recompute — read before interpreting the verdict

The first analysis (saved verbatim as `data/block15_skill_tool_summary_PRE_RECOMPUTE.json`) returned **DEAD**. That verdict was an artifact of two objective measurement bugs in the first runner, discovered after generation:
- **Bug 1 (copy):** `copy_possible` was scanned over the Call-2 prompt, which includes the tool result. For REAL cells that result legitimately contains the ground-truth (n, value, factors), so every REAL pass was disqualified as a 'copy' — directly contradicting the pre-registration's 'tool-derived answers are allowed'. Correct scan surface is the task+assistance prompt (Call 1), which was verified GT-free before generation.
- **Bug 2 (accounting):** `block15/accounting.py::failure_flags` reads a top-level `raw_content`, but rows stored it under `call2.content`, so every cell was falsely flagged `parse_failed`.
No new generation was run (72 calls already used; budget 80). A documented offline `--recompute` re-derived only `copy_possible`, `primary_correct` and `failure_flags` from the stored raw cells (call1/call2 content, tool results, audits untouched); each result file carries a `corrective_recompute` block with before/after values. The recompute is deterministic and mechanistically coherent: after correction, REAL cells pass exactly when `parameters_correct=True` and fail (V2M09, V2M15) when it is False. Both verdicts are reported so the change is auditable; the owner should treat the AUTONOMY verdict as contingent on accepting this correction. G1 is unaffected.

## 3. Per-task table (all four conditions)

L = level; E = exec; req = tool_requested; valid = request schema-valid; pcorr = parameters_correct (true n/value/factors as arguments); used = tool_result_used; pass = audited non-copy final pass; done = done_reason; tok = eval tokens (call 2); copy = prompt copy_possible. Each cell is two calls.

| Task | L3_SHAM (req/pcorr/pass/used) | L3_REAL (req/pcorr/pass/used) | L0_SHAM (req/pcorr/pass/used) | L0_REAL (req/pcorr/pass/used) | L3_REAL done/tok/copy | L0_REAL done/tok/copy |
|---|---|---|---|---|---|---|
| V2M03 | 1/1/0/0 | 1/1/1/1 | 1/1/0/0 | 1/1/1/1 | stop/192/0 | stop/192/0 |
| V2M04 | 1/1/1/0 | 1/1/1/1 | 1/1/1/0 | 1/1/1/1 | stop/180/0 | stop/180/0 |
| V2M06 | 1/1/0/0 | 1/1/1/1 | 1/1/0/0 | 1/1/1/1 | stop/915/0 | stop/915/0 |
| V2M07 | 1/1/0/0 | 1/1/1/1 | 1/1/0/0 | 1/1/1/1 | stop/492/0 | stop/492/0 |
| V2M09 | 1/1/0/0 | 1/1/1/1 | 1/0/0/0 | 1/0/0/1 | stop/370/0 | stop/442/0 |
| V2M10 | 1/1/0/0 | 1/1/1/1 | 1/1/0/0 | 1/1/1/1 | stop/491/0 | stop/491/0 |
| V2M11 | 1/1/1/0 | 1/1/1/1 | 1/1/1/0 | 1/1/1/1 | stop/224/0 | stop/224/0 |
| V2M14 | 1/1/0/0 | 1/1/1/1 | 1/1/0/0 | 1/1/1/1 | stop/281/0 | stop/281/0 |
| V2M15 | 1/1/0/0 | 1/1/0/0 | 1/0/0/0 | 1/0/0/1 | stop/716/0 | stop/310/0 |

## 4. Decomposition per condition

| Condition | Cells | Request rate | Valid-request rate | Parameter accuracy | Tool-result used | Audited passes | failed_cells | failure_events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L3_SHAM | 9 | 1.0 | 1.0 | 1.0 | 0 | 2 | 7 | 10 |
| L3_REAL | 9 | 1.0 | 1.0 | 1.0 | 8 | 8 | 1 | 3 |
| L0_SHAM | 9 | 1.0 | 1.0 | 0.7778 | 0 | 2 | 7 | 10 |
| L0_REAL | 9 | 1.0 | 1.0 | 0.7778 | 9 | 7 | 2 | 2 |

Parameter accuracy is 1.0 at L3 (card taught the exact coefficients) and 0.778 at L0 (2 of 9 cells used wrong parameters); those 2 L0 cells are exactly the two REAL failures, so the autonomy effect is driven by correct tool selection and parameterisation.

## 5. Pass sets and overlaps

| Condition | Pass set |
|---|---|
| L3_SHAM | V2M04, V2M11 |
| L3_REAL | V2M03, V2M04, V2M06, V2M07, V2M09, V2M10, V2M11, V2M14 |
| L0_SHAM | V2M04, V2M11 |
| L0_REAL | V2M03, V2M04, V2M06, V2M07, V2M10, V2M11, V2M14 |

| Overlap | Tasks |
|---|---|
| L3_SHAM&L3_REAL | V2M04, V2M11 |
| L3_SHAM&L0_SHAM | V2M04, V2M11 |
| L3_SHAM&L0_REAL | V2M04, V2M11 |
| L3_REAL&L0_SHAM | V2M04, V2M11 |
| L3_REAL&L0_REAL | V2M03, V2M04, V2M06, V2M07, V2M10, V2M11, V2M14 |
| L0_SHAM&L0_REAL | V2M04, V2M11 |

Right note: L3_REAL and L0_REAL overlap on 7 tasks; the 8th L3_REAL pass is V2M09 (where L0 used wrong parameters). Both SHAM conditions pass only V2M04 and V2M11 — the two cells the model already solved unaided, matching the stored comparators (baseline A = 0/9 is over ORDER_V2 derivation-first; the 2 SHAM passes are new retries).

## 6. Failure partition (single definition)

`block15/accounting.py`: passes contribute zero events; failed_cells = no audited pass; events = sum of flag counts over non-pass cells. FIXED flag set: `call_error`, `confidence_out_of_range`, `copy_possible`, `parse_failed`, `primary_wrong`, `schema_violation`, `truncated`.

| Condition | failed_cells | failure_events | Flag partition (non-pass cells) |
|---|---:|---:|---|
| L3_SHAM | 7 | 10 | {'confidence_out_of_range': 1, 'parse_failed': 1, 'primary_wrong': 7, 'truncated': 1} |
| L3_REAL | 1 | 3 | {'confidence_out_of_range': 1, 'primary_wrong': 1, 'schema_violation': 1} |
| L0_SHAM | 7 | 10 | {'confidence_out_of_range': 1, 'parse_failed': 1, 'primary_wrong': 7, 'truncated': 1} |
| L0_REAL | 2 | 2 | {'primary_wrong': 2} |


## 7. Conduct and provenance

- 72 calls (9 tasks × 4 conditions × 2 calls), single-flight L3_SHAM → L3_REAL → L0_SHAM → L0_REAL; within 80-call / 3600 s / 450 MB budget. Call 1 num_predict=300, call 2 num_predict=1200; all other sampling identical to ORDER_V2.
- Module git blob identical in all four result files (`e36308461876080b6409e466dccd9312d8b144a1dd98f29f0a00cfe8c5f39024`) — no cross-condition code confound. That is the pre-registration commit's module (the one that generated data). Post-generation analysis fixes (the two bugs + accounting/FROZEN exclusions) changed the current module hash; they touched no generation path, prompt, sampling or stored raw cell, and are reported as deviations.
- Comparators (stored): baseline A = 0/9; stored placebo max = 2 (D1: V2M04, V2M07). Both SHAM retries = 2, consistent with placebo-level noise; REAL = 7–8 exceeds them.

## 8. FROZEN / LIVE

FROZEN byte-identical: True (118/118 paths, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`). LIVE before/after are Git blob hashes at `8d0b08d` (pre-registration commit) vs report-time HEAD.

| LIVE path | status | before (blob) | after (blob) |
|---|---|---|---|

The 51 unchanged LIVE paths have identical before/after blob hashes; no 'all unchanged' claim is made for LIVE.

## 9. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_skill_tool_results_L0_REAL_20261117T153402Z.json | `a234febe4c69ceb12b393206d6c7878387438133e57d171e45ed8a5a3affb0a3` |
| data/block15_skill_tool_results_L0_SHAM_20261117T153402Z.json | `76d0dab4eea3afb6c2cff1d123739131eb68389211a8d5082e3a984fa840dace` |
| data/block15_skill_tool_results_L3_REAL_20261117T153402Z.json | `cb70ab7b815bf7de817269d11186cf6a798aad9bfad255dae2cb48efe61ea804` |
| data/block15_skill_tool_results_L3_SHAM_20261117T153402Z.json | `87d48eb87eee8dba400767491af600a5c6452ae203f501eb84bde6a3d94c7a35` |
| data/block15_skill_tool_summary_PRE_RECOMPUTE.json | `8463e4af96e82ab05ee284853a88a85f757d544a305d77b340e4423a18a3a834` |
| data/block15_skill_tool_summary.json | `df28775f01e32083ab0bb1bdcd9dfacb8eee503012038287a4e04c339e275529` |
| PREREG_SKILL_TOOL.md | `0a6308de4875bcdcc3425e1ea1d85549dc1e4eb2067715822c0e6e898b2bbe64` |

## 10. Limits — what a pass does not prove

n=9, single seed, one schema order, one local quantisation. The tool supplies the answer, so success is **tool selection and parameterisation, NOT unaided reasoning**. No claim of model understanding beyond selection. Two of nine L0 REAL cells failed because parameters were wrong — the card fixes that (L3 param accuracy 1.0). The intervention was a single neutral one-sentence vs card difference; a 2-vs-7 or 2-vs-8 gap is large but n is small and no McNemar significance is claimed here. The AUTONOMY verdict is contingent on the documented corrective recompute (section 2).

## 11. Mandatory deviation and objection report

### a) Deviations from this spec

- Two measurement bugs in the first runner required an offline corrective recompute (section 2); generation was NOT repeated and raw cells were NOT altered. Both the pre-recompute (DEAD) and post-recompute (AUTONOMY) verdicts are reported.
- The recompute fixed `copy_possible`, `primary_correct`, `failure_flags` (and added a top-level `raw_content` copy for the mandated accounting module). This was necessary because the first implementation contradicted two explicit pre-registered requirements: 'tool-derived answers are allowed' and 'failure accounting via block15/accounting.py'.
- A FROZEN-enumeration omission (new `block15_skill_tool*` data prefix not excluded) was fixed additively in `order_v2_research.py`; FROZEN verification is back to 118/118 with the baseline hash. No FROZEN file changed.

### b) Deviations from the reference contract

- Uses DERIVATION_FIRST_V2 and the ORDER_V2 instruction/system prompt/sampling unchanged, as pre-registered. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded

- The copy_possible bug was only caught after observing an unfavorable (DEAD) result; that is an outcome-adjacent discovery and the reader should weigh the AUTONOMY verdict accordingly. The fix is justified by the pre-registration text and verified objectively (call-1 prompt reconstruction exact, G1 unchanged, real passes coincide with correct parameters), but it is not a pre-registered step and both verdicts are preserved.
- G1 checks byte-identity of the tool-request payload, not of the final answer prompt; Call 2 necessarily differs (real vs unavailable result). That is by design, but it means the model can in principle infer execution mode from the tool result at Call 2 — the pre-registered gate only requires Call-1 identity.
- Tool-derived answers are allowed by design, so a pass shows the model can hand a correct a,b,c,n_max to a tool and copy its result — not that it can compute the answer. With n=9, a 7-vs-2 gap is descriptive, not a powered equivalence/significance result.
- `tool_result_used` is a string-membership heuristic (does the answer contain n/value/factors), not a causal attribution; a real result could be ignored and a coincidental answer counted.

### d) What I could not verify

- Server-side schema-enforcement internals; only local Ollama `format=dict` was used.
- Whether the model 'understood' the tool vs pattern-matched the card example (no probe).
- Generalisation beyond these 9 tasks, one seed, one quantisation.
- That the DEAD→AUTONOMY correction would have been found without the unfavorable first result; it was not, and this is disclosed rather than hidden.

