# Pre-registration — Tool transfer V2 (certified scorer, fresh run)

**Status: pre-registered before any generation. No model call has been made for this V2 run.**

This is a NEW study following the CONTAMINATED V1 run (`REPORT_TOOL_TRANSFER.md`). Per the
HARD RULE, V1 was never re-scored and no V1 endpoint was computed or observed. This V2 study
has a repaired and **certified** scorer/runner, a NEW generation, and NEW stores.

## 0. Forensic basis (from STEP 0 of this block)
- V1 bug: `block15/tool_transfer_score.py::summarize()` line 284 did
  `per["L0_REAL"]["requested_ids"] & {x.split("_")[0] for x in tnn}`, where `requested_ids`
  is a `sorted(...)` **list** — `list & set` raised `TypeError`. Intended aggregation:
  the set of tool-not-needed short ids for which L0_REAL made a tool_request (false alarms).
- V1 runner typo: a one-line temporary edit in `summarize()`
  (`scorer_blob_sha256()` → `scorer_blob_hash()`) made only during post-generation
  `--summarize` troubleshooting (between run finish 17:57:43 +0100 and report commit
  18:00:56 +0100), then reverted. It lived in the analysis path only; `--run`/`run_study()`
  never calls `summarize()`, and the run finished before the edit, so **no model call ran
  under the modified runner**. The working tree was clean at the V1 report commit.
- V1 result files are retained as contaminated evidence, untouched. Their hashes are in
  `REPORT_TOOL_TRANSFER.md`. No V1 endpoint was reported.

## 1. Certified code (pinned git blob hashes at code commit `fd8c944`)
- Scorer `block15/tool_transfer_score.py`: **`da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`**
- Runner `block15/tool_transfer_research.py`: **`dc1855081fa445516de29f627f49d590bb2be9665ad807ef9a9d2ace542887cf`**
- Certifier `block15/tool_transfer_certify.py`: `b749dd4d4abe3dd178d3ab0359416880471bda9c4495b904467348ab5b03b554`
- Tasks `block15/tool_transfer_tasks.py`: `8837bf21529d3305085278d7f82db843b7d93a0c109712c4d9ffa84260e3dcf5`
- Any post-generation change to the scorer OR runner blob ⇒ **CONTAMINATED**; stop, no re-score.

### Pre-generation certification
`python -m block15.tool_transfer_research --certify` passed (exit 0) with deterministic
output SHA-256 **`0ba59312150e93c749501ed7be27efe41d49cf495c88834f7097d79063c6c63f`**.
It exercised: false-alarm fixtures 0/1/10 (0.0/0.1/1.0), mixed valid/invalid requests,
empty tool-needed set (McNemar p=1.0), all-pass/all-fail, missing raw_content (no crash),
G1 identity PASS vs violation INVALID, passes-contribute-zero-events, and a fake-client
end-to-end dry-run through `run_cell()` (call1+call2, real tool execution + sham) followed by
`summarize()`. 542 tests pass. Certification was run before this pre-registration; if it
had failed, generation would not have been started.

## 2. Tasks — SAME 30 frozen tasks from PREREG_TOOL_TRANSFER.md
20 tool-needed minimality (`TFM01–TFM20`, first composite within n≤64), 10 tool-not-needed
coefficient (`TFC01–TFC10`). Task manifest SHA-256 `138f2a1a441b9ce7ce59e61d0bfa147141878b003c10115ae840615ec52ec9a4`
(unchanged from V1). `verify_tasks()` re-computes SymPy truth, checks copy guard (no GT token
in any prompt), and disjointness. **Tasks are reused because they are frozen and
outcome-independent**; no V1 endpoint was observed to influence them.

## 3. Conditions — L0_REAL and L0_SHAM only, NO card
`TOOL_SCHEMA` identical; copy surface `r1_prompt` only; `tool_result_used` separate, never
disqualifying. Two calls per cell: call1 `num_predict=300` (tool_request JSON), call2
`num_predict=1200` (DERIVATION_FIRST_V2 final, tool result appended). REAL executes
`first_composite_quadratic`; SHAM returns `{"status":"unavailable"}`. Condition never revealed.
Sampling: seed 42, temp 0.1, top_p 1.0, repeat_penalty 1.1, num_ctx 8192, think False,
keep_alive 10m. Run order L0_REAL then L0_SHAM, single-flight.

## 4. G1 gate
Call-1 tool_request payloads byte-identical REAL vs SHAM (`call1_prompt_sha256`,
`raw_request`). Any difference ⇒ **INVALID**. Verdict reported first.

## 5. Endpoints and criteria
- **Primary replication:** paired REAL − SHAM audited non-copy passes on the 20 tool-needed;
  McNemar exact; significance only p<0.05.
- **Co-primary discrimination:** false-alarm rate on the 10 tool-not-needed (fraction with a
  tool_request); per-task list of inappropriate requests.
- **Secondary:** parameter accuracy, conversion rate given correct params, misuse cost
  (REAL vs SHAM passes on tool-not-needed).
- **REPLICATED:** REAL > SHAM on tool-needed AND failed_cells lower AND G1 pass.
- **SELECTIVE:** false-alarm rate ≤ 0.30.
- **Verdict matrix:** REPLICATED+SELECTIVE = procedural selection demonstrated;
  REPLICATED+not SELECTIVE = parameter binding only, NOT selection;
  not REPLICATED = prior result did not transfer (report plainly).
- Guard TOTAL failures across all modes via `block15/accounting.py`.

### What a pass does not prove
Not unaided arithmetic (tool supplies the answer), not general capability, not model
understanding beyond selection/parameterisation. Single seed, one tool, tool supplies answer.

## 6. Budget
Max **130 calls**, **5400 s**, min free **450 MB**. Rationale: 120 planned calls; measured
35.27 s/call upper bound → 4232 s. NEW stores:
`data/block15_tool_transfer_v2.sqlite3` / `_events.jsonl`; results
`data/block15_tool_transfer_v2_results_<cond>_<ts>.json` (NOT matching `block15_round3_results_*`).
Refuse start if any V2 result exists, FROZEN changed, scorer/runner blob changed, or model mismatch.

## 7. Protected manifest
FROZEN = ORDER_V2 118-path baseline, byte-identical (all `block15_tool_transfer*` artifacts
excluded). LIVE before/after are Git blob hashes at `fd8c944` (code commit) vs report HEAD.
PREREG/REPORT_TOOL_TRANSFER_V2.md are new root artifacts excluded from FROZEN.
`block15/round3_report.py` is never executed.
