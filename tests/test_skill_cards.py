"""Offline tests for skill_cards (no generation)."""

from __future__ import annotations

from block15 import skill_cards as C
from block15 import skill_tools as T


def test_levels_and_l0_has_no_card():
    assert set(C.LEVELS) == {"L3", "L0"}
    assert C.assistance_text("L0") == ""
    assert C.assistance_text("L3")


def test_l3_card_fields_present():
    for k in ("trigger", "procedure", "tool_reference", "verification",
              "failure_modes", "provenance"):
        assert k in C.L3_CARD
    assert C.L3_CARD["tool_reference"] == T.TOOL_NAME
    assert C.L3_CARD["provenance"]["assistance_level"] == "L3"
    assert C.L3_CARD["provenance"]["task_hash"] is None


def test_no_gt_token_leak_and_example_not_pilot():
    r = C.verify_assistance_no_gt()
    assert all(not v["leaks"] for k, v in r.items() if isinstance(v, dict))
    assert r["example_not_pilot"] is True


def test_tool_schema_identical_text():
    # Both levels present the same tool_schema_block() string.
    # The harness will append this constant to both prompts; assert it is stable.
    a = C.tool_schema_block()
    assert C.tool_schema_block() == a
    assert T.TOOL_NAME in a


def test_example_numbers_avoid_all_task_tokens():
    from block15 import order_v2_research as O
    gt = O.ground_truth_manifest()
    alltok = set()
    for g in gt.values():
        alltok.update(int(v) for v in g["answer_tokens"])
    r = C.EXAMPLE["tool_result"]
    ex = {r["n"], r["value"], *r["factors"]}
    assert not (ex & alltok)
