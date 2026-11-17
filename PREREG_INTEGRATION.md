# Pre-registration — Integration discrimination (Block B)

**Status: pre-registered before any generation. No model call has been made for this study.**

This study asks whether the earlier tool-use pattern is integration discrimination
or a surface mismatch. The tool-schema `anyOf` confound is removed entirely: the
tool-result block is injected DIRECTLY into a single call per cell — there is no
request step, so the model never sees the tool-request schema. Three conditions
differ only by that injected block.

Harness `block15/integration_research.py`, certifier `block15/integration_certify.py`,
fresh tasks `block15/integration_tasks.py`. Uses the frozen scorer's `audit_answer`
and the frozen `round3._number_present` signed-integer matcher. Writes only new
`data/block15_integration_*` artifacts. `block15/round3_report.py` is never run.

## 0. Build + certify BEFORE generation (green at code commit `425dde3`)
- **A1 atomic sealed analyze:** inject failure → nonzero exit, no summary file, no
  endpoint bytes (`ANALYSIS FAILED: RuntimeError` only). **PASS.**
- **A2 subprocess entrypoints:** `--manifest`, `--summarize` on synthetic files;
  exit codes 0; seal verifies. **PASS.**
- **A3 G1 + plausible:** G1 passes on built prompts and detects a tampered prompt;
  PLAUSIBLE values differ from truth, keep sign and digit count. **PASS.**
- **A4 fake-client dry run:** 30 cells through `run_cell` → `summarize`; adoption
  metric behaves as designed (CORRECT adopts 1.0 / passes 1.0; PLAUSIBLE adopts 1.0
  / passes 0.0 under a client that echoes the injected value). **PASS.**
- **A5 pins** (git blob SHA-256 at generation-time HEAD):
  - scorer `block15/tool_transfer_score.py`: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
  - runner `block15/integration_research.py`: `1094a3b537c569ccc047c3e6bba5657b0b76cf14fb9fca60b6c59a7c9b3d8f1e`
  - Post-generation change to either ⇒ CONTAMINATED; stop, no re-score.
- **Certification output SHA-256:** `890027bff81d721139a5e8ff49deb58eec941474e249ba77014b7bd972b32513`
  (deterministic across repeated runs). Generation started only after green + this
  hash recorded here.

## 1. Tasks — 10 FRESH tool-inapplicable coefficient tasks
Generated deterministically in committed code; SymPy ground truth; disjoint from all
prior coefficient sets (50 prior `(a,b)` pairs; `verify_tasks()` asserts disjointness,
copy guard, distinct ids). Task manifest SHA-256
`d43d719273c34a8ba4d331c7b87a19c8808d6ea4c358a903cc685ec8689dfbcd`. No ground-truth
token appears in any task prompt. None of these tasks' outcomes was observed.

## 2. Conditions — single call, tool-result block injected directly
Prompt = question + `Tool result: <json>` + the frozen DERIVATION_FIRST_V2 instruction,
built by the frozen `SC.build_r2_prompt`. Identical across conditions except the JSON:
- **CORRECT:** `{"status":"ok","value":C}` where C = true coefficient.
- **PLAUSIBLE:** `{"status":"ok","value":P}` with P deterministic: ~7% offset from C,
  same sign, same digit count, P ≠ C (`plausible_value()`), numerically wrong.
- **ABSENT:** `{"status":"unavailable"}`.

Model never sees a request schema. `num_predict=1200`; seed 42, temp 0.1, top_p 1.0,
repeat_penalty 1.1, num_ctx 8192, think False, keep_alive 10m. Order CORRECT →
PLAUSIBLE → ABSENT, single-flight. 10 tasks × 3 conditions = 30 calls.

## 3. Pre-run criteria clarifications (RAISED BEFORE GENERATION)
The brief leaves several terms under-specified; these operational definitions are
fixed now, before any result is seen:

1. **"Adopts the injected value"** = the signed integer token of the injected value
   appears in `final_answer` (frozen `_number_present`, sign-aware). ABSENT has no
   injected value, so adoption is **N/A** for it (not counted as 0 or 1).
2. **"Pass"** = frozen `audit_answer(...).audit_passed` (exact coefficient token
   present). No copy disqualification is applied: there is no separate Call-1 surface
   here and the tool result is injected by design. Stored `copy_possible` is False.
3. **PLAUSIBLE shape/magnitude** = same sign and digit count as truth, small (~7%)
   offset — implemented by `plausible_value()`; values are asserted in certification.
4. **"Placeholder/meta-comment rather than a value"** = `final_answer` has no digit,
   OR matches a deference phrase (e.g. "tool data", "we'll go with tool") without a
   signed integer — implemented by `is_meta()`. Every such task id is reported.
5. **"High rate"** has no numeric threshold in the brief. The primary statistic is
   reported per condition as a raw proportion `P_adopt`; no threshold is applied to
   declare the surface-mismatch hypothesis — the verdict label simply reflects
   whether PLAUSIBLE adoption is > 0, and the reader sees the three proportions.
6. **"Matches ABSENT"** is operationalized as: PLAUSIBLE adoption = 0 together with a
   final answer carrying the correct coefficient (a computed value), i.e. the wrong
   injected value is ignored. Reported via `P_adopt` and `P_pass` per condition.

## 4. Endpoints / G1
- **PRIMARY:** `P_adopt` per condition (CORRECT, PLAUSIBLE; ABSENT = N/A).
- Secondary: audited `P_pass` per condition; meta-cell list per condition.
- **G1:** the three prompts for each task are byte-identical after removing the
  tool-result block (`g1_check`, committed + tested). Any failure ⇒ INVALID.
- Failure partition over `block15/accounting.py`: report failed_cells and
  failure_events (distinct cells AND events), plus flag partition per condition.

## 5. Budget / STOP
Max **45 calls**, **2400 s**, min free **450 MB**; 30 planned. New stores/results
`data/block15_integration_*` (NOT matching `block15_round3_results_*`). STOP+REPORT if
FROZEN not byte-identical (118 / `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`), pins change, G1 fails, budget trips,
or no proof that a crash leaked no endpoint. No fix-and-rescore.

## 6. Protected manifest
FROZEN = ORDER_V2 118-path baseline byte-identical. LIVE before/after = Git blob hashes
at `425dde3` (code commit) vs report HEAD. `PREREG_INTEGRATION.md` and
`REPORT_INTEGRATION.md` are new root artifacts excluded from FROZEN.
