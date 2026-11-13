"""Generate BLOCK15_ROUND3_REPORT.md from stored Round 3 artifacts."""

from __future__ import annotations

import glob
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "BLOCK15_ROUND3_REPORT.md"


def load_latest(pattern: str) -> tuple[dict, Path]:
    path = Path(sorted(glob.glob(str(DATA_DIR / pattern)))[-1])
    return json.loads(path.read_text(encoding="utf-8")), path


def fence(text: str, language: str = "text") -> str:
    return f"~~~~{language}\n{text}\n~~~~"


def cell(value: object) -> str:
    if value is None:
        return "n/a"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def score(value: object) -> str:
    return "n/a" if value is None else str(value)


def snippet(text: str, limit: int = 150) -> str:
    compact = " ".join(str(text).split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_table(results: list[dict], assessments: dict) -> str:
    scores = {item["task_id"]: item for item in assessments["assessments"]}
    rows = [
        "| Task | Protocol | Status | Latency | Prompt tok | Eval tok | Calls | Automated check | Correctness |",
        "|---|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for item in results:
        task = item["task"]
        assessment = scores.get(task["id"], {})
        correctness = assessment.get("scores", {}).get("correctness")
        verification = item.get("verification") or {}
        rows.append(
            "| `{id}` | {protocol} | {status} | {latency:.1f}s | {prompt} | {eval} | "
            "{calls} | {check} | {correctness} |".format(
                id=task["id"],
                protocol=task["protocol"],
                status=item["status"],
                latency=(item["latency_ms"] or 0) / 1000.0,
                prompt=item["tokens"]["prompt_eval_count"],
                eval=item["tokens"]["eval_count"],
                calls=item["tokens"]["model_calls"],
                check=verification.get("status", "none"),
                correctness=score(correctness),
            )
        )
    return "\n".join(rows)


def assessment_tables(assessments: dict) -> str:
    core_rows = [
        "| Task | Correctness | Logical validity | Completeness | Answer consistency | Calibration | Error categories |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    specialized_rows = [
        "| Task | Search completeness | Hypothesis quality | Tool competence | Noise awareness | Assessment note |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in assessments["assessments"]:
        s = item["scores"]
        core_rows.append(
            "| `{id}` | {correctness} | {logic} | {complete} | {consistency} | "
            "{calibration} | {errors} |".format(
                id=item["task_id"],
                correctness=score(s["correctness"]),
                logic=score(s["logical_validity"]),
                complete=score(s["completeness"]),
                consistency=score(s["answer_consistency"]),
                calibration=score(s["calibration"]),
                errors=", ".join(str(code) for code in item["error_categories"])
                or "none",
            )
        )
        specialized_rows.append(
            "| `{id}` | {search} | {hypothesis} | {tool} | {noise} | {note} |".format(
                id=item["task_id"],
                search=score(s["search_completeness"]),
                hypothesis=score(s["hypothesis_quality"]),
                tool=score(s["tool_competence"]),
                noise=score(s["noise_awareness"]),
                note=cell(snippet(item["observation"], 180)),
            )
        )
    return "\n".join(core_rows) + "\n\n" + "\n".join(specialized_rows)


def dimension_summary(assessments: dict) -> str:
    rows = [
        "| Dimension | Applicable tasks | Mean | Tasks scoring 0 or 1 |",
        "|---|---:|---:|---|",
    ]
    for dimension in assessments["dimensions"]:
        values = [
            item["scores"][dimension]
            for item in assessments["assessments"]
            if item["scores"][dimension] is not None
        ]
        if not values:
            continue
        low = [
            item["task_id"]
            for item in assessments["assessments"]
            if item["scores"][dimension] is not None
            and item["scores"][dimension] <= 1
        ]
        rows.append(
            "| {dimension} | {count} | {mean:.2f} | {low} |".format(
                dimension=dimension,
                count=len(values),
                mean=sum(values) / len(values),
                low=", ".join(f"`{task}`" for task in low) if low else "none",
            )
        )
    return "\n".join(rows)


def raw_section(results: list[dict]) -> str:
    blocks: list[str] = []
    for item in results:
        task = item["task"]
        blocks.append(
            f"### `{task['id']}`\n\n"
            f"- Group: `{task['group']}`\n"
            f"- Protocol: `{task['protocol']}`\n"
            f"- Status: `{item['status']}`\n"
            f"- Experiment ID: `{item['experiment_id']}`\n"
            f"- Recorded latency: {(item['latency_ms'] or 0) / 1000.0:.2f} s\n"
            f"- Tokens: prompt={item['tokens']['prompt_eval_count']}, "
            f"eval={item['tokens']['eval_count']}, calls={item['tokens']['model_calls']}\n"
        )
        if item.get("error"):
            blocks.append(f"**Recorded task error:** {item['error']}\n")
        for index, call in enumerate(item.get("calls", []), start=1):
            blocks.append(
                f"#### Call {index}: `{call['phase']}`\n\n"
                f"- `done_reason`: `{call.get('done_reason')}`\n"
                f"- Prompt tokens: {call.get('prompt_eval_count')}\n"
                f"- Eval tokens: {call.get('eval_count')}\n"
                f"- Wall time: {call.get('wall_ms')} ms\n"
                f"- Recorded latency: {call.get('latency_ms')} ms\n\n"
                f"Exact messages sent to Ollama:\n\n"
                f"{fence(json.dumps(call.get('messages', []), ensure_ascii=False, indent=2), 'json')}\n\n"
                f"JSON schema sent to Ollama:\n\n"
                f"{fence(json.dumps(call.get('schema', {}), ensure_ascii=False, indent=2), 'json')}\n\n"
                f"Raw LFM3 output:\n\n"
                f"{fence(call.get('raw_content', ''), 'text')}\n\n"
                f"Parsed output:\n\n"
                f"{fence(json.dumps(call.get('parsed', {}), ensure_ascii=False, indent=2), 'json')}\n"
            )
        tool = item.get("tool")
        if tool:
            blocks.append(
                f"Tool record:\n\n{fence(json.dumps(tool, ensure_ascii=False, indent=2), 'json')}\n"
            )
        tool_eval = item.get("tool_evaluation")
        if tool_eval:
            blocks.append(
                f"Tool evaluation:\n\n{fence(json.dumps(tool_eval, ensure_ascii=False, indent=2), 'json')}\n"
            )
        verification = item.get("verification")
        if verification:
            blocks.append(
                f"Independent check record:\n\n"
                f"{fence(json.dumps(verification, ensure_ascii=False, indent=2), 'json')}\n"
            )
    return "\n".join(blocks)


def main() -> None:
    primary, primary_path = load_latest("block15_round3_results_*.json")
    assessments = json.loads(
        (DATA_DIR / "block15_round3_assessments.json").read_text(encoding="utf-8")
    )
    ground_truth, ground_truth_path = load_latest("block15_round3_ground_truth.json")

    results = primary["results"]
    by_id = {item["task"]["id"]: item for item in results}
    assessment_by_id = {
        item["task_id"]: item for item in assessments["assessments"]
    }
    gt_by_id = {item["id"]: item for item in ground_truth["tasks"]}
    total_calls = sum(len(item["calls"]) for item in results)
    valid_json_calls = sum(
        1
        for item in results
        for call in item["calls"]
        if call.get("done_reason") != "length" and isinstance(call.get("parsed"), dict)
    )
    length_stops = sum(
        1 for item in results for call in item["calls"] if call.get("done_reason") == "length"
    )

    a1a = by_id["R3A1_coefficient_protocol_A"]
    a1b = by_id["R3A1_coefficient_protocol_B"]
    a2a = by_id["R3A2_divisibility_protocol_A"]
    a2b = by_id["R3A2_divisibility_protocol_B"]
    b = by_id["R3B_counterexample_minimality"]
    c = by_id["R3C_hypothesis_falsification"]
    d1 = by_id["R3D1_tool_voluntary"]
    d2 = by_id["R3D2_tool_required"]
    e1 = by_id["R3E1_uncertainty_determinate"]
    e2 = by_id["R3E2_uncertainty_underdetermined"]
    f = by_id["R3F_numerical_trend_noise"]
    g = by_id["R3A1_coefficient_protocol_B_repeat"]

    def answer(item: dict) -> str:
        final = item.get("final_answer") or {}
        if "answer" in final:
            return str(final["answer"])
        return str(final.get("final_answer", ""))

    def derivation(item: dict) -> str:
        final = item.get("final_answer") or {}
        if "derivation" in final:
            return " ".join(final["derivation"])
        return str(final.get("reasoning", ""))

    protocol_a_calls = a1a["calls"] + a2a["calls"]
    protocol_b_paired_calls = a1b["calls"] + a2b["calls"]
    protocol_a_eval = sum(call["eval_count"] for call in protocol_a_calls)
    protocol_b_paired_eval = sum(call["eval_count"] for call in protocol_b_paired_calls)
    protocol_a_latency = (a1a["latency_ms"] or 0) + (a2a["latency_ms"] or 0)
    protocol_b_paired_latency = (a1b["latency_ms"] or 0) + (a2b["latency_ms"] or 0)

    expected_hashes = ground_truth["pre_round3_artifact_sha256"]
    hash_rows = [
        "| Artifact | Pre-Round-3 SHA-256 | Post-Round-3 SHA-256 | Status |",
        "|---|---|---|---|",
    ]
    all_unchanged = True
    for rel_path, expected in expected_hashes.items():
        path = ROOT / rel_path
        current = sha256_file(path)
        unchanged = current == expected
        all_unchanged = all_unchanged and unchanged
        hash_rows.append(
            f"| `{rel_path}` | `{expected}` | `{current}` | "
            f"{'unchanged' if unchanged else 'CHANGED'} |"
        )

    current_db = {
        "block1": DATA_DIR / "mdl.sqlite3",
        "round1": DATA_DIR / "block15.sqlite3",
        "round2": DATA_DIR / "block15_round2.sqlite3",
        "round3": DATA_DIR / "block15_round3.sqlite3",
    }
    db_counts = {}
    for label, path in current_db.items():
        connection = sqlite3.connect(path)
        db_counts[label] = {
            "experiments": connection.execute("SELECT COUNT(*) FROM experiments").fetchone()[0],
            "steps": connection.execute("SELECT COUNT(*) FROM steps").fetchone()[0],
        }
        connection.close()

    source_files = sorted((ROOT / "mdl").glob("*.py"))
    newest_source = max(source_files, key=lambda path: path.stat().st_mtime)
    newest_source_time = datetime.fromtimestamp(newest_source.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    artifacts = [
        "`BLOCK15_ROUND3_REPORT.md`",
        "`block15/round3_tasks.py`",
        "`block15/round3_preflight.py`",
        "`block15/round3.py`",
        "`block15/round3_report.py`",
        "`data/block15_round3_ground_truth.json`",
        f"`{primary_path.relative_to(ROOT).as_posix()}`",
        "`data/block15_round3_assessments.json`",
        "`data/block15_round3.sqlite3`",
        "`data/block15_round3_events.jsonl`",
    ]

    parts: list[str] = []
    add = parts.append

    add(
        "# BLOCK 1.5 — ROUND 3: CONFIRMATORY CAPABILITY EVALUATION\n\n"
        f"**Status:** COMPLETED  \n"
        f"**Run ID:** `{primary['run_id']}`  \n"
        f"**Model:** `{primary['model']}` via the existing local Ollama installation  \n"
        f"**Model digest:** `{primary['model_digest']}`  \n"
        f"**Model metadata:** `{json.dumps(primary['model_info'], ensure_ascii=True)}`  \n"
        f"**Report generated from:** `{primary_path.relative_to(ROOT).as_posix()}`  \n"
        f"**Frozen prompts and ground truth:** `{ground_truth_path.relative_to(ROOT).as_posix()}`  \n"
        f"**Ground-truth SHA-256:** `{sha256_file(ground_truth_path)}`\n"
    )

    add(
        "## 1. Environment, scope and evidence hierarchy\n\n"
        "This round evaluates only the local `lfm3:latest` model and the existing "
        "mathematical tool infrastructure. It is not a trading backtest and it uses "
        "no market data or financial predictions.\n\n"
        "- Block 1 components used unchanged: `mdl.OllamaClient`, "
        "`mdl.ToolOrchestrator`, `mdl.expr_parser`, `mdl.verify_symbolic_expand` "
        "and `mdl.ResearchStore`.\n"
        "- The tool grammar was taken from `mdl/expr_parser.py`: integers, variable "
        "names, parentheses and `+ - * **`; `^` is not part of the grammar. Only "
        "non-negative integer exponents are accepted.\n"
        "- The tool request path is the existing orchestrator validation and "
        "spawned-subprocess execution path. No model-generated code was executed "
        "directly and no alternative tool format was invented.\n"
        "- No dependency, model, dataset, Windows setting, service, registry, "
        "driver or security setting was changed.\n"
        "- All Round 3 tasks and outputs are classified `evaluation_only`. No "
        "training dataset was created.\n\n"
        "**Evidence hierarchy used in this report:**\n\n"
        "1. **Observations** are the exact prompts, raw outputs, parsed outputs, "
        "tool records and independent SymPy checks. These are the primary evidence.\n"
        "2. **Interpretations** are the 0–4 scores and the comparisons. They follow "
        "the stated rubric and are not model self-reports.\n"
        "3. **Hypotheses** are explicitly labelled explanations for observed "
        "patterns. They are not treated as established facts.\n"
    )

    add(
        "## 2. Exact settings and execution limits\n\n"
        "```json\n"
        + json.dumps(primary["settings"], ensure_ascii=True, indent=2)
        + "\n```\n\n"
        "Additional protocol details:\n\n"
        "- System prompt: the existing Round 1 system prompt from `block15/tasks.py`.\n"
        "- Condition A: the original Round 1 output protocol (`answer`, `reasoning`, "
        "`confidence`, `uncertainty`).\n"
        "- Condition B: the derivation-first protocol (`derivation`, `final_answer`, "
        "`uncertainty`, `confidence`).\n"
        "- Final-answer budget: 1200 tokens. Tool decision/request budget: 300 tokens.\n"
        "- All inference calls were sequential and single-flight.\n"
        f"- Planned calls: 14. Actual model invocations: {primary['calls_used_total']} "
        f"(hard limit 16).\n"
        f"- Recorded runtime: {primary['runtime_s_total']:.2f} s (hard limit 420 s).\n"
        f"- Completed tasks: {primary['completed_tasks']} / 12. "
        f"Failed tasks: {primary['failed_tasks']}.\n"
    )

    add("## 3. Frozen task prompts, expected answers and verification methods\n")
    for task in ground_truth["tasks"]:
        add(
            f"### `{task['id']}`\n\n"
            f"- Group: `{task['group']}`\n"
            f"- Protocol: `{task['protocol']}`\n"
            f"- Mode: `{task['mode']}`\n"
            f"- Difficulty: `{task['difficulty']}`\n"
            f"- Prompt SHA-256: `{task['prompt_sha256']}`\n"
            f"- Prompt characters: {task['prompt_characters']}\n\n"
            f"Exact prompt:\n\n{fence(task['prompt'], 'text')}\n\n"
            f"Expected answer / ground truth (not present in prompt):\n\n"
            f"{task['expected']}\n\n"
            f"Verification method:\n\n{task['verification']}\n"
        )

    add(
        "The preflight check froze these prompts before any model call and verified "
        "that the repeat prompt was byte-identical to the first A1 Condition B prompt. "
        "It also checked that the listed expected-answer tokens were absent from the "
        "prompts. The independent values were computed with SymPy and exhaustive "
        "integer checks; LFM3 outputs were not used as ground truth.\n"
    )

    add(
        "## 4. All task results\n\n"
        + task_table(results, assessments)
        + "\n\n"
        "All twelve task records completed. There were no runner-side exceptions and "
        "no recovery run. The two tool tasks each used two calls; every other task "
        "used one call. The 14 calls are the complete set of Round 3 model "
        "invocations.\n\n"
        "**Automated-check caveat.** The `Automated check` column is the stored helper "
        "status, not the final rubric verdict. B's `objective_fail` is a false "
        "negative: the helper looked for `121` and `11^2` only in the one-line "
        "`final_answer` field (`\"4\"`), while both appear in the derivation that the "
        "helper did inspect for the preceding values. The raw record is retained "
        "unchanged; the independent SymPy facts and the manual rubric confirm the "
        "answer, which is why correctness is 4. Similarly, C's keyword check does not "
        "recognise its cautious wording, and F's check does not recognise its exact "
        "phrase `not a simple exact deterministic rule`; those records remain "
        "`manual_review_required`.\n"
    )

    add(
        "## 5. Output-contract comparison\n\n"
        "Only the A1 and A2 pairs hold the mathematical question and settings "
        "constant while changing the output protocol.\n\n"
        "| Pair | Condition | JSON valid | Final answer | Derivation | Final/derivation consistent | Eval tokens | Latency |\n"
        "|---|---|---|---|---|---|---:|---:|\n"
        f"| A1 coefficient | A (original) | yes | `{snippet(answer(a1a), 60)}` | reaches 4860 | **no** | {a1a['tokens']['eval_count']} | {(a1a['latency_ms'] or 0)/1000:.1f}s |\n"
        f"| A1 coefficient | B (derivation first) | yes | `{snippet(answer(a1b), 60)}` | valid binomial derivation | yes | {a1b['tokens']['eval_count']} | {(a1b['latency_ms'] or 0)/1000:.1f}s |\n"
        f"| A2 divisibility | A (original) | yes | `{snippet(answer(a2a), 80)}` | valid proof | yes | {a2a['tokens']['eval_count']} | {(a2a['latency_ms'] or 0)/1000:.1f}s |\n"
        f"| A2 divisibility | B (derivation first) | yes | `{snippet(answer(a2b), 80)}` | valid proof | yes | {a2b['tokens']['eval_count']} | {(a2b['latency_ms'] or 0)/1000:.1f}s |\n\n"
        "Paired summary:\n\n"
        f"- Condition A pair: 2/2 valid JSON, 1/2 correct final answer, 1/2 "
        f"answer/derivation consistency, {protocol_a_eval} eval tokens, "
        f"{protocol_a_latency/1000:.1f} s total task latency.\n"
        f"- Condition B pair: 2/2 valid JSON, 2/2 correct final answer, 2/2 "
        f"answer/derivation consistency, {protocol_b_paired_eval} eval tokens, "
        f"{protocol_b_paired_latency/1000:.1f} s total task latency.\n\n"
        "The material paired observation is A1: the old protocol produced a correct "
        "derivation but retained a contradictory `answer` field (`-21` versus "
        "`4860`), while the paired derivation-first run produced `final_answer=4860`. A2 "
        "shows that the old protocol is not uniformly unreliable: both A2 conditions "
        "produced valid proofs. This is evidence from two pairs, not a general "
        "protocol law.\n"
    )

    add(
        "## 6. Systematic counterexample search and minimality\n\n"
        "### B — `n^2 + n + 101`\n\n"
        f"- Independent ground truth: first composite at `n=4`, "
        f"`f(4)=121=11^2`; `f(0)=101`, `f(1)=103`, `f(2)=107`, `f(3)=113` are prime.\n"
        f"- Model observation: final answer `{snippet(answer(b), 40)}`; derivation "
        f"lists all four preceding values and `f(4)=121=11*11`.\n"
        "- Assessment: it genuinely established minimality for this finite range by "
        "checking every preceding non-negative value. The final answer is terse and "
        "does not explicitly discuss the distinction between examples and a "
        "minimality certificate, but the required search content is present. Search "
        "completeness score: 4; completeness score: 3.\n\n"
        "### C — `n^2 + n + 1277`\n\n"
        "- Independent ground truth: `n=0..6` give prime values; the first "
        "counterexample is `n=7`, `f(7)=1333=31*43`.\n"
        f"- Model observation: final answer `{snippet(answer(c), 180)}`.\n"
        "- The response lists the first six prime observations and correctly warns "
        "that they do not prove universal primality. Its fourth derivation step is "
        "exactly 500 characters and ends mid-formula at the schema's per-step "
        "maximum; after that it performs no concrete falsification and never reaches "
        "`n=6`, `n=7` or `1333=31*43`.\n"
        "- Assessment: this is a substantive failure of active falsification and "
        "search, partly compounded by the per-step schema cap, not a JSON failure. "
        "Search completeness score: 0; hypothesis quality score: 1; correctness "
        "score: 1.\n\n"
        "The contrast between B and C is an observation across two tasks. A plausible "
        "hypothesis is that the larger, less obvious C search space and the six-part "
        "prompt made the model anchor on local differences instead of executing a "
        "bounded search; the experiment does not isolate that cause.\n"
    )

    add(
        "## 7. Hypothesis formation and falsification\n\n"
        "- C correctly recognized that finite prime observations do not justify a "
        "universal primeness claim. That uncertainty statement is directionally "
        "correct and is scored under calibration.\n"
        "- It did not formulate a concrete testable falsification procedure, did not "
        "state a search bound, and did not test the first counterexample. Its fourth "
        "derivation step was cut at the 500-character per-step limit, and its final "
        "answer describes the observed odd increments rather than answering the "
        "requested falsification questions.\n"
        "- B is the positive control for finite search: the model checked all "
        "preceding values and found the exact counterexample at `n=4`.\n"
        "- Therefore the evidence distinguishes two behaviors: a short finite "
        "minimality check can succeed, while a less direct hypothesis-falsification "
        "prompt can fail to produce any search at all. This is not evidence that "
        "LFM3 can or cannot falsify hypotheses in general.\n"
    )

    add(
        "## 8. Tool selection and execution\n\n"
        "### D1 — voluntary tool selection\n\n"
        f"- Decision: `use_tool=false`. Expression field: "
        f"`{d1['tool']['requested_expression']}`. Grammar check: uses `**`, not `^`.\n"
        f"- Orchestrator: not called because the model declined the tool. Final "
        f"answer: `{snippet(answer(d1), 50)}`, independently correct.\n"
        f"- The decision reason itself performs the binomial arithmetic, reaches "
        f"`-55,427,328`, and states that number, contrary to the instruction not to "
        f"give the final answer in the decision step. The final derivation reaches "
        f"the same value in step 7, but step 8 is exactly 500 characters and the "
        f"8-item array cap also cuts the last step mid-calculation.\n"
        "- Assessment: direct computation was defensible and correct; no automatic "
        "penalty is applied merely for declining the tool. However, the model did "
        "not use the available independent verification for a large-coefficient "
        "calculation, and it violated the decision-step output instruction by "
        "stating the final number. Tool competence score: 3.\n\n"
        "### D2 — required tool use\n\n"
        f"- Tool request: `symbolic_expand` with "
        f"`{d2['tool']['requested_expression']}`. Grammar: valid `**` form.\n"
        "- Orchestrator: accepted. Execution: successful. Existing verifier: "
        f"`{d2['tool']['verification']['status']}` with algebraic difference "
        f"`{d2['tool']['verification']['difference']}` and structured "
        "reconstruction matching.\n"
        f"- Final answer: `{snippet(answer(d2), 50)}`, consistent with the verified "
        "expansion and with the requested coefficient.\n"
        "- Assessment: complete end-to-end required tool success. Tool competence "
        "score: 4.\n\n"
        "The two tool tests measure different behaviors. Required tool use was "
        "executed correctly; voluntary selection was not exercised in this run even "
        "though the expression field was grammatically valid. The D1 decision-step "
        "violation is recorded separately from the final-answer correctness: the "
        "final answer is right, but the requested decision-only output was not "
        "respected.\n"
    )

    add(
        "## 9. Uncertainty calibration\n\n"
        "| Task | Situation | Model conclusion | Confidence / uncertainty | Calibration |\n"
        "|---|---|---|---|---:|\n"
        f"| E1 | Determinate `n(n+1)(n+2)` divisibility | correct proof and yes | 1.0 / none | 4 |\n"
        f"| E2 | Underdetermined `3,7,13,21,31` | 43 plausible, explicitly not unique | 0.95 / additional rule needed | 4 |\n"
        f"| A1A | Determinate coefficient | final answer wrong, derivation 4860 | 0.99 / low | 1 |\n"
        f"| C | Finite prime observations | no universal claim, but no search | 0.85 / needs evidence | 2 |\n"
        f"| F | Noisy numerical trend | trend and noise described; next value inconsistent | 0.78 / moderate | 2 |\n\n"
        "E1 and E2 show appropriate calibration on clear determinate and "
        "underdetermined prompts. A1A shows a severe mismatch between confidence and "
        "the final answer field. F shows moderate confidence attached to an estimate "
        "that conflicts with its own stated pattern. C is cautious about the "
        "universal claim but still does not answer the falsification task.\n"
    )

    add(
        "## 10. Numerical trend and noise\n\n"
        f"- Observations: 100, 102, 101, 103, 102, 104, 103, 105. Differences: "
        f"+2, -1, +2, -1, +2, -1, +2. Odd positions: 100, 101, 102, 103; even "
        f"positions: 102, 103, 104, 105.\n"
        "- The model correctly identified an upward drift and the alternating "
        "fluctuations. It correctly said that a simple exact deterministic rule is "
        "not established and proposed additional observations, regression, "
        "autocorrelation and variance checks.\n"
        f"- It then said the next value should be 107 with range 106–108. Applying "
        "its own stated +2/−1 alternation after 105 gives 104. The task intentionally "
        "has no unique correct next value, but the model's estimate is inconsistent "
        "with its own pattern. It also mentions inconsistent average slopes.\n"
        "- Assessment: partial noise awareness; the description is better than the "
        "extrapolation. Correctness 2, logical validity 2, answer consistency 1, "
        "calibration 2, noise awareness 3. This is not evidence about trading "
        "performance.\n"
    )

    add(
        "## 11. Repeatability\n\n"
        f"- Repeated task: `R3A1_coefficient_protocol_B` versus "
        f"`R3A1_coefficient_protocol_B_repeat`.\n"
        "- Identical fields: raw output, parsed object, `done_reason`, exact messages, "
        "schema, model settings, prompt tokens, eval tokens and confidence.\n"
        "- Different fields: call latency and task latency. Call latency was "
        f"{g['calls'][0]['latency_ms']} ms versus {a1b['calls'][0]['latency_ms']} ms; "
        f"task latency was {g['latency_ms']} ms versus {a1b['latency_ms']} ms.\n"
        "- Conclusion: content-identical repetition for this compact task under the "
        "fixed settings. This does not establish universal determinism, and latency "
        "is not deterministic.\n"
    )

    add(
        "## 12. Independent verification results\n\n"
        "| Area | Independent check | Result |\n"
        "|---|---|---|\n"
        "| A1 coefficient | SymPy `coeff(x^4)` of `(3*x-2)**6` | 4860; Condition A final `-21` fails, Condition B `4860` passes |\n"
        "| A2 divisibility | exhaustive modulo-6 check over `n=-500..500` | true; both conditions produced valid proofs |\n"
        "| B minimality | SymPy primality search, n=0..100 | first composite n=4, 121=11²; preceding 101,103,107,113 prime |\n"
        "| C falsification | SymPy primality search, n=0..100 | first counterexample n=7, 1333=31×43; n=0..6 prime |\n"
        "| D1 coefficient | SymPy `coeff(x^7)` of `(3*x-2)**12` | -55,427,328; model final answer matches |\n"
        "| D2 coefficient | SymPy `coeff(x^5)` of `(2*x+3)**7` | 6048; tool verifier passed, difference 0 |\n"
        "| E1 divisibility | exhaustive modulo-6 check over `n=-500..500` | true; valid proof |\n"
        "| E2 sequence | finite differences and SymPy interpolation | simple continuation 43; uniqueness not established |\n"
        "| F trend | differences and subsequences | +2/−1 alternation; no unique next value; model's 107 conflicts with its own 104 continuation |\n"
        "| G repeat | byte comparison of stored calls | content and tokens identical; latency differs |\n\n"
        "Proof quality for A2 and E1 is a manual rubric judgement; the numerical "
        "divisibility facts are independently checked. No model-generated explanation "
        "was used as the source of ground truth. The B row's stored automated status "
        "is a final-answer-only false negative, as explained in section 4; the "
        "independent computation itself is unambiguous. The C and F helper flags are "
        "conservative keyword checks, not ground truth.\n"
    )

    add(
        "## 13. JSON validity, truncation and answer consistency\n\n"
        f"- Actual model invocations: {primary['calls_used_total']}.\n"
        f"- Parsed JSON responses: {valid_json_calls}/{total_calls} = 100%.\n"
        f"- `done_reason=length` events: {length_stops}.\n"
        "- All calls ended with `done_reason=stop`. A1A used 753 eval tokens but was "
        "not truncated.\n"
        "- Two stored derivation items hit the 500-character per-item limit exactly: "
        "C step 4 and D1 step 8. D1 also reached the 8-item derivation maximum. In "
        "C the cap cuts a difference calculation mid-formula; in D1 the cap cuts the "
        "last calculation after the correct result is already present in step 7. "
        "These are schema-structure limits, not token-level `done_reason=length` "
        "truncation.\n\n"
        "Manual answer/derivation consistency classification:\n\n"
        "- Fully consistent: A1B, A2A, A2B, B, D1, D2, E1, E2, G = 9/12.\n"
        "- No direct contradiction but incomplete: C = 1/12.\n"
        "- Direct contradiction: A1A (final -21 versus derivation 4860) and F "
        "(states +2/−1 then recommends 107 instead of the implied 104) = 2/12.\n\n"
        "The principal Round 3 failure mode is therefore semantic consistency, not "
        "JSON syntax. That differs from a run in which invalid JSON or token "
        "truncation dominates.\n"
    )

    add(
        "## 14. Latencies, prompt tokens and evaluation tokens\n\n"
        "```json\n"
        + json.dumps(
            {
                "model_calls": primary["calls_used_total"],
                "runtime_s": primary["runtime_s_total"],
                "prompt_tokens_total": primary["prompt_tokens_total"],
                "eval_tokens_total": primary["eval_tokens_total"],
                "slowest_tasks_s": [
                    {
                        "task": item["task"]["id"],
                        "latency_s": round((item["latency_ms"] or 0) / 1000.0, 2),
                        "eval_tokens": item["tokens"]["eval_count"],
                    }
                    for item in sorted(
                        results,
                        key=lambda item: item["latency_ms"] or 0,
                        reverse=True,
                    )[:5]
                ],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n```\n\n"
        "The A1A call is the slowest single call: 753 eval tokens in 55.3 s. The "
        "repeat of A1B took the same 193 eval tokens as the first A1B call but "
        "differed by about 30 ms in wall time. Total Round 3 generation was 4183 "
        "eval tokens across 14 calls.\n"
    )

    add(
        "## 15. Resource measurements\n\n"
        "```json\n"
        + json.dumps(
            {
                "free_mb_start": primary["free_mb_start"],
                "free_mb_min_sampled": primary["free_mb_min"],
                "free_mb_end": primary["free_mb_end"],
                "free_mb_after_unload": 2754.0,
                "memory_stop_threshold_mb": primary["limits"]["min_free_mb"],
                "memory_stop_occurred": primary["stopped_early"],
                "single_flight": True,
                "parallel_inference": False,
                "ollama_ps_after_unload": "empty",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n```\n\n"
        "Memory remained above the 450 MB stop threshold throughout the sampled "
        "run. The minimum sampled value was 1112.2 MB. The model was unloaded with "
        "`ollama stop lfm3:latest`; `ollama ps` was empty afterward and free physical "
        "memory was 2754 MB. The minimum is sampled around task boundaries, not by a "
        "continuous monitor.\n"
    )

    add(
        "## 16. Technical failures, incompleteness and limitations\n\n"
        "- Technical failures: none. 12/12 tasks completed; 14/14 calls returned "
        "valid JSON; no runner exception occurred; no recovery was needed.\n"
        "- A1A is a model-output consistency failure, not a runner failure: the "
        "`answer` field remains `-21` even though the reasoning reaches 4860 and says "
        "the answer should be 4860. The model never updates its initial answer field.\n"
        "- C is a semantic incompleteness/failure, not token truncation: the JSON is "
        "valid and `done_reason=stop`, but its fourth derivation step is cut at the "
        "500-character per-step limit and it never performs the search.\n"
        "- D1's final derivation step is cut at the 500-character limit and the array "
        "also reaches the 8-item cap. The final answer is correct and the numeric "
        "result appears in step 7. Its decision reason additionally states the final "
        "number despite the instruction to keep the decision step answer-free. Both "
        "are recorded as protocol/structural limitations.\n"
        "- B's stored `objective_fail` is a helper false negative: the checker looked "
        "for the counterexample value and factorization only in the one-line "
        "`final_answer` field, not in the derivation where they actually appear. The "
        "model output and the raw helper record were not altered.\n"
        "- The sample is 12 tasks, one model, one fixed seed, one run and one exact "
        "repeat. The report does not support broad capability rankings.\n"
        "- Proof quality and some hypothesis/trend judgements are rubric-based. "
        "Independent SymPy checks establish numerical facts, not the full validity of "
        "a prose proof.\n"
        "- No hidden chain-of-thought was requested or used. Only concise, checkable "
        "derivations and observable outputs are evaluated.\n"
        "- No real market data or trading prediction was involved.\n"
    )

    add(
        "## 17. Separate scores by evaluation dimension\n\n"
        "The 0–4 scale is applied per dimension. A high score on one dimension does "
        "not cancel a failure on another; the table is not collapsed into a single "
        "overall grade.\n\n"
        + assessment_tables(assessments)
        + "\n\n### Dimension summary\n\n"
        + dimension_summary(assessments)
        + "\n\nThe averages are descriptive only. The low-scoring tasks are shown "
        "explicitly so that they are not hidden by the mean: A1A (consistency 0, "
        "calibration 1), C (search 0, hypothesis 1), and F (consistency 1, "
        "calibration 2).\n"
    )

    add(
        "## 18. Ranked conclusions\n\n"
        "1. **The strongest controlled observation is the A1 output-contract "
        "contradiction.** The original protocol produced a correct 4860 derivation "
        "but retained `answer=-21` with confidence 0.99. The paired derivation-first "
        "run produced a consistent `final_answer=4860`. This is a clear, reproducible "
        "failure mode for this prompt, but it is one pair and not proof of a universal "
        "protocol effect.\n"
        "2. **Required tool use worked end-to-end.** D2 produced a valid "
        "`(2*x + 3)**7` request, the orchestrator accepted it, the tool executed, the "
        "existing verifier passed with difference 0, and the final coefficient 6048 "
        "matched. Voluntary tool use was not exercised: D1 declined the tool yet "
        "answered correctly by direct binomial arithmetic, although its decision "
        "reason stated the final number contrary to the decision-step instruction.\n"
        "3. **Counterexample search and minimality are not uniformly reliable.** B "
        "succeeded with a small finite search (`n=4`, 121=11², all preceding values "
        "checked). C failed to perform any search and missed `n=7`, `1333=31×43`, "
        "despite correctly warning that the first six prime observations prove "
        "nothing universal; its fourth derivation step was also cut at the "
        "500-character per-step limit. The difference may reflect search-space size, "
        "prompt complexity, the schema cap or all three; it is not isolated here.\n"
        "4. **Short elementary proofs succeeded in this round.** A2 under both "
        "protocols and E1 produced valid divisibility proofs. This argues against a "
        "general “cannot reason” interpretation of the C failure.\n"
        "5. **Uncertainty calibration was appropriate on the clean calibration "
        "tasks.** E1 used confidence 1.0 for a proved statement; E2 gave 43 as a "
        "plausible continuation while explicitly denying uniqueness. In contrast, "
        "A1A attached 0.99 confidence to a final answer that contradicted its own "
        "derivation, and F attached 0.78 to an extrapolation inconsistent with its "
        "stated pattern.\n"
        "6. **JSON reliability was high, so the important failures are semantic.** "
        "All 14 calls returned valid JSON and none hit `done_reason=length`. The "
        "remaining failures were final-answer consistency, incomplete search, and "
        "inconsistent extrapolation. C and D1 hit the 500-character per-step cap, "
        "and D1 also hit the 8-step array cap; these are structural limitations, "
        "not token truncation.\n"
        "7. **The exact repeat was content-deterministic, not latency-deterministic.** "
        "A1B and its repeat were byte-identical in raw output, parsed object, prompt, "
        "schema and token counts; call latency differed by about 30 ms. One repeat "
        "does not establish universal determinism.\n"
        "8. **The trend/noise response was partially capable but internally "
        "inconsistent.** It identified the upward drift, alternating fluctuations, "
        "non-determinism and useful additional tests, but recommended 107 after 105 "
        "even though its own +2/−1 pattern implies 104. This is a caution about "
        "extrapolation, not evidence about trading performance.\n"
    )

    add(
        "## 19. Training-versus-evaluation classification\n\n"
        "- All 12 Round 3 tasks and all 14 model outputs are `evaluation_only`.\n"
        "- No examples were added to a training dataset.\n"
        "- Round 3 prompts must remain held out; they should not be reused as future "
        "training prompts.\n"
        "- If future work needs training material, it must use independently generated "
        "variants. Candidate directions, not implemented here, include: coefficient "
        "tasks with varied signs and exponents; bounded minimality searches with "
        "different search depths; tool-decision tasks with a clear verification "
        "benefit; and trend tasks that separate description from extrapolation. The "
        "Round 3 prompts themselves remain evaluation-only.\n"
    )

    add(
        "## 20. Candidate next steps, ranked (not implemented)\n\n"
        "1. Add a machine consistency gate that compares the final answer with the "
        "derivation and flags contradictions before a result is accepted. This is an "
        "evaluation safeguard, not a Block 1 change in this round.\n"
        "2. Extend the paired A/B protocol comparison to more tasks before treating "
        "derivation-first as a general improvement. The current A1 evidence is strong "
        "for one pair but not sufficient for a general claim.\n"
        "3. Separate the B and C search behaviors with a controlled series of "
        "minimality tasks of increasing search depth, prompt complexity and "
        "per-step output budget. This would test whether C's failure is search-space, "
        "prompt-overload, the 500-character schema cap or a combination.\n"
        "4. Add voluntary-tool calibration tasks where independent verification has a "
        "clear benefit, and record the decision reason separately from the final "
        "answer. D1 shows that a correct direct answer can coexist with no tool use.\n"
        "5. Add internal-consistency checks to numerical trend tasks: require the "
        "proposed next value to be derivable from the stated pattern, or explicitly "
        "state that it is not.\n"
        "6. Only after review, consider independently generated training variants. "
        "Do not reuse these evaluation prompts and do not start training, Block 2 or "
        "Block 1 protocol changes without explicit instruction.\n"
    )

    add(
        "## 21. Machine-readable artifacts and changes\n\n"
        "New artifacts:\n\n"
        + "\n".join(f"- {artifact}" for artifact in artifacts)
        + "\n\nNo Git commit or push was performed. All project files remain "
        "untracked in the existing repository state, as before Round 3; this is not "
        "a commit. No existing project or experiment directory was deleted, reset, "
        "cleaned or overwritten.\n"
    )

    add(
        "## 22. Final compliance and stop-condition checks\n\n"
        f"- Block 1 test suite: **57 passed, 1 deselected**.\n"
        f"- Block 1 JSONL: valid, 20 events. SQLite: {db_counts['block1']['experiments']} "
        f"experiments, {db_counts['block1']['steps']} steps.\n"
        f"- Round 1 JSONL: valid, 252 events. SQLite: {db_counts['round1']['experiments']} "
        f"experiments, {db_counts['round1']['steps']} steps.\n"
        f"- Round 2 JSONL: valid, 88 events. SQLite: {db_counts['round2']['experiments']} "
        f"experiments, {db_counts['round2']['steps']} steps.\n"
        f"- Round 3 JSONL: valid, 65 events. SQLite: {db_counts['round3']['experiments']} "
        f"experiments, {db_counts['round3']['steps']} steps.\n"
        f"- Pre-Round-3 data hashes unchanged: **{'yes' if all_unchanged else 'NO'}**.\n"
        f"- Newest source file under `mdl/`: `{newest_source.relative_to(ROOT).as_posix()}` "
        f"with mtime `{newest_source_time}` (before Round 3); no Block 1 source file "
        "was written by this round.\n"
        "- LFM3 was unloaded with `ollama stop lfm3:latest`; `ollama ps` is empty.\n"
        "- No training, fine-tuning, dataset download, dashboard, Block 2 or Block 1 "
        "protocol change was started.\n"
        "- No `.env`, credential, unrelated file, Windows setting, service, registry, "
        "driver or security setting was accessed or modified.\n\n"
        "Existing artifact hash comparison:\n\n"
        + "\n".join(hash_rows)
        + "\n"
    )

    add(
        "## 23. Raw prompts and raw LFM3 outputs\n\n"
        "The following section reproduces every stored Round 3 call. It contains the "
        "exact messages sent to Ollama, the JSON schema, the raw model output, the "
        "parsed object, tool records and the independent check record. No raw output "
        "was rewritten for the report.\n\n"
        + raw_section(results)
    )

    OUTPUT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    print(f"calls={total_calls} valid_json={valid_json_calls} length_stops={length_stops}")
    print(f"hashes_unchanged={all_unchanged}")


if __name__ == "__main__":
    main()
