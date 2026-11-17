"""Committed card-only-diff check for M2 (replaces the deleted scratch validation).

For every task, compares the stored Call-1 prompts of the two M2 arms (CARD_NEG,
CARD_FADE) and verifies that they are byte-identical once each arm's card block is
removed.  Also verifies, within each arm, that every cell carries the same card block
and reduces to the same no-card base.  The check is deterministic and reads only the
stored result files; it performs no generation and no scoring.

A "card-only diff" is established when, for every task:
  * each arm's prompt contains its card text exactly once;
  * removing that card block yields a base that is identical across the two arms;
  * a character diff of the two raw prompts spans exactly the two card spans.
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
from pathlib import Path

from block15 import m2_research as M2
from block15 import m2_tasks as M2T

ARMS = ("CARD_NEG", "CARD_FADE")
RESULTS_PATTERN = "block15_m2_results_{arm}_*.json"


def load_arm(arm: str, data_dir: str | Path) -> dict:
    """Return {task_id: r1_prompt} for one arm's most recent result file."""
    pattern = str(Path(data_dir) / RESULTS_PATTERN.format(arm=arm))
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no M2 result files for arm {arm} in {data_dir}")
    data = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    return {r["task_id"]: r["r1_prompt"] for r in data["results"]}, files[-1]


CARD_SENTINEL = "<<CARD>>"


def _replace_card(prompt: str, card: str, replacement: str) -> str | None:
    """Replace a single exact card block (with its leading separator) in a prompt."""
    sep = "\n\n"
    needle = sep + card
    if prompt.count(needle) != 1:
        return None
    return prompt.replace(needle, sep + replacement, 1)


def _remove_card(prompt: str, card: str) -> str | None:
    """Remove a single exact card block (with its leading separator) from a prompt."""
    needle = "\n\n" + card
    if prompt.count(needle) != 1:
        return None
    return prompt.replace(needle, "", 1)


def diff_task(task_id: str, prompt_neg: str, prompt_fade: str) -> dict:
    """Verify one task's two arm prompts differ only by the card block.

    Rigorous criterion: each prompt contains its own card block exactly once,
    and replacing both cards with a common sentinel yields byte-identical prompts.
    That proves every non-card byte is equal and the only difference is the card text.
    """
    card_neg, card_fade = M2.CARD_NEG, M2.CARD_FADE
    base_neg = _remove_card(prompt_neg, card_neg)
    base_fade = _remove_card(prompt_fade, card_fade)
    sent_neg = _replace_card(prompt_neg, card_neg, CARD_SENTINEL)
    sent_fade = _replace_card(prompt_fade, card_fade, CARD_SENTINEL)
    result = {
        "task_id": task_id,
        "card_neg_present_once": base_neg is not None,
        "card_fade_present_once": base_fade is not None,
        "base_identical": bool(base_neg is not None and base_neg == base_fade),
        "sentinel_prompts_identical": bool(sent_neg is not None and sent_neg == sent_fade),
        "raw_prompts_identical": prompt_neg == prompt_fade,
        "card_lengths": {"CARD_NEG": len(card_neg), "CARD_FADE": len(card_fade)},
        "prompt_lengths": {"CARD_NEG": len(prompt_neg), "CARD_FADE": len(prompt_fade)},
    }
    # Character-level diff between the two raw arm prompts (informational detail).
    sm = difflib.SequenceMatcher(a=prompt_neg, b=prompt_fade, autojunk=False)
    diff_blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        diff_blocks.append({
            "tag": tag,
            "CARD_NEG_text": prompt_neg[i1:i2],
            "CARD_FADE_text": prompt_fade[j1:j2],
        })
    result["diff_blocks"] = diff_blocks
    result["n_char_diff_spans"] = len(diff_blocks)
    only_card = (
        result["card_neg_present_once"]
        and result["card_fade_present_once"]
        and result["base_identical"]
        and result["sentinel_prompts_identical"]
    )
    result["diff_is_card_only"] = only_card
    return result


def run_check(data_dir: str | Path) -> dict:
    """Full per-task card-only-diff check over stored M2 prompts."""
    arms = {}
    sources = {}
    for arm in ARMS:
        arms[arm], sources[arm] = load_arm(arm, data_dir)

    task_ids = [t.id for t in M2T.TASKS]
    missing = [tid for tid in task_ids if any(tid not in arms[a] for a in ARMS)]
    per_task = [diff_task(tid, arms["CARD_NEG"][tid], arms["CARD_FADE"][tid])
                for tid in task_ids if tid not in missing]

    # Within-arm: every cell carries the arm's exact card block exactly once, and
    # after removing it equals the expected no-card base for THAT task (questions
    # differ across tasks, so bases are compared per task, not globally).
    within = {}
    for arm in ARMS:
        all_single = True
        all_base_ok = True
        for tid, prompt in arms[arm].items():
            base = _remove_card(prompt, M2.CARDS[arm])
            if base is None:
                all_single = False
                continue
            expected_base = M2.build_r1_prompt(M2.TASK_BY_ID[tid], "__NO_CARD__")
            if base != expected_base:
                all_base_ok = False
        within[arm] = {
            "n_cells": len(arms[arm]),
            "single_card_block_all_cells": all_single,
            "base_equals_expected_no_card_prompt_per_task": all_base_ok,
        }

    all_card_only = (not missing) and all(d["diff_is_card_only"] for d in per_task)
    return {
        "check": "m2_card_only_diff_v1",
        "sources": {a: sources[a] for a in ARMS},
        "card_texts": {"CARD_NEG": M2.CARD_NEG, "CARD_FADE": M2.CARD_FADE},
        "n_tasks_compared": len(per_task),
        "missing_tasks": missing,
        "within_arm": within,
        "per_task": per_task,
        "arms_differ_only_by_card_block": all_card_only,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M2 card-only-diff check (stored prompts only)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--compact", action="store_true",
                    help="print only per-task task_id -> diff_is_card_only")
    a = ap.parse_args(argv)
    result = run_check(a.data_dir)
    if a.compact:
        for d in result["per_task"]:
            print(f"{d['task_id']:<26} card_only={d['diff_is_card_only']}  "
                  f"base_identical={d['base_identical']}")
        print(f"ALL arms differ only by card block: {result['arms_differ_only_by_card_block']}")
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["arms_differ_only_by_card_block"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
