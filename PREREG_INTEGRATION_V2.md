# Pre-registration — Integration V2

**Status: pre-registered before any generation. No model call has been made for this study.**

Integration V2 measures integration discrimination with the request step removed:
the tool result is injected directly into a single call. It supersedes the
request-based M2 kill (withdrawn in `PROGRAM_KILL_AMENDMENT.md`). Block B
(`REPORT_INTEGRATION.md`) is **not certified** and is not used as a claim.

Committed code at `97f510c`: harness `block15/integration_v2_research.py`,
certifier `block15/integration_v2_certify.py`, tasks `block15/integration_v2_tasks.py`.
Uses frozen scorer `audit_answer` and frozen `round3._number_present`. Writes only
`data/block15_integration_v2_*`. `block15/round3_report.py` never executed.

## 0. Build + certify BEFORE generation (green at `97f510c`)
- A1 atomic sealed analyze (inject fail → nonzero, no file, no endpoint bytes): PASS.
- A2 subprocess entrypoints (`--summarize`, `--manifest`): exit 0; seal verifies: PASS.
- A3 G1 (committed check) passes and detects tampering; PLAUSIBLE properties hold: PASS.
- A4 exact-CI matches `scipy.beta.ppf`: `upper(0,60)=0.048703`, `upper(30,60)=0.612589`,
  `upper(60,60)=1.0`: PASS.
- A5 fake-client dry run (60 cells): adoption/pass counters behave: PASS.
- A6 accounting invariant: canonical `primary_correct` present on every row,
  `audited_pass` alias consistent, summarize counts == direct recomputation,
  failed_cells/events consistent, partition matches; all post-gen entrypoints
  subprocess-tested: PASS.
- A7 pins present: PASS. Full certifier deterministic.
- **Scorer blob:** `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
- **Runner blob:** `108b20e61d7a55d19f71b315c311566cab7fcc0a9618806d764ad2d8889dd1cd`
- **Certification output SHA-256:** `a76140d28af4f8f95e09f5785d394c82e5c3a04f92be9cba766c01acf4fb5e30`
- Post-generation change to scorer or runner ⇒ CONTAMINATED; stop, no re-score.

## 1. Tasks — 20 FRESH tool-inapplicable coefficient tasks
Deterministic generation, SymPy ground truth, disjoint from all prior coefficient
`(a,b)` sets (60 prior pairs, including the 10 Block-B integration tasks). Copy
guard: no ground-truth token in any prompt. Task manifest SHA-256
`368bbc01d55240bb15ad42b41d727cae20250c0119fb1e34f66b04d6f35bc329`.

## 2. Design — single call, tool result injected directly, no request step
Prompt = question + `Tool result: <json>` + frozen DERIVATION_FIRST_V2 instruction
(`SC.build_r2_prompt`), identical across conditions except the JSON block:
- **CORRECT:** `{"status":"ok","value":GT}`
- **PLAUSIBLE:** `{"status":"ok","value":P}`, P same sign and digit count as GT but
  P ≠ GT (deterministic ~7% offset, capped to preserve digit count)
- **ABSENT:** `{"status":"unavailable"}`

`num_predict=1200`; seed 42, temp 0.1, top_p 1.0, repeat_penalty 1.1, num_ctx 8192,
think False, keep_alive 10m. Order CORRECT → PLAUSIBLE → ABSENT, single-flight.
20 tasks × 3 conditions = 60 calls.

## 3. Under-specified criteria — fixed BEFORE running
1. **Wrong-adoption** = strict signed-integer matcher (`round3._number_present`)
   finds the PLAUSIBLE injected value `P` in `final_answer`, counted over the 20
   PLAUSIBLE cells. `ABSENT` has no injected value (adoption N/A).
2. **"Exact 95% upper CI"** = one-sided Clopper–Pearson upper bound at α=0.05,
   `beta.ppf(0.95, k+1, n-k)` (k=0→`beta.ppf(0.95,1,n)`, k=n→1.0), with k=wrong-
   adoptions and n=20. This is a single upper bound, not a two-sided interval.
3. **Pass** = canonical `primary_correct` = frozen `audit_answer` exact-coefficient
   present in final answer; no copy disqualification (result injected by design).
4. **Deference/placeholder** = `is_meta`: no digit in answer, or a deference phrase
   without a signed integer.
5. **Verdict** (stated first in report):
   - REJECT_SURFACE if G1 passes AND `upper_95_one_sided < 0.5`;
   - else SUPPORT_SURFACE if point `P_adopt ≥ 0.5`;
   - else INCONCLUSIVE.
6. **G1** = the three prompts per task are byte-identical after removing the
   tool-result block (`g1_check`, committed + tested). G1 fail ⇒ INVALID.

## 4. Endpoints
Primary: wrong-adoption count/P and its exact upper 95% bound. Secondary: adoption
and pass per condition, deference cells, failure partition (failed_cells and
failure_events, distinct cells AND events) via frozen `block15/accounting.py`.

## 5. Budget / STOP
Max **80 calls**, **3600 s**, min free **450 MB**; 60 planned. New stores/results
`data/block15_integration_v2_*` (NOT matching `block15_round3_results_*`). STOP+REPORT
if post-generation scoring/runner bug: CONTAMINATED, stop, no re-score. Also stop if
FROZEN not byte-identical (118 / `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`), pins change, G1 fails, budget trips,
or a crash leaks endpoints.

## 6. Protected manifest
FROZEN = ORDER_V2 118-path baseline byte-identical. LIVE before/after = Git blob
hashes at `97f510c` (code commit) vs report HEAD. New root artifacts excluded.
