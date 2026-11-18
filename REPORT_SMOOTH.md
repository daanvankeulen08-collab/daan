# Report — SMOOTH study (neighboring vs factor wrong values)

Verdict first. Facts only; no endpoint was re-scored and no code was changed after
generation. Pre-registered in `PREREG_SMOOTH.md` (commit `a71768a`, before generation).

## VERDICT: GENUINE_REJECTION
G1 passes, both exact one-sided 95% upper bounds are below 0.5 (SMOOTH 0.139108,
FACTOR 0.282619), and Fisher exact p=0.487179 ≥ 0.05 (no significant difference), so
the pre-registered rule yields **GENUINE_REJECTION**. 60 calls completed within budget
(70 max / 3600 s / 450 MB). Sealed analysis ran once; no post-generation bug;
accounting counts equal direct recomputation (canonical `primary_correct`).

### Primary endpoint — exclusive WRONG-COMMIT (int-set == {injected})
| Condition | wrong-commit | n | P | one-sided upper 95% | two-sided 95% CI |
|---|---:|---:|---:|---:|---|
| SMOOTH | 0 | 20 | 0.0 | 0.139108 | [0.0, 0.168433] |
| FACTOR | 2 | 20 | 0.1 | 0.282619 | [0.012349, 0.316983] |

Fisher exact 2×2 table [[0,20],[2,18]] → p=0.487179. CI method: Clopper-Pearson
(`scipy.beta.ppf`). "Materially higher" (SMOOTH point > FACTOR point AND p<0.05) is
false. A STRUCTURAL_REJECTION claim is NOT made (p not < 0.05).

### WRONG-COMMIT vs mention_only, per condition
| Condition | wrong_commit | mention_only | passes (P_pass) | account passes / failed_cells / events | partition |
|---|---:|---:|---:|---|---|
| SMOOTH | 0 | 1 (SM14) | 17 (0.85) | 17 / 3 / 3 | primary_wrong:3 |
| FACTOR | 2 (SM04, SM10) | 2 (SM01, SM03) | 15 (0.75) | 15 / 5 / 5 | primary_wrong:5 |
| ABSENT | N/A (0) | N/A (0) | 17 (0.85) | 17 / 3 / 3 | primary_wrong:3 |

- FACTOR wrong-commit cells: SM04 (answer `-52663`, inj −52663) and SM10 (answer
  `12497`, inj 12497) — exclusive commits to the wrong value, pass=False.
- mention_only cells (injected value present in a derivation but NOT an exclusive
  commit; all pass=True): SMOOTH SM14; FACTOR SM01, SM03. Under the tightened
  endpoint these are NOT adoption.
- G1 pass=True (three prompts per task byte-identical after removing the result block).
- No meta/placeholder cells (`is_meta`) in any of the 60 cells.
- TOTAL failures guarded: failed_cells/events 3/3, 5/5, 3/3 across conditions.

## Per-task injected values with prime factorization and smoothness
GT = SymPy ground truth of coefficient of x^p in (a x + b)^6. SMOOTH = neighboring
true coefficient (exponent shown, `is_true_coeff` asserted); FACTOR = round(GT·15/14).

| Task | GT | SMOOTH value (x^exp, same-sign) | SMOOTH factorization | FACTOR value | FACTOR factorization |
|---|---:|---|---|---|---|
| SM01 | −806736 | 117649 (x^0, no) | 7^6 | −864360 | 2^3·3^2·5·7^4 |
| SM02 | −373248 | 46656 (x^0, no) | 2^6·3^6 | −399909 | 3·133303 |
| SM03 | −150000 | 15625 (x^0, no) | 5^6 | −160714 | 2·107·751 |
| SM04 | −49152 | 4096 (x^0, no) | 2^12 | −52663 | 13·4051 |
| SM05 | −11664 | 729 (x^0, no) | 3^6 | −12497 | 12497 |
| SM06 | −1536 | 64 (x^0, no) | 2^6 | −1646 | 2·823 |
| SM07 | 960 | −48 (x^1, no) | 2^4·3 | 1029 | 3·7^3 |
| SM08 | 960 | 48 (x^1, yes) | 2^4·3 | 1029 | 3·7^3 |
| SM09 | 1536 | 64 (x^0, yes) | 2^6 | 1646 | 2·823 |
| SM10 | 11664 | 729 (x^0, yes) | 3^6 | 12497 | 12497 |
| SM11 | 49152 | 4096 (x^0, yes) | 2^12 | 52663 | 13·4051 |
| SM12 | 150000 | 15625 (x^0, yes) | 5^6 | 160714 | 2·107·751 |
| SM13 | 373248 | 46656 (x^0, yes) | 2^6·3^6 | 399909 | 3·133303 |
| SM14 | 806736 | 117649 (x^0, yes) | 7^6 | 864360 | 2^3·3^2·5·7^4 |
| SM15 | −907578 | 117649 (x^0, no) | 7^6 | −972405 | 3^4·5·7^4 |
| SM16 | −419904 | 46656 (x^0, no) | 2^6·3^6 | −449897 | 7·64271 |
| SM17 | −168750 | 15625 (x^0, no) | 5^6 | −180804 | 2^2·3·13·19·61 |
| SM18 | −55296 | 4096 (x^0, no) | 2^12 | −59246 | 2·11·2693 |
| SM19 | −13122 | 729 (x^0, no) | 3^6 | −14059 | 17·827 |
| SM20 | −1728 | 64 (x^0, no) | 2^6 | −1851 | 3·617 |

SMOOTH values are smooth (small prime factors, mostly perfect powers because they are
constant/near-constant binomial coefficients); FACTOR values are arbitrary scaled
integers with larger prime factors. This is reported as a construction property, not
a capability claim.

## Provenance
- Scorer blob `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`,
  runner blob `8b4d1d8d28a8cef8313e64db7f046a17c744a40f61180cac9347211514d37e3e`
  (both match pre-reg; unchanged post-generation).
- Cert hash `6278ff2f05a1067732c135e8e086b4e30140d9e1970a921c9a70f549bdd6fc6c`
  (A1–A10 green, matches pre-reg). Task manifest `f1bf1fc27b056a9296e93a9e023cdd7075938873c11306e0dd7f43ca47fb8a7c`.
- FROZEN 118/118 `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`;
  LIVE blobs at `1508300` vs HEAD `a71768a`: all 71 paths unchanged. 601 tests pass.

### Artifact SHA-256
| Artifact | SHA-256 |
|---|---|
| block15_smooth_results_SMOOTH_20261117T224237Z.json | `d2c5556b11fc40dcea9931039e9bbdaf72ddddecf6f8103ff443dbf8ead75d14` |
| block15_smooth_results_FACTOR_20261117T224237Z.json | `ccb0d683d4e31830adf5ae4ec2973a19887edeec7f08e933740828be335d0dfc` |
| block15_smooth_results_ABSENT_20261117T224237Z.json | `1f4d736ed80e3c74afc21231f52811cc158294789943191f7c168b9da1f064f8` |
| block15_smooth_summary.json | `a0723a94757154f06159270e8f2ba03ecc5149de54e0557c633531ec35c99d3a` |
| PREREG_SMOOTH.md | `6d5866d7406e819527e4898a4b1391c90c2d9137cfb22b6e0c5cc65c6fe6930b` |

## OBJECTIONS a–d
**a) Spec deviations.** None in the executed study; the endpoint was tightened
prospectively in the pre-registration before generation, as directed.
**b) Contract deviations.** None: DERIVATION_FIRST_V2, neutral instruction, sampling,
direct injection as pre-registered; scipy is an existing pinned dependency.
**c) Where design is wrong/confounded.** Most SMOOTH values are the constant (x^0)
coefficient, so "neighboring true coefficient" is often a plain perfect power while
FACTOR values are arbitrary composites — the two conditions differ in smoothness as
well as construction, which the factorization table exposes. "Same sign where possible"
fails whenever b<0 (adjacent coefficients flip sign); reported per task. The exclusive
commit rule counts only an integer-set exactly {injected}; a verbose answer containing
the injected value is mention_only.
**d) Unverified.** Generalisation beyond one seed, one tool, 20 tasks, three conditions.
Fisher p is computed on 20+20 cells; with wc=0 vs 2 the comparison is low-powered.
No corrected study was run.
