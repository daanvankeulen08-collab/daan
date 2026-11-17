# Report — bounded items 1–5 (amendment, accounting fix, null probe, Integration V2)

Verdicts first. Facts only; no endpoint was re-scored and no code was changed after
generation.

## Item 1 — PROGRAM_KILL_AMENDMENT (committed `cf493ee`)
The M2 request-based kill is withdrawn as a capability-endpoint claim: it measured
request-discrimination, not integration discrimination. The program is OPEN pending
Integration V2. Block B is not certified. (Document committed and pushed.)

## Item 2 — ACCOUNTING CERT FIX (committed `760f021`) — VERDICT: GREEN
Canonical row field is now `primary_correct`, written by the runner; `audited_pass`
is a retained alias. Frozen `block15/accounting.py` reads the canonical field. Added
`test_integration_accounting_field_mismatch` and a cert invariant that on synthetic
fixtures checks summarize counts == direct raw recomputation, failed_cells/events
consistency, canonical-field presence, alias consistency, and that every post-gen
entrypoint (`--summarize`, `--manifest`) is subprocess-tested. `--certify` fails on
mismatch. `--certify` run green, deterministic, exit 0.
- **Accounting cert hash (Integration, fixed):** `2abed6e6f24cfad28f33f76e69e22c57447a6799724dc4370aae1b0e46a3a296`
- 590 tests pass; FROZEN 118/118.

## Item 3 — NULL MICRO-PROBE (8 calls, committed `6e0c4d6`) — harness facts
Two schema forms on 4 trivial no-tool tasks, num_predict 300, V3 sampling, all
`protocol_variant=primary`, `schema_enforced=True`:

| Form | tool_request result | missing_process |
|---|---|---|
| N1 `tool_request` type:null only | null 4/4, omitted 0, object 0 | `no_tool_needed` 4/4 |
| N2 `tool_request` not required, anyOf null/object | object 4/4, null 0, omitted 0 | `no_tool_needed` 4/4 |

N1 forced null (the only permitted value); N2 left the field optional and the model
emitted an object even while stating `no_tool_needed`. This is a harness/schema-form
fact, not a capability claim.

## Item 4/5 — INTEGRATION V2 — VERDICT: REJECT_SURFACE
**Stated first:** G1 passes and the exact one-sided 95% upper bound on wrong-adoption
is 0.343664 < 0.5, so the pre-registered rule yields **REJECT_SURFACE** (no certified
surface-adoption of the wrong injected value). 60 calls completed within budget
(80 max / 3600 s / 450 MB). Sealed analysis ran once with no post-generation bug;
accounting counts equal direct recomputation (Item 2 fix confirmed on real data).

**Primary (PLAUSIBLE condition):** wrong-adoption k=3/20, P_adopt=0.15, exact upper
95% (Clopper–Pearson, α=0.05, `beta.ppf(0.95,k+1,n-k)`) = **0.343664**.

| Condition | n | adopted (P_adopt) | passes (P_pass) | account audited_passes / failed_cells / events | partition |
|---|---:|---:|---:|---|---|
| CORRECT | 20 | 19 (0.95) | 19 (0.95) | 19 / 1 / 1 | primary_wrong:1 |
| PLAUSIBLE | 20 | 3 (0.15) | 17 (0.85) | 17 / 3 / 3 | primary_wrong:3 |
| ABSENT | 20 | N/A (0.0 shown) | 15 (0.75) | 15 / 5 / 5 | primary_wrong:5 |

The three PLAUSIBLE wrong-adoption cells (strict matcher finds the injected wrong
value in final_answer): V2I04 (answer `-599862`, GT −559872, pass=False — genuine
adoption); V2I06 (GT −466560) and V2I19 (GT 1179648) — both computed the correct GT
and passed, but quoted the injected wrong value in their derivation ("something
off"), so the pre-registered strict matcher counts them. No deference/placeholder
cells (`is_meta`) in any of the 60 cells. G1 pass=True (three prompts per task
byte-identical after removing the tool-result block).

## Provenance
- Scorer blob: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
- Runner blob: `108b20e61d7a55d19f71b315c311566cab7fcc0a9618806d764ad2d8889dd1cd` (both match pre-reg; unchanged post-generation)
- Accounting cert hash: `2abed6e6f24cfad28f33f76e69e22c57447a6799724dc4370aae1b0e46a3a296`
- Integration V2 cert hash: `a76140d28af4f8f95e09f5785d394c82e5c3a04f92be9cba766c01acf4fb5e30` (matches pre-reg)
- Task manifest: `368bbc01d55240bb15ad42b41d727cae20250c0119fb1e34f66b04d6f35bc329`
- FROZEN: 118/118 byte-identical, `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`
- LIVE git blobs at `97f510c` vs HEAD `198e4fe`: all 68 paths unchanged.

### Artifact SHA-256
| Artifact | SHA-256 |
|---|---|
| block15_integration_v2_results_CORRECT_20261117T215902Z.json | `d631fb978212bfa1821d285b3c0e8be76c0e853514b5aed6ce349f1cc9461432` |
| block15_integration_v2_results_PLAUSIBLE_20261117T215902Z.json | `ee23a38a2d3ad49781176d2dfd9b7472879f15d90afd64127f06918dab1859e9` |
| block15_integration_v2_results_ABSENT_20261117T215902Z.json | `7b4e176e43d25874802ebd0208da78bd44988eb40a334f01f7a6e220309e79ce` |
| block15_integration_v2_summary.json | `3dc07535ab740e5089a882ff2bf375ba53e5457c3b9c41b4b2ec5fc2b1284fd0` |
| block15_null_micro_results_20261117T215120Z.json | `e50d339c608abc4e1a01f0b76ffcf1ab476d869666f3114ef27b34c7356d8c9c` |
| PREREG_INTEGRATION_V2.md | `ed0525c5814855544a532e8a57c6ed7b6feedca4e9a3faabba5bd36a5ec9d064` |

## OBJECTIONS a–d
**a) Spec deviations.** None in the executed studies. The amendment and accounting fix are
additive committed changes explicitly authorized by the directive. No endpoint re-scored.
**b) Contract deviations.** None: DERIVATION_FIRST_V2, neutral instruction, sampling and
direct-injection design are as pre-registered; scipy is an existing pinned dependency.
**c) Where design is wrong/confounded.** The strict matcher counts the injected wrong
value even when the model quotes it while disputing it (V2I06, V2I19); this is the
pre-registered definition, so it is reported as a fact, not corrected post hoc. The exact
upper bound is one-sided; k=3/20 still yields an upper bound (0.3437) below 0.5.
**d) Unverified.** Generalisation beyond one seed, one tool, 20 coefficient tasks, three
static conditions. Whether a different plausible-value offset rule changes the count —
not tested. No corrected study was run.
