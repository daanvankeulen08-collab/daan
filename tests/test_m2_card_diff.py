"""Tests for the committed M2 card-only-diff check."""
from __future__ import annotations

import json

from block15 import m2_card_diff as CD
from block15 import m2_research as M2
from block15 import m2_tasks as M2T


def build_prompt(task, card):
    parts = [task.question]
    if card is not None:
        parts.append(card)
    parts.append(M2.tool_schema_block())
    parts.append("Return a JSON object matching the tool-request schema. Decide whether "
                 "to call the tool; do not explain your reasoning.")
    return "\n\n".join(parts)


def test_diff_task_card_only_synthetic():
    t = M2T.TASKS[0]
    neg = build_prompt(t, M2.CARD_NEG)
    fade = build_prompt(t, M2.CARD_FADE)
    d = CD.diff_task(t.id, neg, fade)
    assert d["card_neg_present_once"] and d["card_fade_present_once"]
    assert d["base_identical"] is True
    assert d["sentinel_prompts_identical"] is True
    assert d["diff_is_card_only"] is True
    assert d["n_char_diff_spans"] > 0  # informational char-level spans
    assert d["raw_prompts_identical"] is False


def test_diff_task_detects_non_card_change():
    t = M2T.TASKS[0]
    neg = build_prompt(t, M2.CARD_NEG)
    fade = build_prompt(t, M2.CARD_FADE) + " EXTRA"
    d = CD.diff_task(t.id, neg, fade)
    assert d["base_identical"] is False
    assert d["diff_is_card_only"] is False


def test_diff_task_detects_missing_card():
    t = M2T.TASKS[0]
    neg = build_prompt(t, None)  # no card at all
    fade = build_prompt(t, M2.CARD_FADE)
    d = CD.diff_task(t.id, neg, fade)
    assert d["card_neg_present_once"] is False
    assert d["diff_is_card_only"] is False


def test_remove_card_rejects_zero_or_multiple():
    assert CD._remove_card("abc", M2.CARD_NEG) is None
    prompt = "X\n\n" + M2.CARD_NEG + "\n\nY\n\n" + M2.CARD_NEG
    assert CD._remove_card(prompt, M2.CARD_NEG) is None


def test_run_check_stored_m2_prompts():
    """On the stored M2 artifacts, confirm arms differ only by the card block."""
    result = CD.run_check("data")
    assert result["n_tasks_compared"] == 30
    assert result["missing_tasks"] == []
    assert all(v["single_card_block_all_cells"] for v in result["within_arm"].values())
    assert all(v["base_equals_expected_no_card_prompt_per_task"]
               for v in result["within_arm"].values())
    assert result["arms_differ_only_by_card_block"] is True
    assert all(d["diff_is_card_only"] for d in result["per_task"])
