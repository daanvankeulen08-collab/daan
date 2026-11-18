# FINDINGS — evidence synthesis

Synthesis only. Every number below is sourced from a **committed report** (SHA-256
listed in the audit trail). Where a figure was supplied in the task brief but is not
present in any committed report, it is marked **NOT IN COMMITTED SOURCE** and not
asserted as a finding. `data/` artifacts are untracked (`git ls-files data/` = 0) and
are cited only via the SHA-256 values recorded in the committed reports.

## Headline strongest result — ORDER_V2 field-order effect

- answer_first **0/30** vs derivation_first **18/30** audited non-copy passes; risk
  difference **+0.6000**, paired bootstrap 95% CI **[0.4333, 0.7667]**; discordant
  pairs b=0, c=18; **McNemar two-sided exact p = 0.000008** (committed value; artifact
  field `mcnemar_exact_two_sided_p = 8e-06`).
  - The brief's "p=7.63e-6" is **NOT IN COMMITTED SOURCE** — the committed report and
    artifact give 0.000008 / 8e-06 (2/2^18 unrounded equals 7.63e-6, but only the
    rounded figure is committed).
- G1 manipulation **PASS** (each arm ≥90% own / ≤10% other key order), G2 length PASS
  (truncation 0/30 vs 1/30). Independent re-audit is documented for the held-out
  study in `REPORT_RESEARCH.md` §8 (20 rows, 0 stored passes failed re-audit, no false
  positives), **not** inside REPORT_ORDER_V2.
- Mechanism: REPORT_ORDER_V2 §11c says the large effect is "consistent with that
  forced-commitment mechanism" but "does not isolate it from a generic 'answer before
  reasoning' penalty." **"9/30 all GT in derivation, none in answer" is NOT IN COMMITTED
  SOURCE**; a read-only check against the untracked artifact found 1 cell with all GT
  in derivation and none in answer, and 18 with all GT in derivation — neither equals
  9. No mechanism count is asserted.

## Ranked validated findings (exact stats, committed sources)

1. **Tool parameter binding, not selection** (`REPORT_TOOL_TRANSFER_V3.md`): tool-needed
   audited passes REAL 14 vs SHAM 4 (**+10/20**), McNemar exact **p=0.012939** (b=12
   real-only, c=2 sham-only per read-only artifact check; committed report states
   "14 gain, 4 loss"). False-alarm rate 1.0 (10/10). G1 PASS. The two tool-needed cells
   where SHAM passed and REAL failed were **TFM04, TFM13** (tool result present but not
   reproduced). Success = selection/parameterisation, not unaided arithmetic.
   - The brief's "b=2 c=12" reverses the committed/checked convention (real-only b=12,
     sham-only c=2); reported here as committed.
2. **Selective integration, no false integrations**: Integration V2 (`REPORT_INTEGRATION_V2.md`)
   REJECT_SURFACE — PLAUSIBLE wrong-adoption 3/20, one-sided upper 95% **0.343664**;
   G1 pass; accounting invariant PASS. SMOOTH study (`REPORT_SMOOTH.md`) —
   GENUINE_REJECTION: SMOOTH exclusive wrong-commit **0/20**, upper 95% **0.139108**
   (two-sided CI [0.0, 0.168433]); FACTOR **2/20**, upper 95% **0.282619** (CI
   [0.012349, 0.316983]); Fisher exact **p=0.487179**. Fisher comparison is
   underpowered (k=0 vs 2). "0/80 false integrations" and "0/276" are **NOT IN COMMITTED
   SOURCE** (they were read-only forensic counts over untracked artifacts).
3. **Request non-refraining**: committed `REPORT_TOOL_TRANSFER_V3.md` gives false-alarm
   rate **1.0** (10/10 tool-not-needed tasks requested the tool); `PROGRAM_KILL_AMENDMENT.md`
   records that null reachability was unresolved and the N1/N2 probes were pending. The
   "0/276 null", "N1 null-only 4/4", "N2 optional 4/4 object" figures are **NOT IN
   COMMITTED SOURCE** (they appear in a prior read-only answer / untracked probe
   artifact `block15_null_micro_results_*`, not in a committed report).
4. **Dead ends**: memory retry **NO SIGNAL** (`REPORT_MEMORY.md`); diagnosis text repair
   **NON-INFORMATIONAL** with oracle C=2 not exceeding max(D1,D2)=3 (D1=3, D2=1)
   (`REPORT_PLACEBO.md`); static negative/faded cards produced **no change in tool
   requests** — false-alarm 1.0 in both arms, CEILING (`REPORT_M2_CARD.md`).

## Retractions / corrected interpretations

- **Harness-artifact hypothesis for null**: retracted as a capability claim —
  `PROGRAM_KILL_AMENDMENT.md` states the null branch was not shown reachable in
  practice and the M2 request-based kill was withdrawn as a capability endpoint.
- **Own-computation-preference hypothesis**: not established — under stratification the
  V3 2×2 (from read-only artifact, not committed) does not support a clean preference
  claim; the committed reports attribute tool use to parameter binding and report the
  unaided pass rates but do not assert this hypothesis.
- **"33 paths"**: NOT IN COMMITTED SOURCE — FROZEN is documented everywhere as **118
  paths**, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`.
- **Criterion guarding one failure mode**: the single accounting convention
  (`REPORT_ORDER_V2.md` §10) replaced ad-hoc totals; passed cells contribute zero events.
- **GENUINE_REJECTION overclaims mechanism**: `REPORT_SMOOTH.md` objection (c) states the
  smooth/factor contrast is low-powered (0 vs 2); the label reflects a pre-registered
  decision rule, not a demonstrated mechanism.
- **Goal met only under reframed endpoint**: `PROGRAM_KILL_AMENDMENT.md` — the original
  request-refraining goal was not demonstrated; the program continued under the
  reframed integration endpoint.

## Open questions

- Request-refraining mechanism (why the tool is requested on inapplicable tasks).
- Tool-output answer suppression with n>2 (TFM04/TFM13 are the only tool-hurt cells).
- Smooth/factor contrast power (Fisher p=0.487, k=0 vs 2).
- Whether integration discrimination reflects true applicability or a task-family
  artifact (SMOOTH values were mostly constant coefficients, FACTOR arbitrary
  composites — `REPORT_SMOOTH.md` objection c).

## Audit trail — committed report SHA-256 (git blob)

| Report | SHA-256 (git blob) |
|---|---|
| REPORT_ORDER_V2.md | `8b00ee986e274242efd85a17f3099d7bc02c39006130c61f5a32f860fa3646b7` |
| REPORT_TOOL_TRANSFER_V3.md | `4aad7eb6277382f5922d70eb3d9f0b22280521408b79d2470b7f69b78703b4c5` |
| REPORT_M2_CARD.md | `dc3c88ee5f2d42239b96c79ead617bae1f92dbc75402dc781a64debfaddbd275` |
| REPORT_INTEGRATION.md | `80ed964267a4f94aed578d5f1c65a0b14cb0fafb16793f4036ff165145a20434` |
| REPORT_INTEGRATION_V2.md | `6f147c4b807d9f9e7b09b5bf0f07bbe81e7ce6e6d0ffcebf0f30aaee6e3ac992` |
| REPORT_SMOOTH.md | `2dc950dabb0fea4ea458a33afa7ff19e585fd749e27cf86046789daa65f8789f` |
| REPORT_MEMORY.md | `6719d36a832bd56d023d690ab2b76a132aeccc62c6452c726e2a6aad089cf766` |
| REPORT_DIAGNOSIS.md | `23734fa6d569fcbbda66639138f9710bd0926cdef1f60441092865f74fc1212a` |
| REPORT_PLACEBO.md | `406f1410d45af67b52a14bf311e774e15bab0d7fdf610b41e3e7740c0386b87a` |
| REPORT_QAD.md | `6f1814f7cb53ace8e1e0d76ce9b95584277f7a161f8a610f75871a843772394c` |
| REPORT_RESEARCH.md | `1fac5ba6ba53424c9e9e614b181b75c0643567eba2467793777ab69e06412026` |
| PROGRAM_KILL_AMENDMENT.md | `e879be5250b9d9f18364287a00e1a66619e3126d07fab0bb612c270ed6a3de1c` |

FROZEN: 118/118 byte-identical, manifest
`9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1` (verified at report
time in every committed report).

## Objections a–d

**a) Spec deviations.** Figures in the brief not present in committed reports
(p=7.63e-6, 9/30 mechanism, b=2/c=12 convention, 0/80, 0/276, N1/N2 4/4) are marked
NOT IN COMMITTED SOURCE and not asserted, per the synthesis-only rule.
**b) Reference deviations.** None; all studies used DERIVATION_FIRST_V2 and the frozen
scorer as reported.
**c) Where design is wrong/confounded.** Mechanism counts (forced commitment) are
qualitative in committed sources; Fisher/smooth contrasts underpowered; FROZEN path
count is 118, not 33.
**d) Unverified.** The exact-McNemar rounding, null-reachability counts, and any
mechanism number beyond the committed qualitative statement could not be sourced from
committed reports.
