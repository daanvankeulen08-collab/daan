"""A1 tests: tool-schema validator accepts TOOL_SCHEMA, rejects malformed variants."""
from __future__ import annotations

import copy

import pytest

from block15 import skill_tools as T
from block15 import tool_schema_validator as V
from block15 import contract_v2 as CV


def _old_guard(schema) -> bool:
    """Replicate the OLD contract_v2 guard outcome (True = accepted)."""
    try:
        CV.validate_v2({}, schema)
        return True
    except (ValueError, KeyError, TypeError):
        return False


def test_old_guard_rejected_tool_schema():
    assert _old_guard(T.TOOL_SCHEMA) is False


def test_prevunguarded_keywords_are_now_covered():
    # Keywords appearing in TOOL_SCHEMA that the old validator did not guard.
    old_allowed = set()
    for s in CV._ALLOWED_KEYWORDS.values():
        old_allowed |= set(s)
    schema_keywords = {"anyOf", "const", "enum"}
    assert schema_keywords.isdisjoint(old_allowed)
    assert schema_keywords.issubset(V.ASSERTION_KEYWORDS)


def test_accepts_current_tool_schema():
    V.validate_schema(T.TOOL_SCHEMA)  # does not raise


def test_accepts_nullable_variant_f2():
    f2 = copy.deepcopy(T.TOOL_SCHEMA)
    obj_branch = f2["properties"]["tool_request"]["anyOf"][1]
    f2["properties"]["tool_request"] = {
        "type": ["object", "null"],
        "additionalProperties": obj_branch["additionalProperties"],
        "required": obj_branch["required"],
        "properties": obj_branch["properties"],
    }
    V.validate_schema(f2)


def test_rejects_malformed_variants():
    bad = []
    x = copy.deepcopy(T.TOOL_SCHEMA); x["properties"]["tool_request"]["anyOf"] = {}; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["properties"]["tool_request"]["anyOf"] = []; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["properties"]["tool_request"]["anyOf"][1]["properties"]["tool"] = {"const": T.TOOL_NAME, "type": "bogus"}; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["properties"]["missing_process"]["enum"] = []; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["type"] = ["object", "bogus"]; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["properties"]["tool_request"]["anyOf"][1]["unknown_kw"] = 1; bad.append(x)
    x = copy.deepcopy(T.TOOL_SCHEMA); x["required"] = ["not_declared"]; bad.append(x)
    for i, schema in enumerate(bad):
        with pytest.raises(ValueError):
            V.validate_schema(schema)


def test_instance_validation_null_and_object():
    null_req = {"tool_request": None, "missing_process": "no_tool_needed"}
    obj_req = {"tool_request": {"tool": T.TOOL_NAME,
                                "arguments": {"a": 1, "b": 2, "c": 3, "n_max": 64}}}
    assert V.validate_instance(null_req, T.TOOL_SCHEMA) == []
    assert V.validate_instance(obj_req, T.TOOL_SCHEMA) == []
    bad = {"tool_request": {"tool": "wrong_tool"}, "bogus": 1}
    assert V.validate_instance(bad, T.TOOL_SCHEMA)
