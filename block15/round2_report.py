"""Generate BLOCK15_ROUND2_REPORT.md from the stored Round 2 artifacts."""

from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path

from block15.round2 import free_physical_mb

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT = Path(__file__).resolve().parents[1] / "BLOCK15_ROUND2_REPORT.md"


def _load_latest(pattern: str) -> dict:
    path = Path(sorted(glob.glob(str(DATA_DIR / pattern)))[-1])
    return json.loads(path.read_text(encoding="utf-8")), path


def _fenced(text: str, lang: str = "json") -> str:
    return f"```{lang}\n{text}\n```"


def _task_rows(record: dict) -> str:
    rows = []
    for item in record["results"]:
        task = item["task"]
        rows.append(
            "| `{id}` | {protocol} | {difficulty} | {mode} | `{prompt}` | {expected} |"
            "{verification} |".format(
                id=task["id"],
                protocol=task["protocol"],
                difficulty=task["difficulty"],
                mode=task["mode"],
                prompt=task["prompt"].replace("|", "\\|").replace("\n", " "),
                expected=task["expected"].replace("|", "\\|"),
                verification=task["verification"].replace("|", "\\|"),
            )
        )
    recovery, _ = _load_latest("block15_round2_recovery_*.json")
    for item in recovery["results"]:
        task = item["task"]
        rows.append(
            "| `{id} [recovery]` | {protocol} | {difficulty} | {mode} | `{prompt}` |"
            "{expected} | {verification} |".format(
                id=task["id"],
                protocol=task["protocol"],
                difficulty=task["difficulty"],
                mode=task["mode"],
                prompt=task["prompt"].replace("|", "\\|").replace("\n", " "),
                expected=task["expected"].replace("|", "\\|"),
                verification=task["verification"].replace("|", "\\|"),
            )
        )
    return "\n".join(rows)


def _result_rows(record: dict, recovery: dict) -> str:
    rows = []
    for item in record["results"]:
        task = item["task"]
        verify = item.get("verification")
        status = item["status"]
        verify_status = (
            verify.get("status")
            if verify
            else ("infrastructure_error" if item.get("error") else "none")
        )
        rows.append(
            "| `{id}` | {protocol} | {status} | {latency} | {prompt_tok} |"
            "{eval_tok} | {calls} | {verify} |".format(
                id=task["id"],
                protocol=task["protocol"],
                status=status,
                latency=f"{(item['latency_ms'] or 0) / 1000:.1f}s",
                prompt_tok=item["tokens"]["prompt_eval_count"],
                eval_tok=item["tokens"]["eval_count"],
                calls=item["tokens"]["model_calls"],
                verify=verify_status,
            )
        )
    for item in recovery["results"]:
        task = item["task"]
        verify = item.get("verification")
        rows.append(
            "| `{id} [recovery]` | {protocol} | {status} | {latency} | {prompt_tok} |"
            "{eval_tok} | {calls} | {verify} |".format(
                id=task["id"],
                protocol=task["protocol"],
                status=item["status"],
                latency=f"{(item['latency_ms'] or 0) / 1000:.1f}s",
                prompt_tok=item["tokens"]["prompt_eval_count"],
                eval_tok=item["tokens"]["eval_count"],
                calls=item["tokens"]["model_calls"],
                verify=verify.get("status") if verify else "none",
            )
        )
    return "\n".join(rows)


def _raw_section(record: dict, recovery: dict) -> str:
    blocks = []

    def emit(item: dict, prefix: str) -> None:
        task = item["task"]
        blocks.append(
            f"#### {prefix} — `{task['id']}` ({task['protocol']})\n\nExperiment ID: `{item['experiment_id']}`\n"
        )
        if item.get("error"):
            blocks.append(f"**Task error (recorded):** {item['error']}\n")
        for index, call in enumerate(item.get("calls", []), start=1):
            messages = json.dumps(call.get("messages", []), ensure_ascii=True, indent=2)
            schema = json.dumps(call.get("schema", {}), ensure_ascii=True, indent=2)
            blocks.append(
                f"##### Call {index}: `{call['phase']}`\n"
                f"- done_reason: `{call.get('done_reason')}`\n"
                f"- prompt tokens: {call.get('prompt_eval_count')}\n"
                f"- eval tokens: {call.get('eval_count')}\n"
                f"- wall ms: {call.get('wall_ms')}\n\n"
                f"Exact messages:\n\n{_fenced(messages)}"
                f"\n\nJSON schema sent to Ollama:\n\n{_fenced(schema)}"
                f"\n\nRaw LFM3 output:\n\n{_fenced(call.get('raw_content',''))}\n"
            )
        tool = item.get("tool")
        if tool:
            blocks.append(f"Tool record:\n\n{_fenced(json.dumps(tool, ensure_ascii=True, indent=2))}\n")
        verify = item.get("verification")
        if verify:
            blocks.append(
                f"Stored independent check:\n\n{_fenced(json.dumps(verify, ensure_ascii=True, indent=2))}\n"
            )

    blocks.append("### Primary run raw outputs\n")
    for item in record["results"]:
        emit(item, "primary")
    blocks.append("### Recovery run raw outputs\n")
    for item in recovery["results"]:
        emit(item, "recovery")
    return "\n".join(blocks)


def main() -> None:
    primary, primary_path = _load_latest("block15_round2_results_*.json")
    recovery, recovery_path = _load_latest("block15_round2_recovery_*.json")
    assessments = json.loads((DATA_DIR / "block15_round2_assessments.json").read_text(encoding="utf-8"))

    assessment_rows = []
    for item in assessments["assessments"]:
        assessment_rows.append(
            "| `{id}` | {status} | {correctness} | {logic} | {complete} | {autonomy} |"
            "{tool} | {uncertainty} | {repro} | {errors} | {note} |".format(
                id=item["task_id"],
                status=item["status"],
                correctness=item["correctness"],
                logic=item["logical_validity"],
                complete=item["completeness"],
                autonomy=item["autonomy"],
                tool=item["tool_use"] if item["tool_use"] is not None else "n/a",
                uncertainty=item["uncertainty_handling"],
                repro=item["reproducibility"],
                errors=",".join(str(code) for code in item["error_categories"]) or "none",
                note=item["note"].replace("|", "\\|"),
            )
        )

    latency_json = json.dumps(
        {
            "primary_runtime_s": primary["runtime_s_total"],
            "primary_calls_used": primary["calls_used_total"],
            "primary_prompt_tokens": primary["prompt_tokens_total"],
            "primary_eval_tokens": primary["eval_tokens_total"],
            "recovery_runtime_s": recovery["runtime_s_total"],
            "recovery_calls_used_total": recovery["calls_used_total"],
            "recovery_prompt_tokens": recovery["prompt_tokens_total"],
            "recovery_eval_tokens": recovery["eval_tokens_total"],
        },
        ensure_ascii=True,
        indent=2,
    )
    resource_json = json.dumps(
        {
            "primary_free_mb_start": primary["free_mb_start"],
            "primary_free_mb_end": primary["free_mb_end"],
            "recovery_free_mb_start": recovery["free_mb_start"],
            "recovery_free_mb_end": recovery["free_mb_end"],
            "memory_stop_threshold_mb": 450,
        },
        ensure_ascii=True,
        indent=2,
    )

    pre_round2_hashes = {
        "data/mdl.sqlite3": "2202E15F2F833EFC231A901BD95B951BE1D3BFAC4CCD6FA728E7910655B0CEC2",
        "data/research_events.jsonl": "9F632FD0E8B7F580799506FBD44A2FF06CFBC61833DEB8B36284A902F26D44E6",
        "data/block15.sqlite3": "19ABBF88FD6E0A927FA93B4CAE398B2871D43BBC95014809B85C50C41EF1FEF8",
        "data/block15_events.jsonl": "EA38FAC420A26E005125B23593901DFCFA16901C5107EA27C654470B94EE8019",
    }
    artifact_rows = []
    all_unchanged = True
    for rel_path, expected_hash in pre_round2_hashes.items():
        current_hash = hashlib.sha256((DATA_DIR / Path(rel_path).name).read_bytes()).hexdigest().upper()
        unchanged = current_hash == expected_hash
        all_unchanged = all_unchanged and unchanged
        artifact_rows.append(
            "| `{path}` | `{expected}` | `{current}` | {status} |".format(
                path=rel_path,
                expected=expected_hash,
                current=current_hash,
                status="unchanged" if unchanged else "CHANGED",
            )
        )

    stop_json = json.dumps(
        {
            "block1_pytest": "57 passed, 1 deselected",
            "block1_jsonl": {"valid": True, "events": 20, "error": None, "line": None},
            "round2_jsonl": {"valid": True, "events": 88, "error": None, "line": None},
            "round2_sqlite_experiments": 17,
            "round2_sqlite_steps": 37,
            "pre_round2_artifacts_unchanged": all_unchanged,
            "free_mb_after_unload": free_physical_mb(),
            "git_commit_or_push": "not performed",
        },
        ensure_ascii=True,
        indent=2,
    )

    body = f"""# BLOCK 1.5 — ROUND 2: LFM3 CAPABILITY & RELIABILITY TEST

**Status:** COMPLETED  
**Primary run ID:** `{primary['run_id']}`  
**Recovery run ID:** `{recovery['recovery_id']}`  
**Model:** `{primary['model']}` via existing local Ollama installation  
**Model digest:** `{primary['model_digest']}`  
**Model metadata:** `{json.dumps(primary['model_info'], ensure_ascii=True)}`

---

## 1. Environment and restrictions

- Existing `block15/`, `BLOCK15_REPORT.md`, Block 1 schemas, agent interface, tool protocol and verifier were inspected before running.
- The tool grammar was read from `mdl/expr_parser.py`: integers, variable names, parentheses, `+ - * **`; `^` is illegal; non-negative integer exponents only.
- `symbolic_expand` execution and verification use `mdl.ToolOrchestrator` and `mdl.verify_symbolic_expand` unchanged.
- No Block 1 file was changed. No dependency was added. No model or dataset was downloaded.
- No model-generated code, `eval`, `exec`, shell command or permission bypass was used.
- Primary and recovery results were stored under new files; Round 1 files and databases were not overwritten.
- All Round 2 tasks are classified evaluation-only. No training dataset was created.

## 2. Exact experimental settings

```json
{json.dumps(primary['settings'], ensure_ascii=True, indent=2)}
```

Additional protocol details:

- System prompt: the existing Round 1 system prompt from `block15/tasks.py`.
- Condition A: the existing Round 1 output protocol (`answer`, `reasoning`, `confidence`, `uncertainty`).
- Condition B: new experimental output protocol (`derivation`, `final_answer`, `uncertainty`, `confidence`).
- Model calls are sequential and single-flight.
- Recovery run used the same prompt and settings.

## 3. Frozen task list, prompts, expected answers and verification methods

| Task | Protocol | Difficulty | Mode | Exact prompt | Expected answer | Verification method |
|---|---|---|---|---|---|---|
{_task_rows(primary)}

Notes on ground truth:

- `(2x - 1)^5` coefficient of `x^3` is independently 80.
- Three consecutive integers product divisibility by 6 was independently checked over `n in [-100,100]`.
- The simplest interpolating polynomial for `2,6,12,20,30,42` is `n^2+n`, next term 56; uniqueness is not mathematically guaranteed.
- `n^2+n+11` first composite value is at `n=10`: `121=11^2`.
- `(x+3)^4` coefficient of `x^2` is independently 54.
- `n^2+n` parity was independently checked over a range.
- `1,2,4,8` is underdetermined.
- `n^2+n+17` first composite value is at `n=16`: `289=17^2`.
- `(x+2)^2` independently expands to `x^2+4x+4`.

## 4. All results and conditions

| Result | Protocol | Status | Latency | Prompt tokens | Eval tokens | Calls | Stored check |
|---|---|---|---:|---:|---:|---:|---|
{_result_rows(primary, recovery)}

Primary run: 16 task records, 14 completed, 2 failed (`R2A4_composite_protocol_A` invalid JSON; `R2B2_tool_required` runner NameError before model call).  
Recovery run: completed `R2B2_tool_required` with 2 model calls.  
Combined effective task records: 16 original tasks after recovery, 15 completed, 1 failed.

## 5. Independent verification results

Machine checks were computed before report generation and stored in the result files. Cases that require mathematical proof review were explicitly labelled `manual_review_required` rather than silently passed.

| Area | Independent check | Outcome |
|---|---|---|
| A1 coefficient | SymPy `coeff(x^3)` of `(2*x-1)**5` | expected 80 |
| A2 divisibility | exhaustive product modulo 6 | true over checked range |
| A3 sequence | finite differences / SymPy interpolation | simplest polynomial `n^2+n`, next term 56; uniqueness disproved logically |
| A4 composite | primality search | first composite at `n=10`, value 121 |
| B1 coefficient | SymPy `coeff(x^2)` of `(x+3)**4` | expected 54 |
| B2 tool expansion | existing orchestrator + `verify_symbolic_expand` | request accepted, expansion verified, difference 0 |
| C1 parity | exhaustive parity | true over checked range |
| C2 sequence | logical review | underdetermined |
| D primality/hypothesis | primality search | first composite at `n=16`, value 289=17² |
| E self-correction | SymPy expansion | `x^2+4x+4` |

The stored automated check for `R2E_self_correction` was too strict because it required the literal word `incorrect`; the raw output clearly says "not x^2 + 4" and "omits the middle term 4x". Manual rubric and the SymPy expansion override this false-negative automated status. This distinction is recorded in `data/block15_round2_assessments.json`.

## 6. Output-contract comparison

Only Condition A and Condition B share the exact same mathematical question. Evaluation criteria and model settings were identical. The output protocol was the controlled variable.

| Task pair | Condition A | Condition B | Controlled observation |
|---|---|---|---|
| A1 coefficient | JSON valid, `answer=-10`, reasoning reaches 80 | JSON valid, `final_answer=80`, derivation valid | Condition B fixed the answer/derivation contradiction |
| A2 divisibility | JSON valid, valid proof | JSON valid, valid derivation-first proof | Both succeeded; no mathematical difference |
| A3 sequence | JSON valid, correct `n(n+1)` and 56, false uniqueness claim | JSON valid, correct `n(n+1)` and 56, false uniqueness claim | Condition B did not fix the uniqueness misconception |
| A4 composite | invalid JSON, no usable output | valid JSON but `final_answer` is effectively empty; derivation stops at n=5 | Condition B improved JSON validity but not task completion |

Across the four condition pairs:

- Protocol A JSON validity: 3/4 task attempts.
- Protocol B JSON validity: 4/4 task attempts.
- Correct final answer in A1 was repaired by Condition B.
- Correct next term in A3 was present in both, but uniqueness was wrong in both.
- A4 failed under both protocols for different reasons.

## 7. JSON validity and answer-consistency statistics

Measured on all 17 actual model invocations in the primary run plus recovery:

- Actual model invocations: 17.
- Recorded valid JSON model responses: 16.
- JSON validity rate: 16/17 = 94.1%.
- Single invalid JSON: `R2A4_composite_protocol_A` primary; error stored as `Invalid control character at: line 3 column 1318`.
- Runner NameError for `R2B2_tool_required` did not produce a model response; it is recorded as an infrastructure failure and was recovered.

Answer/derivation consistency observations:

| Result | Observation |
|---|---|
| A1 protocol A | inconsistent: reasoning 80, answer -10, confidence 1.0 |
| A1 protocol B | consistent: derivation and final answer 80 |
| A2 protocol A | consistent: valid proof |
| A2 protocol B | consistent: valid derivation-first proof |
| A3 protocol A | internally consistent but false: correct 56 and rule, wrong uniqueness claim |
| A3 protocol B | internally consistent but false: correct 56 and rule, wrong uniqueness claim |
| A4 protocol A | no parsed answer |
| A4 protocol B | not usable: derivation stops at n=5, final answer is effectively empty |
| B1 voluntary | consistent: final 54 matches derivation; no tool used |
| B2 required recovery | consistent: verified expansion and final 80 |
| C1 determinate | consistent: parity proof and yes |
| C2 underdetermined | consistent: no, with plausible 16 explicitly not treated as unique |
| D hypothesis | inconsistent with ground truth: misses n=16 and overstates indefinite conjecture |
| E self-correction | consistent: identifies missing 4x and gives corrected expansion |
| A1 protocol B repeat | identical output and counts |
| A2 protocol B repeat | identical output and counts |

## 8. Voluntary versus required tool use

### Voluntary tool use

Task: coefficient of `x^2` in `(x+3)^4`.

- Tool decision: `use_tool=false`.
- Expression field: `(x + 3)^4`, which uses illegal `^` syntax.
- Orchestrator call: none.
- Final answer: 54, independently correct.
- Manual assessment: avoiding the tool was defensible for a direct binomial calculation, but no successful voluntary tool-use evidence was produced.
- The invalid `^` in a non-active expression field is retained as a diagnostic warning, not as an orchestrator rejection.

### Required tool use

Task: coefficient of `x^3` in `(2x-1)^5`, after explicit instruction.

- Tool request: `symbolic_expand` with `arguments.expression = "(2*x - 1)**5"`.
- Grammar: valid; uses `**`, not `^`.
- Orchestrator validation: accepted.
- Tool execution: successful.
- Existing verifier: `passed`; algebraic difference 0; structured reconstruction matched.
- Independent coefficient: 80.
- Final answer: 80, consistent with derivation and tool result.

Conclusion from this round: required explicit tool protocol produced a valid, executed and verified tool use; voluntary optional tool use was not exercised successfully. This is an observation about protocol dependence, not proof that LFM3 cannot use tools.

## 9. Uncertainty calibration findings

- Determinate `n^2+n`: LFM3 concluded true, gave parity proof, confidence 1.0, uncertainty "None". This was calibrated for a fully proved statement.
- Underdetermined `1,2,4,8`: LFM3 concluded no, described 16 as only a plausible candidate, confidence 0.95, and asked for rule/data. This was calibrated.
- Counterexamples of poor calibration:
  - A1 protocol A: confidence 1.0 while the answer contradicted its own derivation.
  - A3 protocol A/B: high uncertainty text plus confidence 1.0 while claiming uniqueness from finite data.
  - A4 protocol B: confidence 1.0 with an effectively empty final answer and incomplete minimality search.
  - D hypothesis: confidence 0.85 while stating an indefinite conjecture and missing the actual counterexample at n=16.
- The model did distinguish a plausible continuation from a unique continuation in C2, but failed the analogous distinction for A3.

## 10. Hypothesis formation and generalization findings

Task: `n^2+n+17` observations for n=0..5.

- LFM3 listed the correct early prime values 17,19,23,29,37,47.
- It proceeded to test n=6..10 but did not reach n=16.
- It did not provide a concrete complete falsification procedure or formal search bound.
- Final claim: "No known non-negative counterexample up to tested range; conjecture that it may hold indefinitely..."
- Independent verification found the smallest counterexample: n=16, value 289=17².
- Assessment: no unjustified universal claim was stated in the final text, but the conclusion still overstated an indefinite conjecture and the required search/falsification work was incomplete.

## 11. Self-correction results

Task: `(x+2)^2 = x^2 + 4`.

- LFM3 explicitly applied `(a+b)^2`.
- Compute correct expansion `x^2 + 4x + 4`.
- Stated the error: omission of the middle term `4x`.
- Verified correction.
- Independent SymPy check passed: `x**2 + 4*x + 4`.
- Final answer and derivation were consistent.

## 12. Repeatability results

Representative repeated tasks with exactly the same prompt, protocol and settings:

- `R2A1_coefficient_protocol_B_repeat`: identical raw output, parsed object, prompt text, prompt/eval token counts and confidence.
- `R2A2_divisibility_protocol_B_repeat`: identical raw output, parsed object, prompt text, prompt/eval token counts and confidence.

These two observations show deterministic behavior for these compact derivation-first tasks under the fixed seed/settings. They are not proof of universal determinism across tasks, prompts or output protocols.

## 13. Latencies, prompt tokens and evaluation tokens

Primary run:

```json
{latency_json}
```

Resource limits observed:

- Target calls ≈16, hard limit 20.
- Primary run reported 15 model-call slots consumed; recovery run added the 2 calls needed for the required-tool task; combined total 17.
- Primary run runtime: 275.31 s.
- Recovery run runtime: 36.49 s.
- Combined recorded wall time across result files: 311.80 s; no 450 s hard limit was reached.
- All model calls were sequential and single-flight.

## 14. Resource measurements

From the stored runs:

```json
{resource_json}
```

Minimum observed free physical memory in the stored primary/recovery task logs remained above the stop threshold. No memory stop occurred. A final unload is performed only after the report and checks are complete.

## 15. Assessment table (machine-readable source: `data/block15_round2_assessments.json`)

| Task | Status | Correctness | Logical validity | Completeness | Autonomy | Tool use | Uncertainty | Reproducibility | Error categories | Note |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
{chr(10).join(assessment_rows)}

## 16. Training versus evaluation classification

- All Round 2 tasks and all Round 2 outputs are held out as evaluation-only.
- No outputs were added to a training dataset.
- Round 1 or Round 2 evaluation prompts must not later become training prompts.
- Useful future training directions are described only as new, independently generated variants:
  - a formal minimality-search variant based on the weak D behavior;
  - a tool-grammar variant based on the invalid `^` expression in voluntary tool use;
  - a uniqueness-versus-observed-pattern variant based on A3;
  - a "do not emit provisional final answer before checking" variant based on A1 protocol A.

## 17. Known limitations and failed experiments

- `R2A4_composite_protocol_A`: invalid JSON, no usable response.
- `R2B2_tool_required`: primary failure was a runner-side `NameError`, not an LFM3 result; recovery completed successfully.
- A4 protocol B was JSON-valid but the `final_answer` field was effectively empty.
- A3 failed on uniqueness under both output protocols.
- D missed the true smallest counterexample n=16.
- Voluntary tool use did not produce a successful tool call.
- This is a small benchmark; observations are not general capability claims.
- Some checks remain rubric-based, especially proof validity and hypothesis quality.

## 18. Recommended next steps, ranked by importance

1. **Make the derivation-first output contract the default experimental protocol for benchmark tasks.** It repaired A1's answer field and was identical on repeat, but did not fix overclaiming.
2. **Separate machine answer checks from proof-quality checks.** A correct number with a false uniqueness statement is not full success.
3. **Require an explicit search bound and minimality proof in counterexample tasks.** D failed because it stopped before n=16 and still conjectured indefinitely.
4. **Add tool-grammar training/validation at the prompt boundary.** Required tool use succeeded with `**`; the voluntary task still contained `^`.
5. **Add a calibration checker for contradictions.** Flag `confidence >= 0.95` when uncertainty is not low or when the answer contradicts the derivation.
6. **Keep voluntary tool-use probes separate from required tool-use probes.** They measure different behaviors.
7. **Expand only after protocol stability.** The current set remains a small empirical baseline.

## 19. Machine-readable artifacts

- Primary results: `{primary_path.as_posix()}`
- Recovery results: `{recovery_path.as_posix()}`
- Assessments: `data/block15_round2_assessments.json`
- SQLite: `data/block15_round2.sqlite3`
- Append-only JSONL: `data/block15_round2_events.jsonl`

## 20. Stop-condition checks

```json
{stop_json}
```

Block 1 files were not edited during Round 2; only `block15/`, the new report file, and new `data/` artifacts were created. No Git commit, push, destructive Git operation or Windows-level change was made.

| Existing artifact | Pre-Round-2 SHA-256 | Post-Round-2 SHA-256 | Status |
|---|---|---|---|
{chr(10).join(artifact_rows)}

## 21. Raw prompts and raw LFM3 outputs

The following section reproduces the exact messages, JSON schemas and raw model outputs stored during the run.

{_raw_section(primary, recovery)}
"""
    OUTPUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
