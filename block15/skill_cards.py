"""Offline-compiled assistance cards for the skill-tool study.

Two assistance levels, both receiving the IDENTICAL tool schema:

  L3: a full procedure card plus ONE generated worked example.  The example is
      f(n)=n^2+103 (first composite n=1, value=104=2*13).  Its numbers are not
      any pilot task and none of its ground-truth tokens appear in any of the
      30 ORDER_V2 task answers (asserted at import-verification time).
  L0: NO card.  Only the tool schema and the task's own neutral instruction.

Cards are compiled offline (static text).  No model generation, no teacher
hint, no task-specific answers.  The tool schema object is imported unchanged
from skill_tools so L3 and L0 are byte-identical in their schema block.
"""

from __future__ import annotations

import json

from block15 import order_v2_research as O
from block15 import skill_tools as T
from block15.round3 import _number_present

# The single worked example. Chosen to avoid every ground-truth token of every
# ORDER_V2 task (verified by verify_assistance_no_gt).
EXAMPLE = {
    "question": "Let f(n) = n^2 + 103. Find the smallest integer n >= 0 such that f(n) is composite. Give n, the value f(n), and the complete prime factorization of f(n).",
    "tool_request": {
        "tool": T.TOOL_NAME,
        "arguments": {"a": 1, "b": 0, "c": 103, "n_max": 128},
    },
    "tool_result": {"n": 1, "value": 104, "factors": [2, 13]},
    "final_answer": "n = 1, f(n) = 104, prime factorization = 2 * 13",
}

# L3 procedure card: fields required by the study spec.
L3_CARD = {
    "trigger": (
        "A bounded-minimality question asks for the smallest integer n at which "
        "a quadratic f(n) = a*n^2 + b*n + c is composite, plus its factorization."
    ),
    "procedure": (
        "Read the integer coefficients a, b and c from the question. Choose an "
        "n_max bound within the tool's allowed range that covers the expected "
        "search. Request the first-composite tool with those coefficients and "
        "that bound. Copy the returned n, value and prime factors into the "
        "final_answer field exactly. Verify the value is composite and the "
        "factors multiply back to it before finalising."
    ),
    "tool_reference": T.TOOL_NAME,
    "verification": (
        "Check that f(n) equals the returned value, that the value is composite, "
        "and that the listed primes are its complete factorization."
    ),
    "failure_modes": (
        "Searching only a small range of n; a slip in evaluating the quadratic; "
        "omitting the factorization; or reporting a prime as composite."
    ),
    "provenance": {
        "assistance_level": "L3",
        "compiler": "offline-static-card",
        "task_hash": None,
    },
}

LEVELS = ("L3", "L0")


def tool_schema_block() -> str:
    """The tool-schema text presented to the model. IDENTICAL for L3 and L0."""
    return (
        "A tool is available. Return a tool-request object matching this schema "
        "(or null if you will not use it):\n"
        + json.dumps(T.TOOL_SCHEMA, ensure_ascii=True, separators=(",", ":"))
    )


def assistance_text(level: str) -> str:
    """Return the appended assistance text for a level (empty for L0)."""
    if level == "L0":
        return ""
    if level != "L3":
        raise ValueError(level)
    parts = [
        "PROCEDURE CARD",
        "Trigger: " + L3_CARD["trigger"],
        "Procedure: " + L3_CARD["procedure"],
        "Tool: " + L3_CARD["tool_reference"],
        "Verification: " + L3_CARD["verification"],
        "Failure modes: " + L3_CARD["failure_modes"],
        "WORKED EXAMPLE (a different problem)",
        "Question: " + EXAMPLE["question"],
        "Tool request: " + json.dumps(EXAMPLE["tool_request"], separators=(",", ":")),
        "Tool result: " + json.dumps(EXAMPLE["tool_result"], separators=(",", ":")),
        "final_answer: " + EXAMPLE["final_answer"],
    ]
    return "\n".join(parts)


def verify_assistance_no_gt() -> dict:
    """Assert no pilot (or any ORDER_V2 task) GT token leaks into assistance."""
    truth = O.ground_truth_manifest()

    # GT tokens of the 9 pilot NO_SEARCH tasks, plus all 30 for a stricter check.
    pilot_ids = [
        t.id for t in O.TASKS
        if t.id.split("_")[0] in {
            "V2M03", "V2M04", "V2M06", "V2M07", "V2M09",
            "V2M10", "V2M11", "V2M14", "V2M15",
        }
    ]
    pilot_tokens: set[int] = set()
    for tid in pilot_ids:
        pilot_tokens.update(int(v) for v in truth[tid]["answer_tokens"])
    all_tokens: set[int] = set()
    for g in truth.values():
        all_tokens.update(int(v) for v in g["answer_tokens"])

    texts = {
        "L3": assistance_text("L3"),
        "L0": assistance_text("L0"),
        "TOOL_SCHEMA": tool_schema_block(),
    }
    report = {}
    for name, text in texts.items():
        pilot_hits = sorted(t for t in pilot_tokens if _number_present(text, t))
        all_hits = sorted(t for t in all_tokens if _number_present(text, t))
        report[name] = {
            "pilot_gt_token_hits": pilot_hits,
            "all_task_gt_token_hits": all_hits,
            "leaks": bool(pilot_hits or all_hits),
        }
        if report[name]["leaks"]:
            raise SystemExit(f"assistance text {name} leaks GT tokens: {report[name]}")
    # L0 must carry no card
    if assistance_text("L0") != "":
        raise SystemExit("L0 must have no assistance card")
    # example must not be a pilot task: compare normalized question text
    pilot_questions = {t.question.strip() for t in O.TASKS if t.id in pilot_ids}
    if EXAMPLE["question"].strip() in pilot_questions:
        raise SystemExit("worked example is a pilot task")
    report["example_not_pilot"] = True
    report["schema_identical_L3_L0"] = True  # both call tool_schema_block()
    return report
