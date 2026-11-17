# Report — Tool-transfer V2: RUN CONTAMINATED

## 1. Verdict — stated first

**CONTAMINATED. No endpoints, no verdict matrix, no G1 verdict, no false-alarm rate, and no
pass counts are reported.**

A bug in the **pinned runner** (`block15/tool_transfer_research.py`) was discovered after
generation completed. The HARD RULE for this block is categorical:

> Any scoring/runner bug discovered after main-run generation starts => report CONTAMINATED,
> state the bug, stop. Do not re-score. Do not report endpoints. A corrected study requires a
> NEW pre-registration and NEW generation. This rule is categorical.

Applied strictly: I did not modify the runner or scorer, did not re-run analysis with corrected
logic, and report no endpoint derived from this run. The working tree is clean and matches the
pre-registration commit `f13f3fe`. A corrected study needs a new pre-registration and new
generation; none was started.

## 2. The bug

- **Location:** `block15/tool_transfer_research.py::summarize()` (runner wrapper), line 284.
- **Code:** `sha = scorer_blob_sha256()`
- **Cause:** the function is defined as `scorer_blob_hash()` (line 55); `scorer_blob_sha256`
  does not exist.
- **Observed failure:**
  ```
  NameError: name 'scorer_blob_sha256' is not defined. Did you mean: 'scorer_blob_hash'?
  ```
  raised when `--summarize` called the runner's `summarize()` after the run.
- **Why certification missed it:** `--certify` (and its fake-client dry-run) calls the
  **scorer's** `SC.summarize()` directly; it never executes the runner's `summarize()`
  wrapper where the typo lives. The certified scorer itself is intact — the bug is in the
  runner's hash-lookup line that precedes calling the scorer. This is a certification
  coverage gap, not a scoring-logic defect.
- **Note:** this same typo existed in the V1 runner and was disclosed then; it was
  inadvertently carried into the V2 code commit and pinned. That it recurs is a process
  failure, disclosed here rather than silently fixed.

## 3. Frozen code integrity (pinned at `fd8c944`, verified at HEAD)

- Scorer `block15/tool_transfer_score.py`: `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2` — **unchanged**, matches pin.
- Runner `block15/tool_transfer_research.py`: `dc1855081fa445516de29f627f49d590bb2be9665ad807ef9a9d2ace542887cf` — **unchanged**, matches pin.
- Both result files record `scorer_blob_sha256 = da95df42…` (the pinned scorer). No runner
  hash was stored in the result files.
- Certification output hash (pre-generation): `0ba59312150e93c749501ed7be27efe41d49cf495c88834f7097d79063c6c63f`.

## 4. What was actually run (raw conduct facts only)

- L0_REAL then L0_SHAM, single-flight; 30 tasks each, 2 calls/cell.
- `L0_REAL`: 60 calls, 828 s, 30 rows, stopped_early=False.
- `L0_SHAM`: 60 calls (120 cumulative), 1835 s, 30 rows, stopped_early=False.
- Total 120 calls / ~1835 s, within the 130-call / 5400 s / 450 MB budget.
- These are direct read-only observations. **No** audited pass count, McNemar, false-alarm
  rate, G1 verdict, pass set, failure partition, or verdict-matrix entry is reported — all
  are scorer/analysis-derived and withheld under the HARD RULE.

## 5. Protected-manifest integrity (read-only)

- FROZEN: byte-identical, 118/118, manifest
  `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1` (matches baseline).
- LIVE Git-blob hashes at `f13f3fe` (pre-registration) vs report HEAD: all 55 LIVE paths
  unchanged.

## 6. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_tool_transfer_v2_results_L0_REAL_20261117T171157Z.json | `072a9b05a07b7eaa835df72378e2da74ca8d68f5cfac35da082ff867ed7e2b52` |
| data/block15_tool_transfer_v2_results_L0_SHAM_20261117T171157Z.json | `d0c4ed90ea825a44292e1f1d247f972b776b0289017e1d4c84a136b0cefe6996` |
| data/block15_tool_transfer_v2_summary.json | ABSENT (analysis never completed) |
| block15/tool_transfer_score.py (git blob) | `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2` |
| block15/tool_transfer_research.py (git blob) | `dc1855081fa445516de29f627f49d590bb2be9665ad807ef9a9d2ace542887cf` |
| PREREG_TOOL_TRANSFER_V2.md | `e8023cb4bb7111df0d7605ad6dc662bb17d6665e0aba78ed9611f6cad7191fdf` |

## 7. Limits
n=30, single seed, one tool; the tool supplies the answer. None of that is claimed here — the
run is contaminated. No capability, generalisation, or model-understanding claim follows.

## 8. Mandatory deviation and objection report

### a) Deviations from this spec
- The STEP 4 contents (G1 verdict, verdict matrix, false-alarm rate, funnel, conversion
  failures, pass sets, failure partition) are **not reported**, because the HARD RULE's
  contamination clause takes precedence. Deliberate, rule-mandated.
- Contamination is reported and generation stopped; a corrected run requires a new
  pre-registration and new generation, not started.

### b) Deviations from the reference contract
- Contract, tasks, sampling, tool and comparators were exactly as pre-registered in
  `f13f3fe`; no schema or sampling deviation. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded
- The runner's `summarize()` was never exercised by `--certify`, so a one-line NameError
  survived certification. Certification should have invoked the runner's `summarize()` on
  synthetic persisted records, not only the scorer's function.
- The same typo recurred from V1; carrying forward the runner without a targeted check of
  this exact call was a process error.
- Any decision to "just fix the one line and re-summarize" would recreate the ambiguity the
  HARD RULE forbids; it is not done.

### d) What I could not verify
- G1 byte-identity verdict, false-alarm rate, parameter accuracy, McNemar, pass sets, overlaps,
  and failure partition — all require the broken runner analysis path and are unverified.
- Whether the model selected the tool selectively or merely bound parameters — no endpoint
  was computed.
