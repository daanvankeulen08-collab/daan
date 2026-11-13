"""Tests for lenient JSON extraction from model responses."""

from __future__ import annotations

import pytest

from mdl.errors import ModelOutputError
from mdl.ollama_client import _extract_json


def test_extracts_plain_json():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extracts_fenced_json():
    content = '```json\n{"tool": "symbolic_expand", "arguments": {}}\n```'
    assert _extract_json(content) == {
        "tool": "symbolic_expand",
        "arguments": {},
    }


def test_extracts_json_with_surrounding_prose():
    content = 'Here is the answer: {"a": {"b": 2}} and nothing else.'
    assert _extract_json(content) == {"a": {"b": 2}}


@pytest.mark.parametrize(
    "content",
    ["", "no json here", "{broken", "[1, 2, 3]"],
)
def test_rejects_invalid_json(content):
    with pytest.raises(ModelOutputError):
        _extract_json(content)
