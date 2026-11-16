"""Contract v2: one answer shape with two field orderings.

This module is additive.  It does not import or modify the frozen ceiling and
held-out harnesses (``block15/ceiling_research.py`` and
``block15/heldout_research.py``) and it performs no generation.

``SYSTEM_PROMPT_V2`` is Round 3's ``SYSTEM_PROMPT``, copied verbatim from
``block15/tasks.py`` (``SYSTEM_PROMPT``, lines 15-22; re-exported unchanged by
``block15/round3_tasks.py``):

    You are LFM3, a local mathematical reasoning model. Solve the task
    independently from the information given. Do not claim to have used a
    tool unless its result is provided to you. Return exactly one JSON object
    matching the required schema. Use concise reasoning (at most 120 words).
    Every string value must be on one line: do not put literal newline
    characters inside a string. Do not use markdown or code fences.

Both schemas have exactly the same shape and constraints.  Only the insertion
order of ``required`` and ``properties`` differs.  ``validate_v2`` enforces
every declared constraint and never repairs, clamps, or coerces values; it
raises on any schema keyword it does not implement instead of silently
under-validating.

Contract v2 uses one instruction shared by both arms.  The ceiling study's
instruction was constant across arms, which is what allowed schema-order
attribution.  Deliberately neutral wording preserves that: the shared
instruction lists the fields alphabetically and contains no ordering language,
so only the schema's required/property order varies between arms.

``emitted_key_order`` and ``emission_order_provenance`` let a runner persist
the parsed field order and whether it matches each arm's required order.
"""

from __future__ import annotations

__all__ = [
    "ANSWER_FIRST_V2",
    "DERIVATION_FIRST_V2",
    "INSTRUCTIONS_V2",
    "OUTPUT_INSTRUCTION_V2",
    "SCHEMAS_V2",
    "SYSTEM_PROMPT_V2",
    "emission_order_provenance",
    "emitted_key_order",
    "validate_v2",
]

SYSTEM_PROMPT_V2 = (
    "You are LFM3, a local mathematical reasoning model. Solve the task "
    "independently from the information given. Do not claim to have used a "
    "tool unless its result is provided to you. Return exactly one JSON object "
    "matching the required schema. Use concise reasoning (at most 120 words). "
    "Every string value must be on one line: do not put literal newline "
    "characters inside a string. Do not use markdown or code fences."
)


def _properties() -> dict:
    """Return fresh property rules shared in substance by both arms."""
    return {
        "derivation": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1, "maxLength": 500},
        },
        "final_answer": {"type": "string", "minLength": 1, "maxLength": 1400},
        "uncertainty": {"type": "string", "maxLength": 700},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    }


def _schema(required: tuple[str, ...]) -> dict:
    """Build an object schema with properties inserted in ``required`` order."""
    rules = _properties()
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": {name: rules[name] for name in required},
    }


ANSWER_FIRST_V2: dict = _schema(
    ("final_answer", "derivation", "uncertainty", "confidence")
)
DERIVATION_FIRST_V2: dict = _schema(
    ("derivation", "final_answer", "uncertainty", "confidence")
)

OUTPUT_INSTRUCTION_V2 = (
    "\n\nReturn a JSON object with exactly these fields: confidence (number "
    "from 0 to 1), derivation (array of short, independently checkable steps), "
    "final_answer (string), uncertainty (string). Put every string on one "
    "line; do not include literal newline characters inside string values. "
    "Do not use markdown or code fences."
)

SCHEMAS_V2: dict[str, dict] = {
    "answer_first": ANSWER_FIRST_V2,
    "derivation_first": DERIVATION_FIRST_V2,
}

INSTRUCTIONS_V2: dict[str, str] = {
    "answer_first": OUTPUT_INSTRUCTION_V2,
    "derivation_first": OUTPUT_INSTRUCTION_V2,
}


_ALLOWED_KEYWORDS: dict[str, frozenset[str]] = {
    "object": frozenset(
        {"type", "additionalProperties", "required", "properties"}
    ),
    "array": frozenset({"type", "minItems", "maxItems", "items"}),
    "string": frozenset({"type", "minLength", "maxLength"}),
    "number": frozenset({"type", "minimum", "maximum"}),
}


def _assert_supported_schema(schema: object, path: str = "$") -> None:
    """Raise if ``schema`` uses any keyword or type this validator ignores."""
    if not isinstance(schema, dict):
        raise ValueError(f"{path}: schema node must be an object")
    expected = schema.get("type")
    if expected not in _ALLOWED_KEYWORDS:
        raise ValueError(
            f"{path}: unsupported or missing schema type {expected!r}"
        )
    unsupported = sorted(set(schema) - _ALLOWED_KEYWORDS[expected])
    if unsupported:
        raise ValueError(
            f"{path}: unsupported schema keyword(s): {', '.join(unsupported)}"
        )

    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, dict):
            raise ValueError(f"{path}.properties: must be an object")
        for name, rule in properties.items():
            _assert_supported_schema(rule, f"{path}.properties.{name}")

    if "additionalProperties" in schema:
        additional = schema["additionalProperties"]
        if isinstance(additional, dict):
            _assert_supported_schema(
                additional, f"{path}.additionalProperties"
            )
        elif not isinstance(additional, bool):
            raise ValueError(
                f"{path}.additionalProperties: must be a boolean or schema"
            )

    if "items" in schema:
        items = schema["items"]
        if not isinstance(items, dict):
            raise ValueError(f"{path}.items: must be a schema object")
        _assert_supported_schema(items, f"{path}.items")


def _type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__


def _validate_node(
    value: object,
    schema: dict,
    path: str,
    violations: list[str],
) -> None:
    expected = schema.get("type")
    if expected is None:
        violations.append(f"{path}: schema declares no type")
        return

    if expected == "object":
        if not isinstance(value, dict):
            violations.append(
                f"{path}: expected object, got {_type_name(value)}"
            )
            return
        for name in schema.get("required", []):
            if name not in value:
                violations.append(f"{path}: missing required property {name!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for name in value:
            if name in properties:
                continue
            if additional is False:
                violations.append(f"{path}: unexpected property {name!r}")
            elif isinstance(additional, dict):
                _validate_node(
                    value[name], additional, f"{path}.{name}", violations
                )
        for name, rule in properties.items():
            if name in value:
                _validate_node(value[name], rule, f"{path}.{name}", violations)
        return

    if expected == "array":
        if not isinstance(value, list):
            violations.append(
                f"{path}: expected array, got {_type_name(value)}"
            )
            return
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            violations.append(
                f"{path}: expected at least {min_items} items, got {len(value)}"
            )
        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            violations.append(
                f"{path}: expected at most {max_items} items, got {len(value)}"
            )
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_node(item, items, f"{path}[{index}]", violations)
        return

    if expected == "string":
        if not isinstance(value, str):
            violations.append(
                f"{path}: expected string, got {_type_name(value)}"
            )
            return
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            violations.append(
                f"{path}: expected at least {min_length} characters, "
                f"got {len(value)}"
            )
        max_length = schema.get("maxLength")
        if max_length is not None and len(value) > max_length:
            violations.append(
                f"{path}: expected at most {max_length} characters, "
                f"got {len(value)}"
            )
        return

    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            violations.append(
                f"{path}: expected number, got {_type_name(value)}"
            )
            return
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            violations.append(f"{path}: expected >= {minimum}, got {value!r}")
        maximum = schema.get("maximum")
        if maximum is not None and value > maximum:
            violations.append(f"{path}: expected <= {maximum}, got {value!r}")
        return

    violations.append(f"{path}: unsupported schema type {expected!r}")


def validate_v2(obj: object, schema: dict) -> tuple[bool, list[str]]:
    """Validate ``obj`` against every constraint declared by ``schema``.

    Returns ``(ok, violations)``.  Values are checked as-is: nothing is
    repaired, clamped, coerced, or dropped.  Raises ``ValueError`` if the
    schema uses a keyword or type this validator does not implement.
    """
    _assert_supported_schema(schema)
    violations: list[str] = []
    _validate_node(obj, schema, "$", violations)
    return not violations, violations


def emitted_key_order(obj: object) -> tuple[str, ...]:
    """Return ``obj``'s parsed key order, or ``()`` for a non-object."""
    if not isinstance(obj, dict):
        return ()
    return tuple(obj.keys())


def emission_order_provenance(
    obj: object,
    own_schema: dict,
    other_schema: dict,
) -> dict:
    """Return order-only provenance for one arm's result row.

    ``matches_own_schema`` and ``matches_other_schema`` compare the emitted
    key order with each schema's ``required`` order.  This is an order check
    only; it does not validate types, lengths, or values.
    """
    emitted = emitted_key_order(obj)
    return {
        "emitted_key_order": emitted,
        "matches_own_schema": emitted == tuple(own_schema["required"]),
        "matches_other_schema": emitted == tuple(other_schema["required"]),
    }
