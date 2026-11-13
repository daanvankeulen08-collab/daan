"""Freeze Round 3 prompts and independently computed ground truth.

This script performs no model calls and writes only new Round 3 metadata.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import sympy

from block15.round3_tasks import (
    ANSWER_SCHEMA,
    EXPERIMENTAL_SCHEMA,
    PLANNED_CALLS,
    RUN_ORDER,
)
from mdl.config import load_settings

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA_DIR / "block15_round3_ground_truth.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _task_facts(task_id: str) -> dict:
    x, n = sympy.symbols("x n")

    if task_id.startswith("R3A1_coefficient"):
        expression = sympy.expand((3 * x - 2) ** 6)
        return {
            "expression": str(expression),
            "coefficient_x4": str(expression.coeff(x, 4)),
        }

    if task_id.startswith("R3A2_divisibility"):
        checked = all((k**3 - k) % 6 == 0 for k in range(-500, 501))
        return {
            "identity": str(sympy.factor(n**3 - n)),
            "exhaustive_check_n_minus_500_to_500": checked,
            "argument": "product of three consecutive integers",
        }

    if task_id == "R3B_counterexample_minimality":
        values = []
        first = None
        first_value = None
        for k in range(0, 101):
            value = k * k + k + 101
            is_prime = sympy.isprime(value)
            values.append(
                {
                    "n": k,
                    "value": value,
                    "prime": bool(is_prime),
                    "factorization": None if is_prime else sympy.factorint(value),
                }
            )
            if not is_prime and first is None:
                first = k
                first_value = value
        return {
            "first_composite_n": first,
            "first_composite_value": first_value,
            "factorization": sympy.factorint(first_value) if first_value else None,
            "preceding_values": values[: first if first is not None else 0],
            "values": values,
        }

    if task_id == "R3C_hypothesis_falsification":
        values = []
        first = None
        first_value = None
        for k in range(0, 101):
            value = k * k + k + 1277
            is_prime = sympy.isprime(value)
            values.append(
                {
                    "n": k,
                    "value": value,
                    "prime": bool(is_prime),
                    "factorization": None if is_prime else sympy.factorint(value),
                }
            )
            if not is_prime and first is None:
                first = k
                first_value = value
        return {
            "first_counterexample_n": first,
            "first_counterexample_value": first_value,
            "factorization": sympy.factorint(first_value) if first_value else None,
            "preceding_values": values[: first if first is not None else 0],
            "values": values,
        }

    if task_id == "R3D1_tool_voluntary":
        expression = sympy.expand((3 * x - 2) ** 12)
        return {
            "expression": str(expression),
            "coefficient_x7": str(expression.coeff(x, 7)),
        }

    if task_id == "R3D2_tool_required":
        expression = sympy.expand((2 * x + 3) ** 7)
        return {
            "expression": str(expression),
            "coefficient_x5": str(expression.coeff(x, 5)),
        }

    if task_id == "R3E1_uncertainty_determinate":
        checked = all((k * (k + 1) * (k + 2)) % 6 == 0 for k in range(-500, 501))
        return {
            "exhaustive_check_n_minus_500_to_500": checked,
            "argument": "one factor divisible by 3 and at least one even factor",
        }

    if task_id == "R3E2_uncertainty_underdetermined":
        sequence = [3, 7, 13, 21, 31]
        first_differences = [b - a for a, b in zip(sequence, sequence[1:])]
        second_differences = [
            b - a for a, b in zip(first_differences, first_differences[1:])
        ]
        poly = sympy.interpolate(
            [(index + 1, value) for index, value in enumerate(sequence)], n
        )
        return {
            "observations": sequence,
            "first_differences": first_differences,
            "second_differences": second_differences,
            "interpolated_polynomial": str(sympy.expand(poly)),
            "simple_continuation": int(poly.subs(n, 6)),
            "uniqueness": "not unique without an additional rule or model class",
        }

    if task_id == "R3F_numerical_trend_noise":
        observations = [100, 102, 101, 103, 102, 104, 103, 105]
        return {
            "observations": observations,
            "first_differences": [
                b - a for a, b in zip(observations, observations[1:])
            ],
            "odd_positions": observations[0::2],
            "even_positions": observations[1::2],
            "simple_description": (
                "upward drift of about 0.5 per observation with an "
                "alternating +2/-1 fluctuation"
            ),
            "unique_next_value": None,
        }

    return {}


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite frozen ground truth: {OUTPUT}")

    settings = load_settings(
        db_path=DATA_DIR / "block15_round3.sqlite3",
        jsonl_path=DATA_DIR / "block15_round3_events.jsonl",
    )
    task_ids = [task.id for task in RUN_ORDER]
    if len(task_ids) != len(set(task_ids)):
        raise SystemExit("duplicate Round 3 task IDs")

    existing_artifacts = {
        "data/mdl.sqlite3": DATA_DIR / "mdl.sqlite3",
        "data/research_events.jsonl": DATA_DIR / "research_events.jsonl",
        "data/block15.sqlite3": DATA_DIR / "block15.sqlite3",
        "data/block15_events.jsonl": DATA_DIR / "block15_events.jsonl",
        "data/block15_round2.sqlite3": DATA_DIR / "block15_round2.sqlite3",
        "data/block15_round2_events.jsonl": DATA_DIR / "block15_round2_events.jsonl",
    }
    pre_hashes = {
        rel_path: _sha256_file(path) for rel_path, path in existing_artifacts.items()
    }

    tasks = []
    for task in RUN_ORDER:
        metadata = task.metadata()
        metadata["prompt_sha256"] = _sha256_bytes(task.prompt.encode("utf-8"))
        metadata["prompt_characters"] = len(task.prompt)
        metadata["independent_facts"] = _task_facts(task.id)
        tasks.append(metadata)

    forbidden_tokens = {
        "R3A1_coefficient_protocol_A": ["4860"],
        "R3A1_coefficient_protocol_B": ["4860"],
        "R3A1_coefficient_protocol_B_repeat": ["4860"],
        "R3B_counterexample_minimality": ["121", "11^2"],
        "R3C_hypothesis_falsification": ["1333", "31*43", "31 x 43"],
        "R3D1_tool_voluntary": ["55427328", "55,427,328"],
        "R3D2_tool_required": ["6048"],
        "R3E2_uncertainty_underdetermined": ["43"],
    }
    safety = {}
    for task in RUN_ORDER:
        prompt = task.prompt
        leaks = [
            token
            for token in forbidden_tokens.get(task.id, [])
            if token.lower() in prompt.lower()
        ]
        safety[task.id] = {"checked_tokens": forbidden_tokens.get(task.id, []), "leaks": leaks}
        if leaks:
            raise SystemExit(f"prompt for {task.id} contains an answer hint: {leaks}")

    if not (A1_B := next(task for task in RUN_ORDER if task.id.endswith("R3A1_coefficient_protocol_B"))):
        raise SystemExit("missing A1 condition B")
    repeat = next(task for task in RUN_ORDER if task.id == "R3A1_coefficient_protocol_B_repeat")
    if A1_B.prompt != repeat.prompt:
        raise SystemExit("repeat prompt is not byte-identical to A1 condition B")
    if PLANNED_CALLS > 16:
        raise SystemExit(f"planned calls exceed hard limit: {PLANNED_CALLS}")

    payload = {
        "round": 3,
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": settings.model,
        "settings": {
            "think": settings.think,
            "num_ctx": settings.context_limit,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "repeat_penalty": settings.repeat_penalty,
            "seed": settings.seed,
            "keep_alive": settings.keep_alive,
            "num_predict_decision": 300,
            "num_predict_final": 1200,
            "single_flight": True,
            "sequential": True,
        },
        "call_plan": {
            "tasks": len(RUN_ORDER),
            "planned_model_calls": PLANNED_CALLS,
            "target_low": 12,
            "target_high": 14,
            "hard_limit": 16,
            "hard_runtime_s": 420,
        },
        "schemas": {
            "answer": ANSWER_SCHEMA,
            "experimental": EXPERIMENTAL_SCHEMA,
        },
        "prompt_safety": safety,
        "pre_round3_artifact_sha256": pre_hashes,
        "tasks": tasks,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT}")
    print(f"tasks={len(RUN_ORDER)} planned_calls={PLANNED_CALLS}")
    for task in RUN_ORDER:
        facts = next(item for item in tasks if item["id"] == task.id)["independent_facts"]
        key = (
            facts.get("coefficient_x4")
            or facts.get("coefficient_x7")
            or facts.get("coefficient_x5")
            or facts.get("first_composite_n")
            or facts.get("first_counterexample_n")
            or facts.get("simple_continuation")
            or "checked"
        )
        print(f"{task.id}: {key}")


if __name__ == "__main__":
    main()
