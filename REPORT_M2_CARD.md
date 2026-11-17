# Report — M2: negative/faded card intervention (fresh tasks)

Pre-registered in `PREREG_M2_CARD.md` (commit `b060b0f`, before generation). Model `lfm3base:latest`, digest `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`, local Ollama only. Fresh 30-task set; frozen scorer `da95df42…`, runner `72f6f93b…` (pins unchanged).

## 1. Verdict — stated first

**CEILING. Program kill: STOP.** M2's pre-registered criterion (`any_discrimination=False`) is **not met**: neither card arm achieved TNN request rate ≤ 0.30 with TN request rate ≥ 0.80 and hits ≥ 14. Both card arms kept the false-alarm rate at 1.0 and discrimination at 0.0. The negative/faded cards did **not** cut false alarms on fresh tasks. Per the program goal, this is a ceiling: report and stop. No further stage was run and no outcome was tuned.

The manipulation itself was clean: the card-only-diff check passed (see §5). The scorer's G1 field reads INVALID only because the frozen scorer hardcodes L0_REAL/L0_SHAM keys and M2 mapped the two intentionally *different* card arms onto them — those call-1 payloads are supposed to differ (by the card). This is an adapter artifact, not a leak; M2's decision uses `m2_criterion` and the card-only-diff check, not that G1 field.

## 2. Why M2 ran and what it tested

M1 (`REPORT_TOOL_TRANSFER_V3.md`) was REPLICATED but not SELECTIVE: tool selection and parameterisation worked (tool-needed REAL 14 vs SHAM 4, p=0.0129) but the false-alarm rate was 1.0. M2 asked whether an offline-compiled negative card (explicit applicability rule, 64 tokens) or a faded card (general reminder, 24 tokens) could cut tool requests on tool-not-needed tasks without losing tool-needed hits. Both arms used REAL execution and identical tool schema; the card was the only prompt difference.

## 3. Funnel per condition

| Arm | Scope | n | requested | params_correct | result_used | audited passes |
|---|---|---:|---:|---:|---:|---:|
| CARD_NEG | all | 30 | 30 | 20 | 18 | 28 |
| CARD_NEG | tool-needed | 20 | 20 | 20 | 18 | 18 |
| CARD_NEG | tool-not-needed | 10 | 10 | 0 | 0 | 10 |
| CARD_FADE | all | 30 | 30 | 18 | 16 | 26 |
| CARD_FADE | tool-needed | 20 | 20 | 18 | 16 | 16 |
| CARD_FADE | tool-not-needed | 10 | 10 | 0 | 0 | 10 |

Both arms: TN request rate 1.0, TNN request rate 1.0, discrimination 0.0. Hits (tool-needed passes) were 18 (CARD_NEG) and 16 (CARD_FADE), both ≥ M1's 14 — so hits were not lost, but false alarms were not cut either. The card changed nothing about whether the tool was requested.

## 4. Pass sets and overlaps

| Arm | Pass set |
|---|---|
| CARD_NEG | M2C01, M2C02, M2C03, M2C04, M2C05, M2C06, M2C07, M2C08, M2C09, M2C10, M2M01, M2M02, M2M03, M2M04, M2M05, M2M06, M2M07, M2M08, M2M09, M2M10, M2M11, M2M13, M2M14, M2M15, M2M16, M2M17, M2M18, M2M20 |
| CARD_FADE | M2C01, M2C02, M2C03, M2C04, M2C05, M2C06, M2C07, M2C08, M2C09, M2C10, M2M01, M2M02, M2M03, M2M04, M2M05, M2M06, M2M07, M2M08, M2M09, M2M10, M2M11, M2M15, M2M16, M2M17, M2M18, M2M20 |

| Overlap | Tasks |
|---|---|
| L0_REAL&L0_SHAM | M2C01, M2C02, M2C03, M2C04, M2C05, M2C06, M2C07, M2C08, M2C09, M2C10, M2M01, M2M02, M2M03, M2M04, M2M05, M2M06, M2M07, M2M08, M2M09, M2M10, M2M11, M2M15, M2M16, M2M17, M2M18, M2M20 |

All 10 tool-not-needed tasks passed in BOTH arms (unaided), and the tool was requested on all 10 in BOTH arms — the category error persisted despite the cards.

## 5. Manipulation check, conversion failures, failure partition

**Card-only-diff check: PASS.** Within each arm every cell's Call-1 prompt reduces to an identical no-card base; between arms, for every task, the prompts differ *only* by the card block. No real/sham status was ever revealed (both arms REAL, no feedback). Cards were asserted free of any ground-truth token and task id (`A3_card_safety` PASS).

Conversion failures (correct params + available real result + wrong answer): **0** — none in either arm.

| Arm | Cells | audited passes | failed_cells | failure_events | Flag partition |
|---|---:|---:|---:|---:|---|
| CARD_NEG | 30 | 28 | 2 | 5 | {'confidence_out_of_range': 1, 'parse_failed': 1, 'primary_wrong': 2, 'truncated': 1} |
| CARD_FADE | 30 | 26 | 4 | 7 | {'confidence_out_of_range': 1, 'parse_failed': 1, 'primary_wrong': 4, 'truncated': 1} |


## 6. Provenance, pins, certification

- Scorer git blob `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2` — unchanged (`scorer_hash_unchanged=True`).
- Runner git blob `72f6f93ba7f8971a1fbb40a9126fcd81ab11ab76a960909fe60f480e161954e5` — unchanged since pre-registration.
- Task manifest `b7b0da5cb8602667244e30a107792d332afd7c512462a3f623e83b9b9c62ab24` — fresh, disjoint from all prior task sets (verified).
- Certification `m2_certify_v1` passed A1–A5; deterministic output SHA-256 `4a7cbf8120aa3497945b11ccdc78885890cc2855bd8e98578a7ce3e724553066` (matches pre-registration; re-verified after generation). No post-generation scorer/runner change; no re-scoring. Seal present in summary. 120 calls within 130/5400/450 budget.

## 7. FROZEN / LIVE

FROZEN byte-identical: True — 118/118 paths, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`. LIVE before/after are Git blob hashes at `d6eb3b1` (code commit) vs report-time HEAD.

| LIVE path | status | before (blob) | after (blob) |
|---|---|---|---|

The 58 unchanged LIVE paths have identical before/after blob hashes; no 'all unchanged' claim is made for LIVE.

## 8. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_m2_results_CARD_FADE_20261117T190507Z.json | `7285d14778e1cfd9cd6444b6976647a6c4231c13379b2930c4cc12d2f29ec681` |
| data/block15_m2_results_CARD_NEG_20261117T190507Z.json | `7454f43da1c21c76842b89cdd7f847ec90a204e699ee72e5f3b8d9b93affd9f5` |
| data/block15_m2_summary.json | `916c21f79e493c9d42ee344c04285f5f405b369ef5382bac7f0d1b5f3e5420b4` |
| PREREG_M2_CARD.md | `8af888f9df1e6c7249f025ca2182ff8190e33d2d8cc80d80957c8f5bd35ccc95` |

## 9. Limits

Single seed (42), one tool, n=30 (20 tool-needed), one local quantisation, static cards. The tool supplies the answer, so any success here is tool selection/parameterisation and refraining, not unaided arithmetic. No capability or understanding claim. Both cards left the false-alarm rate at 1.0, so on this evidence the model does not refrain from requesting a needed-but-inapplicable tool under these static instructions.

## 10. Mandatory deviation and objection report

### a) Deviations from this spec

- The scorer's G1 field reports INVALID due to the frozen-scorer adapter mapping the two intentionally different card arms onto L0_REAL/L0_SHAM; their call-1 payloads must differ by the card. This is a documented adapter artifact, not a manipulation failure. M2's decision uses `m2_criterion` plus the card-only-diff check (PASS). Disclosed here, not hidden.
- M2 uses only two REAL card arms (120 calls) rather than a no-card control in the same run; the no-card comparator is M1's pre-registered finding (false-alarm 1.0), stated before generation in the pre-registration. No endpoint was used to tune mechanics.

### b) Deviations from the reference contract

- DERIVATION_FIRST_V2, neutral instruction + schema-order sentence, and ORDER_V2 sampling are unchanged. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded

- The cards may simply be too weak or too easily ignored; a 24–64 token static reminder was not enough to overcome the model's apparent default of requesting the available tool. This test cannot distinguish 'cannot refrain' from 'the card was insufficient'.
- Tool-not-needed tasks all passed unaided in both arms; the false alarm is a category error (requesting a quadratic tool for coefficient extraction), not a wrong final answer.
- The adapter's G1 artifact means the scorer's own verdict fields (NOT REPLICATED) are not M2's criterion; reporting relies on `m2_criterion`. This coupling is a design limitation.

### d) What I could not verify

- Whether a longer, repeated, or held-out-card intervention could cut false alarms — the program kill stops the program here.
- Server-side schema-enforcement internals; only local Ollama `format=dict` was used.
- Generalisation beyond one seed, one tool, these fresh tasks and two static cards.

