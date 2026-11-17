# Report — Tool transfer V3 (certified harness, fresh generation)

Pre-registered in `PREREG_TOOL_TRANSFER_V3.md` (commit `e70538c`, before generation). Model `lfm3base:latest` (Q4_K_M, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`), local Ollama only. Backed by the certified scorer `da95df42…` and runner `212e9cf8…` (unchanged pins).

## 1. G1 gate and verdict — stated first

**G1 manipulation: PASS.** Call-1 tool_request payloads are byte-identical REAL vs SHAM (L0: identical, no mismatches). The real/sham distinction never entered Call 1.

**Verdict: PARAMETER BINDING ONLY, NOT SELECTION.** The primary replication criterion holds, but the discrimination (selectivity) criterion fails:
- REPLICATED: **true** — tool-needed audited passes REAL 14 vs SHAM 4 (+10), McNemar exact p=0.012939 (<0.05), failed_cells 6 < 17, G1 pass.
- SELECTIVE: **false** — false-alarm rate 1.0 on tool-not-needed (> 0.30).
By the pre-registered verdict matrix, REPLICATED + not SELECTIVE = **parameter binding only, NOT selection**. The tool helps when the model chooses to call it with correct parameters, but the model does not refrain from calling it when it is inapplicable. Per the program goal, this outcome keeps M2 available (a new pre-registration + fresh generation); it is not tuned here.

## 2. False-alarm rate and inappropriate requests

False-alarm rate = 10/10 = 1.0. Inappropriate tool_requests (all 10 tool-not-needed tasks): TFC01, TFC02, TFC03, TFC04, TFC05, TFC06, TFC07, TFC08, TFC09, TFC10.
Every coefficient-extraction task requests a tool whose schema only accepts a,b,c,n_max for a quadratic — a category error. This is the selectivity failure.

## 3. Funnel per condition

| Condition | Scope | Cells | requested | params_correct | result_used | audited passes |
|---|---|---:|---:|---:|---:|---:|
| L0_REAL | all | 30 | 30 | 19 | 14 | 24 |
| L0_REAL | tool-needed | 20 | 20 | 19 | 14 | 14 |
| L0_REAL | tool-not-needed | 10 | 10 | 0 | 0 | 10 |
| L0_SHAM | all | 30 | 30 | 19 | 0 | 13 |
| L0_SHAM | tool-needed | 20 | 20 | 19 | 0 | 4 |
| L0_SHAM | tool-not-needed | 10 | 10 | 0 | 0 | 9 |

On tool-needed tasks: REAL requested 20, correct parameters 19, tool result used 14, passed 14. The 1 wrong-parameter cell and 5 correct-parameter-but-unused cells did not convert. SHAM requested 20, correct parameters 19, result used 0 (sham), passed 4 (unaided). Conversion (correct params + available result + wrong answer) failures: **0** — none; every cell with correct parameters and a used real result passed.

## 4. Per-task table

Columns per condition: req=tool_requested, pc=parameters_correct, used=tool_result_used, pass=audited non-copy pass, done=done_reason, tok=eval tokens, cp=copy_possible.

| Task | kind | REAL req/pc/used/pass/done/tok/cp | SHAM req/pc/used/pass/done/tok/cp |
|---|---|---|---|
| TFM01_tool_needed | minimality | 1/1/1/1/stop/334/0 | 1/1/0/0/stop/261/0 |
| TFM02_tool_needed | minimality | 1/1/1/1/stop/307/0 | 1/1/0/0/stop/1024/0 |
| TFM03_tool_needed | minimality | 1/1/0/0/stop/295/0 | 1/1/0/0/stop/958/0 |
| TFM04_tool_needed | minimality | 1/1/0/0/stop/556/0 | 1/1/0/1/stop/487/0 |
| TFM05_tool_needed | minimality | 1/1/0/0/stop/437/0 | 1/1/0/0/stop/162/0 |
| TFM06_tool_needed | minimality | 1/1/1/1/stop/279/0 | 1/1/0/0/stop/397/0 |
| TFM07_tool_needed | minimality | 1/1/1/1/stop/258/0 | 1/1/0/0/stop/716/0 |
| TFM08_tool_needed | minimality | 1/1/1/1/stop/409/0 | 1/1/0/0/stop/403/0 |
| TFM09_tool_needed | minimality | 1/1/1/1/stop/201/0 | 1/1/0/0/stop/953/0 |
| TFM10_tool_needed | minimality | 1/1/1/1/stop/387/0 | 1/1/0/0/stop/247/0 |
| TFM11_tool_needed | minimality | 1/1/1/1/stop/282/0 | 1/1/0/0/stop/211/0 |
| TFM12_tool_needed | minimality | 1/1/0/0/stop/268/0 | 1/1/0/0/stop/265/0 |
| TFM13_tool_needed | minimality | 1/0/0/0/stop/310/0 | 1/0/0/1/stop/988/0 |
| TFM14_tool_needed | minimality | 1/1/1/1/stop/195/0 | 1/1/0/0/stop/538/0 |
| TFM15_tool_needed | minimality | 1/1/1/1/stop/539/0 | 1/1/0/1/stop/867/0 |
| TFM16_tool_needed | minimality | 1/1/0/0/stop/465/0 | 1/1/0/0/stop/226/0 |
| TFM17_tool_needed | minimality | 1/1/1/1/stop/625/0 | 1/1/0/0/stop/211/0 |
| TFM18_tool_needed | minimality | 1/1/1/1/stop/234/0 | 1/1/0/0/stop/203/0 |
| TFM19_tool_needed | minimality | 1/1/1/1/stop/275/0 | 1/1/0/1/stop/380/0 |
| TFM20_tool_needed | minimality | 1/1/1/1/stop/262/0 | 1/1/0/0/stop/475/0 |
| TFC01_tool_not_needed | coefficient | 1/0/0/1/stop/240/0 | 1/0/0/1/stop/316/0 |
| TFC02_tool_not_needed | coefficient | 1/0/0/1/stop/312/0 | 1/0/0/1/stop/777/0 |
| TFC03_tool_not_needed | coefficient | 1/0/0/1/stop/232/0 | 1/0/0/1/stop/421/0 |
| TFC04_tool_not_needed | coefficient | 1/0/0/1/stop/375/0 | 1/0/0/0/stop/160/0 |
| TFC05_tool_not_needed | coefficient | 1/0/0/1/stop/226/0 | 1/0/0/1/stop/239/0 |
| TFC06_tool_not_needed | coefficient | 1/0/0/1/stop/267/0 | 1/0/0/1/stop/170/0 |
| TFC07_tool_not_needed | coefficient | 1/0/0/1/stop/231/0 | 1/0/0/1/stop/274/0 |
| TFC08_tool_not_needed | coefficient | 1/0/0/1/stop/309/0 | 1/0/0/1/stop/275/0 |
| TFC09_tool_not_needed | coefficient | 1/0/0/1/stop/254/0 | 1/0/0/1/stop/252/0 |
| TFC10_tool_not_needed | coefficient | 1/0/0/1/stop/210/0 | 1/0/0/1/stop/267/0 |


## 5. Pass sets and overlaps

| Condition | Pass set |
|---|---|
| L0_REAL | TFC01, TFC02, TFC03, TFC04, TFC05, TFC06, TFC07, TFC08, TFC09, TFC10, TFM01, TFM02, TFM06, TFM07, TFM08, TFM09, TFM10, TFM11, TFM14, TFM15, TFM17, TFM18, TFM19, TFM20 |
| L0_SHAM | TFC01, TFC02, TFC03, TFC05, TFC06, TFC07, TFC08, TFC09, TFC10, TFM04, TFM13, TFM15, TFM19 |

| Overlap | Tasks |
|---|---|
| L0_REAL&L0_SHAM | TFC01, TFC02, TFC03, TFC05, TFC06, TFC07, TFC08, TFC09, TFC10, TFM15, TFM19 |

REAL−SHAM tool-needed discordance: 14 gain, 4 loss → McNemar exact p=0.012939. Risk difference (paired, tool-needed) = +0.50.

## 6. Failure partition (single definition)

`block15/accounting.py`: passes contribute zero events; failed_cells = no audited pass; failure_events = sum of flag counts over non-pass cells.

| Condition | Cells | audited passes | failed_cells | failure_events | Flag partition |
|---|---:|---:|---:|---:|---|
| L0_REAL | 30 | 24 | 6 | 6 | {'primary_wrong': 6} |
| L0_SHAM | 30 | 13 | 17 | 21 | {'confidence_out_of_range': 2, 'parse_failed': 1, 'primary_wrong': 17, 'schema_violation': 1} |


## 7. Provenance, pinned blobs, certification

- Scorer git blob `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2` — unchanged since pre-registration (`scorer_hash_unchanged=True`).
- Runner git blob `212e9cf8d759f90a9710eb50ced466bc33486387032ed256a30f66bd836313e7` — unchanged since pre-registration.
- Certification `tool_transfer_v3_certify_v1` passed A1–A6; deterministic output SHA-256 `fd74465bdcc58257f132e7849c80c6beffd3bcefcc86ebcd0e754df3a0f1746e` (matches the pre-registration; the pre-reg hash was corrected for a transcription typo with no code/design change — see deviations).
- 120 calls single-flight L0_REAL→L0_SHAM, within 130/5400/450 budget. All cells used `protocol_variant=primary`, `schema_enforced=True`, `think_sent=False`. No post-generation scorer or runner change; no re-scoring. Seal present in the summary (wrapper not bypassed).

## 8. FROZEN / LIVE

FROZEN byte-identical: True — 118/118 paths, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1` (baseline hash). LIVE before/after are Git blob hashes at `e70538c` (pre-registration) vs report-time HEAD.

| LIVE path | status | before (blob) | after (blob) |
|---|---|---|---|

The 56 unchanged LIVE paths have identical before/after blob hashes; no 'all unchanged' claim is made for LIVE.

## 9. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_tool_transfer_v3_results_L0_REAL_20261117T182136Z.json | `abe574e8cb613f1ad8e88c08bac974d3e3f4aebf9914951c8109545adf1c8c95` |
| data/block15_tool_transfer_v3_results_L0_SHAM_20261117T182136Z.json | `74379a20182801e0f6c999a9b40f3a8661e26588e05c73e312ab939a92eef0b1` |
| data/block15_tool_transfer_v3_summary.json | `1759100cd912cc79242684d4063005c8273a4af395c18d059b39a3a2725a8cf0` |
| PREREG_TOOL_TRANSFER_V3.md | `52da3ca6fdf885888a37d7407ea8b018ca1174bd194d89db9e709ca17c77563d` |

## 10. Limits

Single seed (42), one tool, n=30 (20 tool-needed), one local quantisation. The tool supplies the answer, so success here is **tool selection and parameterisation, NOT unaided arithmetic**. No claim of model understanding beyond selection/binding. A 14-vs-4 tool-needed gap is descriptive; n is small and one seed cannot establish robustness. The false-alarm rate is 1.0 — the model does not refrain — so the 'refrains when unneeded' half of the goal is not demonstrated by M1.

## 11. Mandatory deviation and objection report

### a) Deviations from this spec

- The pre-registration's certification-output SHA-256 was hand-transcribed with a missing `cc`; corrected in `PREREG_TOOL_TRANSFER_V3.md` after generation. This is a factual-record fix only — the actual deterministic certifier output and all pinned scorer/runner blobs are unchanged, and no design/scoring/outcome was altered. Disclosed rather than hidden.
- No re-scoring; the sealed analyzer wrote the summary once on full success. No endpoint was used to tune mechanics. Result is reported as found.

### b) Deviations from the reference contract

- DERIVATION_FIRST_V2, neutral instruction + schema-order sentence, and ORDER_V2 sampling are unchanged, as pre-registered. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded

- The model requests the tool on all 30 tasks, including coefficient tasks where the tool is inapplicable. The current prompt gives only the tool schema, no guidance on when to refrain; the selectivity failure may reflect task framing as much as an inability to refrain. M2 (fading/negative cards, new pre-reg) is the pre-registered next step.
- SHAM passes on tool-needed (4) and tool-not-needed (9) are unaided-answer successes; the +10 REAL gain is tool-mediated, not a reasoning gain.
- McNemar p=0.0129 is computed on 20 paired tasks; the multiple endpoints (primary, false-alarm, misuse) are reported descriptively without multiplicity correction.

### d) What I could not verify

- Server-side schema-enforcement internals (only local Ollama `format=dict` used).
- Generalisation beyond one seed, one tool, these frozen tasks.
- Whether a negative/fading card can cut false alarms without losing hits — that is M2, not tested here.
