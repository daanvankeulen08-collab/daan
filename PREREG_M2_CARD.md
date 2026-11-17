# Pre-registration — M2: can a negative/faded card cut false alarms without losing hits?

**Status: pre-registered before any generation. No model call has been made for M2.**

M1 (`REPORT_TOOL_TRANSFER_V3.md`) showed REPLICATED but **not SELECTIVE**: on frozen V3
tasks the model requested the tool on all 10 tool-not-needed tasks (false-alarm 1.0), while
it did select and parameterise the tool on tool-needed tasks (+10, p=0.0129). Per the program
goal, M2 tests whether an offline-compiled negative/faded instruction card can cut false
alarms without losing hits. **No M1 endpoint was used to tune M2 mechanics**; M2 is a new
hypothesis with fresh tasks, a new pre-registration and new generation.

Harness `block15/m2_research.py`, certifier `block15/m2_certify.py`, backed by the unchanged
frozen scorer `block15/tool_transfer_score.py` and fresh tasks `block15/m2_tasks.py`. Writes
only new `data/block15_m2_*` artifacts. `block15/round3_report.py` never executed.

## 0. Build + certify BEFORE generation (green at commit `d6eb3b1`)
- **A1 atomic sealed analyze:** inject failure → nonzero, no summary file, no endpoint bytes. PASS.
- **A2 subprocess entrypoints:** `--summarize`, `--manifest`, `--verify-cards` on synthetic
  files; exit codes all 0; seal verify True. PASS.
- **A3 card safety:** both cards contain no ground-truth token and no task id. PASS.
- **A4 confined-fix:** reproduce ORDER_V2 0/30+18/30, SKILL_TOOL L3_SHAM2 L0_SHAM2 exactly. PASS.
- **A5 blob pins** (git blob SHA-256 at generation-time HEAD):
  - scorer `block15/tool_transfer_score.py`: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
  - runner `block15/m2_research.py`: `72f6f93ba7f8971a1fbb40a9126fcd81ab11ab76a960909fe60f480e161954e5`
  - Post-generation change to either ⇒ CONTAMINATED; stop, no re-score.
- **Certification output SHA-256:** `4a7cbf8120aa3497945b11ccdc78885890cc2855bd8e98578a7ce3e724553066`
  (deterministic across repeated runs). Generation started only after green + this hash here.

## 1. Fresh tasks — 30 NEW, disjoint from every prior task set
20 tool-needed minimality (`M2M01–M2M20`, first composite n≤64), 10 tool-not-needed
coefficient (`M2C01–M2C10`). Task manifest SHA-256
`b7b0da5cb8602667244e30a107792d332afd7c512462a3f623e83b9b9c62ab24`.
`verify_tasks()` recomputes SymPy truth, asserts copy guard and disjointness from
Round3/H1-H5/C01-M08/V2C*/V2M*/TFM*/TFC*. None of these tasks' outcomes was observed.

## 2. Cards (offline-compiled static text, NO runtime teacher text)
- **CARD_NEG** (64 tokens): explicit applicability rule — the tool only accepts a,b,c,n_max
  for a quadratic's first composite; if the question is not that, do not request the tool.
- **CARD_FADE** (24 tokens): faded general reminder — only request the tool for the
  smallest-n-composite quadratic question, otherwise solve directly.
- Both asserted free of any ground-truth token and task id. Both appended to the Call-1
  prompt; the tool schema is identical in both. The model is never told which card is in use,
  nor given any attempt-specific feedback.

## 3. Conditions and calls
Two conditions: **CARD_NEG** then **CARD_FADE**, single-flight. 30 tasks each, 2 calls/cell
(call1 `num_predict=300` tool_request; call2 `num_predict=1200` DERIVATION_FIRST_V2 final with
tool result appended). Both arms use REAL tool execution. Sampling seed 42, temp 0.1, top_p
1.0, repeat_penalty 1.1, num_ctx 8192, think False, keep_alive 10m. Copy surface = Call-1
prompt only; `tool_result_used` recorded separately, never disqualifying.

## 4. Criterion (M2 verdict)
- **hits** = tool-needed audited non-copy passes; **false alarms** = tool-not-needed tasks
  with a tool_request; **discrimination** = TN request rate − TNN request rate.
- **DISCRIMINATION** iff ANY card arm has TNN request rate ≤ 0.30 AND TN request rate ≥ 0.80
  AND hits ≥ M1 baseline hits (14). This means the card cut false alarms without losing hits.
- Otherwise **CEILING** → report ceiling and STOP the program (per program kill).
- Guard TOTAL failures across all modes via `block15/accounting.py`. Report funnel, pass sets,
  conversion failures, failure partition (distinct + events), G1-equivalent card-only-diff
  check, pins, cert hash, FROZEN/LIVE, artifact SHA-256s.

### What a pass does not prove
Not unaided reasoning (the tool supplies the answer); not general capability or understanding.
Success is tool selection/parameterisation and refraining under a static card, on n=30, one seed.

## 5. Budget / STOP
Max **130 calls**, **5400 s**, min free **450 MB**; 120 planned calls, 35.27 s/call upper
bound → 4232 s. New stores/results `data/block15_m2_*` (NOT matching `block15_round3_results_*`).
STOP+REPORT if: endpoint revealed and unfavorable; fix not confined; FROZEN not byte-identical
(118/9ece313e); budget trips; cannot prove no endpoint escaped a crash. No fix-and-rescore.

## 6. Protected manifest
FROZEN = ORDER_V2 118-path baseline byte-identical (all `block15_m2*` excluded). LIVE before/after
are Git blob hashes at `d6eb3b1` (code commit) vs report HEAD. PREREG/REPORT_M2_CARD.md are new
root artifacts excluded from FROZEN.
