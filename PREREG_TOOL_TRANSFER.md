# Pre-registration — Tool transfer: procedural tool selection on fresh tasks

**Status: pre-registered before any generation. No model call has been made for this study.**

This pre-registration records the FROZEN SCORER hash before generation. Per the hard rule,
if a scoring bug is discovered after generation, this run is **CONTAMINATED** and must be
discarded — no re-scoring; a corrected run needs a new pre-registration and new generation.

Harness `block15/tool_transfer_research.py`; all measurement in the frozen
`block15/tool_transfer_score.py`; tasks in `block15/tool_transfer_tasks.py`. Writes only
new `data/block15_tool_transfer_*` artifacts. `block15/round3_report.py` never executed.

## 0. Frozen scorer (hard rule)
- Scorer module: `block15/tool_transfer_score.py`, version `tool_transfer_scorer_v1_frozen`.
- **Git blob SHA-256 (pinned at commit `98f1a62`, BEFORE generation):**
  `d0da9ce3915713293848b72311201003c50ae34f4cc0497ea9f4ff3b2b5bd4ad`.
- The report MUST assert the scorer's git blob hash still equals this value. Any mismatch,
  or any post-generation scoring change, voids the run as CONTAMINATED.
- Copy surface frozen as `r1_prompt` (task + assistance + tool schema). The tool result
  appended at Call 2 legitimately contains ground truth and is NEVER scanned for copying;
  `tool_result_used` is recorded separately and never disqualifies. `primary_correct =
  audit_passed AND NOT copy_possible`. These live in the scorer, not the runner.
- All audit, request-validation, parameter-accuracy, accounting and analysis logic is in
  the frozen scorer. The runner only builds prompts (via scorer functions), makes HTTP
  calls, executes/shams the tool, persists raw cells, and invokes the scorer.

## 1. Tasks — 30 FRESH, frozen
20 TOOL-NEEDED bounded-minimality tasks `TFM01–TFM20` (a·n²+b·n+c, first composite within
n≤64, SymPy ground truth n/value/both prime factors); 10 TOOL-NOT-NEEDED binomial
coefficient tasks `TFC01–TFC10` (first_composite_quadratic inapplicable). Disjoint from
Round 3, H1–H5, C01–C08, V2C*/V2M* (verified by `TT.verify_tasks`: 30 distinct ids,
ground truth recomputed by SymPy, copy guard passes). Prompts and SHA-256s frozen in the
tasks module and listed by `--manifest`. GT-token-in-prompt assert passes for all 30.

## 2. Conditions — L0_REAL and L0_SHAM only
NO procedure card at either level. `TOOL_SCHEMA` identical (SHA-256
`0a02ea9a4d606f2b8c1b1ed02a9c61cda3e2193b12b85d04d94e8c083eb4b4cd`). Two calls per cell:
- Call 1, `num_predict=300`: task + tool schema → tool_request JSON
  `{tool_request: null | {tool, arguments:{a,b,c,n_max}}, missing_process?}`.
- Call 2, `num_predict=1200`: append the tool result, ask for `DERIVATION_FIRST_V2` final.
  REAL executes `first_composite_quadratic`; SHAM returns `{"status":"unavailable"}`.
  Condition never revealed in any prompt.
Sampling: seed 42, temp 0.1, top_p 1.0, repeat_penalty 1.1, num_ctx 8192, think False,
keep_alive 10m. No retries/repairs/teacher hints/memory injection/net model API.

## 3. G1 manipulation gate
Call-1 tool_request payloads must be byte-identical REAL vs SHAM (`call1_prompt_sha256`
and `raw_request`). Any difference ⇒ **INVALID**. G1 verdict reported first.

## 4. Endpoints and criteria
- **Primary (replication):** paired REAL − SHAM audited non-copy passes on the 20
  tool-needed tasks; McNemar exact; significance only at p<0.05.
- **Co-primary (discrimination):** false-alarm rate = fraction of the 10 tool-not-needed
  tasks where a tool_request is made; report the per-task list of inappropriate requests.
- **Secondary:** parameter accuracy on tool-needed; conversion rate given correct params;
  misuse cost = REAL vs SHAM passes on tool-not-needed.
- **REPLICATED:** REAL > SHAM on tool-needed AND failed_cells lower AND G1 pass.
- **SELECTIVE:** false-alarm rate ≤ 0.30 on tool-not-needed.
- **Verdict matrix:** REPLICATED+SELECTIVE → procedural selection demonstrated;
  REPLICATED+not SELECTIVE → parameter binding only, NOT selection;
  not REPLICATED → prior result did not transfer (report plainly).
- Guard TOTAL failures across all modes via `block15/accounting.py`, not one mode.

### What a pass does not prove
Not unaided arithmetic (the tool supplies the answer), not general capability, not model
understanding beyond selection/parameterisation. Single tool, single seed, n=30.

## 5. Budget and execution
Max **130 calls**, **5400 s**, min free **450 MB**. Rationale: 120 planned calls; measured
35.27 s/call upper bound → 4232 s. Run order **L0_REAL then L0_SHAM**, single-flight.
New stores `data/block15_tool_transfer.sqlite3` / `_events.jsonl`; results
`data/block15_tool_transfer_results_<cond>_<ts>.json` (NOT matching `block15_round3_results_*`).
Refuse start if any tool-transfer result exists, FROZEN changed, or model mismatch.

## 6. Protected manifest
FROZEN = ORDER_V2 118-path baseline, byte-identical (tool-transfer artifacts excluded by
rule). LIVE before/after are Git blob hashes at `98f1a62` (code commit) vs report HEAD.
PREREG/REPORT_TOOL_TRANSFER.md are new root artifacts excluded from FROZEN.
