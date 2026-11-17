# Pre-registration — Skill-tool study: executable tool selection for NO_SEARCH repair

**Status: pre-registered before any generation. No model call has been made for this study.**

This document fixes the design that tests whether the local model can select and
parameterise an allowlisted executable tool to repair the 9 NO_SEARCH failures, with
and without an offline procedure card. Harness `block15/skill_tool_research.py`;
only new `data/block15_skill_tool_*` artifacts written. `block15/round3_report.py`
is never executed. Commit `2c74a89` and earlier hold the prior (frozen) studies.

---

## 0. Scope and prior frozen conclusions
- `REPORT_PLACEBO.md`: diagnosis-text repair is **NON-INFORMATIONAL (frozen dead)**; not retried.
- Diagnosis-text repair is not revisited here; this is a distinct, tool-use hypothesis.
- **Tasks:** exactly the 9 NO_SEARCH cells: V2M03, V2M04, V2M06, V2M07, V2M09, V2M10,
  V2M11, V2M14, V2M15 (full ids frozen in the harness `PILOT_IDS`).
- **Pre-registered comparators (stored):** baseline A = **0/9**; stored placebo max = **2/9**
  (D1 passes V2M04, V2M07). These are context, not the primary criterion.

## 1. Allowlisted executable tool (STEP 1)
`block15/skill_tools.py::first_composite_quadratic(a,b,c,n_max)` — general SymPy procedure:
first n in [0,n_max] with composite f(n)=a·n²+b·n+c, returning `{n,value,factors}` or
`{none:true}`; strict int validation (bool excluded), `0<n_max<=128`; no eval/exec, no task
ids, no GT constants. Adopted as-is; 8 offline tests pass (correct first composite,
no-composite, bool rejection, n_max bounds, negatives, negative coefficients, no wrong
factorization sweep, general/no eval). No deviation.

## 2. Assistance levels (STEP 2)
`block15/skill_cards.py`, compiled offline. Card fields: trigger, procedure, tool-reference,
verification, failure_modes, provenance (assistance_level, compiler, task-hash=None).
- **L3**: full procedure card + ONE generated worked example f(n)=n²+103 (first composite
  n=1, value 104 = 2·13), verified NOT a pilot task and containing no GT token of any of
  the 30 ORDER_V2 tasks.
- **L0**: NO card — only `TOOL_SCHEMA` and the neutral task instruction.
- `TOOL_SCHEMA` object is imported unchanged from `skill_tools.py` and used identically in
  both levels (asserted). No pilot GT token appears in any assistance text or prompt
  (`verify_assistance_no_gt`, `verify_prompts_no_gt`); 5 offline tests pass.

## 3. Conditions and per-cell procedure
Four conditions: **L3_SHAM, L3_REAL, L0_SHAM, L0_REAL**. Each cell uses TWO calls:
- **Call 1** (`num_predict=300`): task + level assistance + `TOOL_SCHEMA` → tool-request JSON
  `{tool_request: null | {tool, arguments:{a,b,c,n_max}}, missing_process?}`. Schema-validated;
  invalid → `invalid_request` recorded and a null tool result used.
- **Call 2** (`num_predict=1200`): append the tool result, then ask for `DERIVATION_FIRST_V2`
  final object. **REAL** executes the tool (`first_composite_quadratic`); **SHAM** returns
  `{"status":"unavailable"}` with no GT. The prompt never reveals real vs sham, and Call 1
  is byte-identical between REAL and SHAM at a level by construction.

Sampling identical to ORDER_V2: `think=False`, `num_ctx=8192`, `temperature=0.1`,
`top_p=1.0`, `repeat_penalty=1.1`, `seed=42`, `keep_alive=10m`, `num_predict=1200`
(call 1 uses 300). No retries/repairs/teacher hints/memory injection.

## 4. G1 manipulation gate — verdict stated first
Tool-request payloads (`call1_prompt_sha256` and `raw_request`) must be **BYTE-IDENTICAL**
between REAL and SHAM at each assistance level. Any difference ⇒ **INVALID** (condition
leaked into the prompt). Verdict is the first thing reported.

## 5. Primary endpoint and extra records
- **PRIMARY**: audited non-copy final pass, strict SymPy minimality conjunction
  (n AND value AND both primes present), via `O.audit_answer`. Tool-derived answers allowed.
- Recorded separately from `copy_possible`: `tool_requested`, `tool_request_valid`,
  `parameters_correct`, `tool_result_used`.
- Failure accounting via `block15/accounting.py` (passes contribute zero events); distinct
  failed cells and multi-label events both reported.

## 6. Criteria
- **Tool value at level X:** REAL passes > SHAM passes AND REAL failed_cells < SHAM failed_cells.
- **AUTONOMY:** L0_REAL passes > 2 AND L0_REAL > L0_SHAM.
- **SCAFFOLDING-DEPENDENT:** L3_REAL > L3_SHAM but AUTONOMY fails.
- **DEAD:** no REAL > SHAM at either level.
- Verdict precedence: DEAD → "DEAD"; else AUTONOMY → "AUTONOMY"; else SCAFFOLDING →
  "SCAFFOLDING-DEPENDENT". Pass sets and overlaps reported, not just counts.

## 7. Budget and execution
- Max **80 calls**, max **3600 s**, min free physical **450 MB**, guarded before every call.
- Rationale: 9×4×2 = 72 calls max; measured 35.27 s/call upper bound ⇒ 2539 s; call 1 at
  300 tokens is shorter ⇒ expected ~1590–2540 s.
- Run order **single-flight**: L3_SHAM → L3_REAL → L0_SHAM → L0_REAL.
- New stores `data/block15_skill_tool.sqlite3` / `_events.jsonl`; results
  `data/block15_skill_tool_results_<cond>_<ts>.json` (does NOT match `block15_round3_results_*`).
- Refuse start if any skill-tool result exists, FROZEN changed, prompt/card GT leak, or model
  digest/quantisation mismatch.

## 8. Protected manifest
FROZEN = ORDER_V2 118-path baseline, byte-identical (skill-tool artifacts excluded by rule).
LIVE before/after are Git blob hashes at `1bbd13a` (block start) vs report-time HEAD.
`.gitignore` is not FROZEN; STEP 0 added `main/`, `main-search/`, `scratch_step0.py` to it.

## 9. Limits
n=9, single seed, one schema order, one local quantisation. The tool supplies the answer,
so success is **tool selection and parameterisation, NOT unaided reasoning**. No claim of
model understanding beyond selection. A 2-vs-2 tie cannot establish equivalence.
