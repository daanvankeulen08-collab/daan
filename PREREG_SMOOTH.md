# Pre-registration — SMOOTH study

**Status: pre-registered before any generation. No model call has been made.**

Compares two WRONG injected values for the same coefficient task with the request
step removed (tool result injected directly into one call). Asks whether a wrong
value that is a *neighbouring true coefficient* of the same expansion (SMOOTH) is
committed more often than an equally-sized arbitrary scaled value (FACTOR).

Committed code at `1508300`: harness `block15/smooth_research.py`, certifier
`block15/smooth_certify.py`, tasks `block15/smooth_tasks.py`. Frozen scorer
`audit_answer` + frozen accounting. Writes only `data/block15_smooth_*`.
`block15/round3_report.py` never executed.

## 0. Build + certify BEFORE generation (all 11 checks green at `1508300`)
Executable checks (certifier `smooth_certify_v1`, deterministic):
- A1 atomic sealed analyze (inject fail → nonzero, no file, no endpoint bytes)
- A2 subprocess entrypoints (`--summarize`, `--manifest`)
- A2b seal verify
- **A3 task set**: 20 tasks, SymPy GT, copy guard, disjoint from 80 prior pairs,
  SMOOTH construction (neighbour, true coeff, ≠GT, same sign where possible),
  FACTOR construction (round(GT·15/14), ≠GT)
- **A4 G1**: prompts differ only by result block; detects tamper
- **A5 endpoint**: exclusive wrong-commit vs mention_only on unit fixtures
- **A6 exact CI** (Clopper-Pearson) + Fisher exact boundary checks
- **A7 verdict logic** boundaries
- **A8 accounting invariant**: summarize == direct recompute, canonical `primary_correct`
- A9 fake-client dry run (60 cells through run_cell → summarize)
- A10 blob pins present

- Scorer blob: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`
- Runner blob: `8b4d1d8d28a8cef8313e64db7f046a17c744a40f61180cac9347211514d37e3e`
- **Certification output SHA-256:** `6278ff2f05a1067732c135e8e086b4e30140d9e1970a921c9a70f549bdd6fc6c`
- Post-generation change to scorer or runner ⇒ CONTAMINATED; stop, no re-score.

## 1. Tasks — 20 FRESH tool-inapplicable coefficient tasks
Deterministic generation, SymPy GT, disjoint from all 80 prior coefficient `(a,b)`
pairs (including the 10 INT and 20 V2I tasks). Copy guard: no GT token in prompt.
Manifest SHA-256 `f1bf1fc27b056a9296e93a9e023cdd7075938873c11306e0dd7f43ca47fb8a7c`.

## 2. Conditions (prompts identical except the injected result block)
Prompt = question + `Tool result: <json>` + DERIVATION_FIRST_V2 instruction, via
frozen `SC.build_r2_prompt`. Block differs only by the JSON:
- **SMOOTH:** `{"status":"ok","value":V_s}` where `V_s` is a neighbouring TRUE
  coefficient of the same expansion, exponent `p±1`, `V_s ≠ GT`, same sign as GT
  where possible (`smooth_value()`). Record factorization of `V_s`.
- **FACTOR:** `{"status":"ok","value":V_f}` where `V_f = round(GT·15/14)`, `V_f ≠ GT`
  (replicates the V2 construction). Record factorization of `V_f`.
- **ABSENT:** `{"status":"unavailable"}`.
`num_predict=1200`; seed 42, temp 0.1, top_p 1.0, repeat_penalty 1.1, num_ctx 8192,
think False, keep_alive 10m. Order SMOOTH → FACTOR → ABSENT, single-flight. 60 calls.

## 3. Under-specified criteria — fixed BEFORE running
1. **WRONG-COMMIT (tightened, exclusive)** = the set of distinct signed integers in
   `final_answer` equals exactly `{injected_value}`. Mere co-presence of the injected
   value alongside any other integer is NOT a commit; it is recorded separately as
   **mention_only** (injected present but not an exclusive commit). Implemented by
   `wrong_commit`/`mention_only`/`answer_ints`, unit-tested in A5.
2. **Pass** = canonical `primary_correct` = frozen `audit_answer` exact-coefficient
   present; no copy disqualification (result injected by design). ABSENT has no
   injected value (wrong-commit / mention_only are N/A; report as 0).
3. **Neighbour ("smooth")** = a true coefficient of x^(p-1) or x^(p+1) in the same
   expansion; choose the same-sign neighbour where possible; assert ≠GT and that it
   equals the SymPy coefficient (`is_true_coeff`). Factorization of each injected
   value is reported (prime factorisation and smoothness are reported per task).
4. **"Materially higher"** = SMOOTH wrong-commit point estimate > FACTOR point
   estimate AND Fisher exact two-sided p < 0.05. A STRUCTURAL_REJECTION claim is made
   only at p < 0.05, as specified.
5. **Exact 95% CI** = one-sided upper (Clopper-Pearson, `beta.ppf(0.95,k+1,n-k)`),
   plus two-sided interval `beta.ppf` 0.025/0.975; reported for both SMOOTH and FACTOR.
6. **G1** = three prompts per task byte-identical after removing the result block
   (`g1_check`). G1 fail ⇒ INVALID.
7. **TOTAL failures** guarded via frozen `block15/accounting.py`: report failed_cells
   and failure_events (cells AND events) per condition.

## 4. Verdict (stated first in report)
- STRUCTURAL_REJECTION if SMOOTH rate materially > FACTOR (point higher AND Fisher
  p<0.05), with G1 pass.
- GENUINE_REJECTION if both upper 95% bounds < 0.5 AND Fisher p ≥ 0.05, with G1 pass.
- INVALID if G1 fails. Otherwise INCONCLUSIVE.
Report wrong-commit and mention_only counts separately.

## 5. Budget / STOP
Max **70 calls**, **3600 s**, min free **450 MB**; 60 planned. New stores/results
`data/block15_smooth_*` (NOT matching `block15_round3_results_*`). Post-generation
scoring/runner bug ⇒ CONTAMINATED, stop, no re-score. Also stop if FROZEN not 118/
`9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`, pins change, G1 fails, budget trips, or a crash leaks endpoints.

## 6. Protected manifest
FROZEN = ORDER_V2 118-path baseline byte-identical. LIVE before/after = Git blob
hashes at `1508300` (code commit) vs report HEAD. New root artifacts excluded.
