# Report — Tool-transfer study: RUN CONTAMINATED

## 1. Verdict — stated first

**CONTAMINATED. No endpoints, no verdict matrix, no G1 verdict, and no pass counts are reported.**

A bug in the **frozen scorer** (`block15/tool_transfer_score.py`) was discovered **after
generation completed**. The standing HARD RULE for this block is explicit and categorical:

> Freeze the scorer and record its git blob hash in the pre-registration BEFORE any
> generation. If a scoring bug is discovered after generation, you MUST NOT re-score this
> run. Report the run as **CONTAMINATED**, state the bug, and stop. A corrected run requires
> a NEW pre-registration and NEW generation.

That rule was written specifically to prevent a repeat of the prior block, where a verdict
flipped after an unfavorable result. It is therefore applied strictly here: even though the
defect is a trivial aggregation error and per-cell scoring completed, the scorer is frozen
and pinned, and the rule forbids any post-generation fix-and-rescore. I did **not** modify
the scorer, did **not** re-run the analysis with corrected logic, and do **not** report any
endpoint derived from it. The working tree was restored so it matches the pre-registration
commit exactly (`git status --porcelain` empty).

A corrected study requires a **new pre-registration and new generation**; none was started.

## 2. The bug

- **Location:** `block15/tool_transfer_score.py::summarize()`, line 284.
- **Code:**
  ```python
  fa_ids = per["L0_REAL"]["requested_ids"] & {x.split("_")[0] for x in tnn}
  ```
- **Cause:** `per[...]["requested_ids"]` is produced at line 247 as
  `sorted(x.split("_")[0] for x in requested)`, i.e. a **list**. The `&` operator between a
  `list` and a `set` is not defined in Python.
- **Observed failure:**
  ```
  TypeError: unsupported operand type(s) for &: 'list' and 'set'
  ```
- **Effect:** the co-primary false-alarm-rate computation (and therefore the whole
  `summarize()` aggregation, which also contains G1 and the verdict matrix) cannot complete.
  No summary JSON was produced, and none will be produced for this run.
- **Discovery path:** `--summarize` was invoked once after the run finished; it raised the
  TypeError. A pre-existing runner-side NameError (`scorer_blob_sha256` vs `scorer_blob_hash`)
  was encountered first, fixed locally, then reverted so no post-generation source change
  remains; after the revert the frozen scorer's TypeError is the blocking, reported defect.

## 3. Frozen scorer integrity

- Pinned in `PREREG_TOOL_TRANSFER.md` (commit `3b9348e`, before generation):
  `d0da9ce3915713293848b72311201003c50ae34f4cc0497ea9f4ff3b2b5bd4ad`.
- Git blob SHA-256 of `block15/tool_transfer_score.py` at HEAD: **unchanged**, equals the
  pinned value. The scorer binary is exactly what was pre-registered; the bug was present
  in the frozen artifact from the start, not introduced after generation.

## 4. What was actually run (raw conduct facts only, no scoring/re-scoring)

- Conditions run single-flight: `L0_REAL` then `L0_SHAM`; 30 tasks each, 2 calls per cell.
- `L0_REAL`: 60 calls, 858 s, stopped_early=False, 30 cells stored.
- `L0_SHAM`: 60 calls (120 cumulative), 1899 s, stopped_early=False, 30 cells stored.
- Total 120 calls / ~1899 s, within the 130-call / 5400 s / 450 MB budget.
- Both result files record `scorer_blob_sha256 = d0da9ce3…` (the pinned value).
- These are direct read-only observations from the result files. **No** audited pass count,
  McNemar, false-alarm rate, G1 verdict, pass set, failure partition, or verdict-matrix entry
  is reported — all of those are scorer-derived and therefore withheld under the HARD RULE.

## 5. Protected-manifest integrity (read-only)

- FROZEN: **byte-identical**, 118/118 paths, manifest
  `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1` (matches baseline).
- LIVE before/after are Git blob hashes at `3b9348e` (pre-registration commit) vs report-time
  HEAD: all 54 LIVE paths unchanged; no "all unchanged" claim beyond this verified set.

## 6. Artifact SHA-256s

| Artifact | SHA-256 |
|---|---|
| data/block15_tool_transfer_results_L0_REAL_20261117T162603Z.json | `04c887fb2d1515a446491005c1cbbb46785e902d793ed4a6f31e0d76ead6188c` |
| data/block15_tool_transfer_results_L0_SHAM_20261117T162603Z.json | `8f333ca17ef2daad347c4aca932c19cad31a20e79caa78832fc5b51f07f202b0` |
| block15/tool_transfer_score.py (git blob, frozen) | `d0da9ce3915713293848b72311201003c50ae34f4cc0497ea9f4ff3b2b5bd4ad` |
| PREREG_TOOL_TRANSFER.md | `0dc085d146734d3edfed79010f563dc6b86d1e93a602795fb655293e2ad85bd3` |

## 7. Limits

n=30, single seed, one tool; the tool supplies the answer, so any eventual pass would show
tool selection/parameterisation, not unaided arithmetic. None of that is claimed here: the
run is contaminated. No capability, generalisation, or model-understanding claim follows.

## 8. Mandatory deviation and objection report

### a) Deviations from this spec
- The required endpoints/verdict matrix/G1 verdict/false-alarm rate are **not reported**,
  because the HARD RULE's contamination clause took precedence over STEP 3's normal report
  contents. This is a deliberate, rule-mandated deviation, not an omission.
- The contamination is reported and generation is stopped; a corrected run requires a new
  pre-registration and new generation, which was not started.

### b) Deviations from the reference contract
- Contract, tasks, sampling, tool and comparators were exactly as pre-registered in
  `3b9348e`; no schema or sampling deviation. Not a Round 3/4 protocol replication.

### c) Where the design is wrong or still confounded
- The single `list & set` line in the frozen scorer made the entire analysis un-runnable;
  this should have been caught by a dry-run of `summarize()` on synthetic records before
  freezing. It was not — a test-coverage gap in the pre-registration step.
- Any decision to later "just fix the two-character bug and re-summarize" would recreate the
  exact ambiguity the HARD RULE forbids; it is not done here.

### d) What I could not verify
- The G1 byte-identity verdict, false-alarm rate, parameter accuracy, McNemar, pass sets and
  failure partition — all require the broken scorer and are therefore unverified.
- Whether the model selected the tool selectively or merely bound parameters, since no
  endpoint was computed.
