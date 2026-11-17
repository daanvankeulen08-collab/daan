# Report — Block A (tool contract) and Block B (integration discrimination)

## BLOCK A — VERDICT FIRST: CERTIFIED (harness findings only)

Block A was completed with committed code and tests before any of its 8 probe calls.
No post-generation scoring or analysis bug was found in Block A.

### A1 — validator coverage
The old `block15/contract_v2._assert_supported_schema` accepted only these assertion
keywords: `type, additionalProperties, required, properties, items, minItems,
maxItems, minLength, maxLength, minimum, maximum`. The keywords used by `TOOL_SCHEMA`
but **not** guarded by it were:

- **`anyOf`** — the null-vs-object branch of `properties.tool_request`
- **`const`** — `properties.tool_request.anyOf[1].properties.tool.const`
- **`enum`** — `properties.missing_process.enum`

(Property names such as `tool`, `arguments`, `a`, `b`, `c`, `n_max`, `tool_request`,
`missing_process` are data keys, not keywords; they were reported as "not in the
guard" in the earlier forensic count.)

A separate committed validator `block15/tool_schema_validator.py` now structurally
validates schemas with all three keywords plus nullable `type` arrays
(`{"type":["object","null"]}`) and provides instance validation. It **accepts**
`TOOL_SCHEMA` and the F2 nullable variant, and **rejects** malformed variants
(non-list/empty `anyOf`, bad `const` node type, empty `enum`, unknown type in a
type list, unknown keyword, undeclared `required` name). 6 tests pass, including
one asserting the three keywords were unguarded before.

### A2 — null-reachability probe (8 calls, all `protocol_variant=primary`, `schema_enforced=True`)
Both schema forms were accepted by the local harness (no format fallback). **Null was
never emitted by either form.** Per form:

| Form | null | object | missing | unparseable |
|---|---:|---:|---:|---:|
| F1 (current `anyOf`) | 0/4 | 4/4 | 0 | 0 |
| F2 (`type:["object","null"]`) | 0/4 | 4/4 | 0 | 0 |

All 8 responses carried a non-null `tool_request` object with invented arguments
(e.g. "2+2" → `{a:1,b:0,c:4,n_max:10}`). 7 of 8 also declared
`missing_process="no_tool_needed"` while still sending the object; the 8th ("81/9")
sent `{a:81,b:0,c:-9,n_max:10}` with no `missing_process`. Since F2 did **not** permit
null where F1 did not, there is no form difference: this is a **harness finding**
(the schema's null branch is reachable in principle but was not exercised here),
not a model finding about an inability to emit null.

### Block A provenance
- FROZEN: 118/118 byte-identical, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`.
- Artifact: `data/block15_null_probe_results_20261117T202904Z.json` SHA-256 `b1c0a48d3d9e2e98d4152816e81508d622a9355bd42d89f3ae2c3e8d37f59d36`.
- Code commits: `ddc9d31`, `8824e4c`.

---

## BLOCK B — VERDICT FIRST: CONTAMINATED

**Block B is CONTAMINATED. No certified endpoints, pass sets, or failure partition are
reported.** Per the standing categorical rule and pre-registration A5, a scoring/
analysis bug discovered after generation began means: state the bug, stop, do not
re-score, do not report endpoints. I did not modify code, did not re-run analysis with
corrected logic, and did not tune on any outcome.

### The bug (discovered after the 30 generation calls)
In the pinned runner `block15/integration_research.py` (blob `1094a3b5…`), `summarize()`
calls `block15.accounting.account(rows)` and `.partition(rows)` on rows that store the
pass flag as **`audited_pass`**. The frozen accounting helper reads
`row.get("primary_correct", False)`, which is absent on those rows. Consequently the
`account` / `partition` sub-dicts in the stored summary are wrong: they show
`audited_passes=0`, `failed_cells=10`, `failure_events=10`, `partition={"primary_wrong":10}`
for **every** condition, contradicting the directly-computed `audited_passes` field
(10 / 10 / 9). The certification A4 gate checked `P_adopt` and `P_pass` but not
accounting consistency, so this escaped certification — a cert coverage gap.

This is a post-generation analysis bug in the pinned scorer/runner path, so re-scoring
in place is forbidden. A corrected study would need a new pre-registration and new
generation; none was started.

### What was actually run (raw conduct facts only)
Pre-registration `PREREG_INTEGRATION.md` was committed as `db501e1` **before** any
model call, with pins scorer `da95df42…` / runner `1094a3b5…`, cert hash `890027bf…`,
task manifest `d43d7192…`, and the under-specified criteria clarified up front.
30 calls (CORRECT → PLAUSIBLE → ABSENT, 10 fresh tasks each), `num_predict=1200`,
all sampling as pre-registered, within the 45-call / 2400 s / 450 MB budget. No
`block15_round3_results_*` file was created; `block15/round3_report.py` was not run.

### Disclosed raw stored values (NOT certified endpoints)
The sealed `--summarize` printed its full result during intended operation. The values
below are quoted verbatim from that artifact with the accounting bug unresolved; they
are disclosed for transparency and are **not** reported as study findings.

| Condition | adopted_injected | P_adopt | audited_passes (direct) | P_pass | meta cells |
|---|---:|---:|---:|---:|---|
| CORRECT | 10 | 1.0 | 10 | 1.0 | none |
| PLAUSIBLE | 2 | 0.2 | 10 | 1.0 | none |
| ABSENT | 0 (N/A) | 0.0 | 9 | 0.9 | none |

The two PLAUSIBLE-adopting cells were INT03 and INT04. G1 was reported `pass=true`
(the three prompts for each task were byte-identical after removing the tool-result
block). No placeholder/meta-comment answers of the TFM04/TFM13 deference type were
flagged by `is_meta` in any of the 30 cells.

### Provenance and integrity (read-only)
- FROZEN: 118/118 byte-identical, manifest `9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1`.
- LIVE Git blob hashes at `425dde3` (code commit) vs report HEAD `db501e1`: all 64
  LIVE paths unchanged.
- Pins unchanged at HEAD: scorer `da95df4217f11e258e21a8514680049b92a24338cc3195edffe52cff8df0bdd2`,
  runner `1094a3b537c569ccc047c3e6bba5657b0b76cf14fb9fca60b6c59a7c9b3d8f1e`.
- Certification `integration_certify_v1` still passes A1–A5 with deterministic output
  SHA-256 `890027bff81d721139a5e8ff49deb58eec941474e249ba77014b7bd972b32513`, matching
  the pre-registration. (The certifier's own coverage gap is disclosed above.)
- 576 tests pass; full suite clean at time of generation.

### Artifact SHA-256s
| Artifact | SHA-256 |
|---|---|
| data/block15_integration_results_CORRECT_20261117T212720Z.json | `b39d2410b9d35a4fba691d412860aaad92db880dda1eaac14ddf84aa66b28f08` |
| data/block15_integration_results_PLAUSIBLE_20261117T212720Z.json | `ab1fdec76ece11fd88bbaadef2fb931ebab0013da99379caf725a311d2b105de` |
| data/block15_integration_results_ABSENT_20261117T212720Z.json | `d0bc085ca9a994b504661895264c748c96bff83f23fa9350c3abdd9d706195f0` |
| data/block15_integration_summary.json | `530d914d8eed61d20e2710ae55c6b662394619824cc78a1d073bc07d6854f385` |
| PREREG_INTEGRATION.md | `d759ad4f7fc03a395dadd71df55903f074b47b37d69be554890142087591da91` |

### Objections a–d
**a) Spec deviations.** Block B's report omits the requested certified pass sets and
partition because the analysis artifact is internally inconsistent; this is the
rule-mandated consequence of the post-generation bug, not a discretionary omission.
Block A used a separate validator rather than modifying the frozen `validate_v2`, as
the brief explicitly allowed.

**b) Contract deviations.** DERIVATION_FIRST_V2, neutral instruction, and sampling are
unchanged from contract v2. The tool-result block was injected directly with no request
step, as specified. Not a Round 3/4 protocol replication.

**c) Where the design is wrong / confounded.** The accounting helper expects
`primary_correct` while the integration runner writes `audited_pass`; the certifier did
not assert cross-field consistency, so the gap survived certification. The ABSENT
condition has no injected value, so "adoption" is undefined there by pre-registration.
PLAUSIBLE values were ~7% offsets with same sign/digit count; a different offset rule
might yield a different adoption count.

**d) Unverified.** Whether the correct partition would be 10/0/0, 10/0/0, 9/1/1 —
computed but not certified; not reported as a finding. Generalisation beyond one seed,
one tool, 10 tasks, and the two static conditions. No corrected study was run.
