"""Tool-schema validator covering the JSON-Schema keywords the answer validator
in ``block15.contract_v2.validate_v2`` does not implement.

``validate_v2`` deliberately raises on ``anyOf``, ``const`` and ``enum`` (and on a
``type`` given as a list).  That is correct for the answer contract, which uses
none of them, but the *tool* schema uses all three.  This module is an additive,
separate validator for tool schemas.  It

  * structurally validates a schema document (raising on malformed schemas), and
  * validates a data instance against a schema document (returning a violation
    list, so callers can assert acceptance/rejection).

Supported assertion keywords: type (string or list, including "null" and
"integer"), anyOf, const, enum, properties, required, additionalProperties,
items, minItems, maxItems, minLength, maxLength, minimum, maximum.  Annotation
keywords are accepted but ignored.  Any other keyword raises: a constraint that
is not implemented must never be silently dropped.

No generation; pure validation logic.
"""
from __future__ import annotations

ANNOTATION_KEYWORDS = frozenset(
    {"title", "description", "$schema", "$comment", "default", "examples"}
)
ASSERTION_KEYWORDS = frozenset(
    {
        "type", "anyOf", "const", "enum", "properties", "required",
        "additionalProperties", "items", "minItems", "maxItems", "minLength",
        "maxLength", "minimum", "maximum",
    }
)
VALID_TYPES = frozenset(
    {"null", "boolean", "object", "array", "string", "number", "integer"}
)


def validate_schema(schema: object, path: str = "$") -> None:
    """Raise ValueError if ``schema`` is not a well-formed supported schema."""
    if not isinstance(schema, dict):
        raise ValueError(f"{path}: schema node must be an object")
    unknown = sorted(set(schema) - ASSERTION_KEYWORDS - ANNOTATION_KEYWORDS)
    if unknown:
        raise ValueError(f"{path}: unsupported schema keyword(s): {', '.join(unknown)}")

    if "type" in schema:
        t = schema["type"]
        if isinstance(t, str):
            if t not in VALID_TYPES:
                raise ValueError(f"{path}: unknown type {t!r}")
        elif isinstance(t, list):
            if not t:
                raise ValueError(f"{path}: type list must not be empty")
            for entry in t:
                if not isinstance(entry, str) or entry not in VALID_TYPES:
                    raise ValueError(f"{path}: invalid type entry {entry!r}")
            if len(set(t)) != len(t):
                raise ValueError(f"{path}: duplicate types in type list")
        else:
            raise ValueError(f"{path}: type must be a string or a list of strings")

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"{path}.anyOf: must be a non-empty list of schemas")
        for i, branch in enumerate(branches):
            validate_schema(branch, f"{path}.anyOf[{i}]")

    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{path}.enum: must be a non-empty list")

    if "properties" in schema:
        props = schema["properties"]
        if not isinstance(props, dict):
            raise ValueError(f"{path}.properties: must be an object")
        for name, rule in props.items():
            validate_schema(rule, f"{path}.properties.{name}")

    if "required" in schema:
        req = schema["required"]
        if not isinstance(req, list) or not all(isinstance(x, str) for x in req):
            raise ValueError(f"{path}.required: must be a list of strings")
        if len(set(req)) != len(req):
            raise ValueError(f"{path}.required: duplicate names")
        if "properties" in schema:
            extra = [x for x in req if x not in schema["properties"]]
            if extra:
                raise ValueError(f"{path}.required: undeclared name(s): {extra}")

    if "additionalProperties" in schema:
        ap = schema["additionalProperties"]
        if isinstance(ap, dict):
            validate_schema(ap, f"{path}.additionalProperties")
        elif not isinstance(ap, bool):
            raise ValueError(f"{path}.additionalProperties: must be bool or schema")

    if "items" in schema:
        items = schema["items"]
        if not isinstance(items, dict):
            raise ValueError(f"{path}.items: must be a schema object")
        validate_schema(items, f"{path}.items")

    for key in ("minimum", "maximum"):
        if key in schema and not isinstance(schema[key], (int, float)):
            raise ValueError(f"{path}.{key}: must be a number")
    if "minimum" in schema and "maximum" in schema:
        if schema["minimum"] > schema["maximum"]:
            raise ValueError(f"{path}: minimum greater than maximum")
    for key in ("minItems", "maxItems", "minLength", "maxLength"):
        if key in schema and (not isinstance(schema[key], int)
                              or isinstance(schema[key], bool)
                              or schema[key] < 0):
            raise ValueError(f"{path}.{key}: must be a non-negative integer")
    if "minItems" in schema and "maxItems" in schema:
        if schema["minItems"] > schema["maxItems"]:
            raise ValueError(f"{path}: minItems greater than maxItems")
    if "minLength" in schema and "maxLength" in schema:
        if schema["minLength"] > schema["maxLength"]:
            raise ValueError(f"{path}: minLength greater than maxLength")


def _type_ok(value: object, t: str) -> bool:
    if t == "null":
        return value is None
    if t == "boolean":
        return isinstance(value, bool)
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def validate_instance(value: object, schema: dict, path: str = "$",
                      violations: list[str] | None = None) -> list[str]:
    """Return a list of violations of ``schema`` by ``value`` (empty = valid)."""
    if violations is None:
        violations = []

    t = schema.get("type")
    if t is not None:
        types = [t] if isinstance(t, str) else list(t)
        if not any(_type_ok(value, x) for x in types):
            violations.append(f"{path}: expected type {types}, got {type(value).__name__}")
            return violations

    if "const" in schema and value != schema["const"]:
        violations.append(f"{path}: value does not equal const {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        violations.append(f"{path}: value {value!r} not in enum")

    if "anyOf" in schema:
        ok = False
        for branch in schema["anyOf"]:
            if not validate_instance(value, branch, path, None):
                ok = True
                break
        if not ok:
            violations.append(f"{path}: value satisfies no anyOf branch")

    object_applies = (
        t is None or t == "object" or (isinstance(t, list) and "object" in t)
    )
    if isinstance(value, dict) and object_applies:
        for name in schema.get("required", []):
            if name not in value:
                violations.append(f"{path}: missing required property {name!r}")
        props = schema.get("properties", {})
        ap = schema.get("additionalProperties", True)
        for name, val in value.items():
            if name in props:
                validate_instance(val, props[name], f"{path}.{name}", violations)
            elif ap is False:
                violations.append(f"{path}: unexpected property {name!r}")
            elif isinstance(ap, dict):
                validate_instance(val, ap, f"{path}.{name}", violations)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            violations.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            violations.append(f"{path}: more than maxItems")
        if isinstance(schema.get("items"), dict):
            for i, val in enumerate(value):
                validate_instance(val, schema["items"], f"{path}[{i}]", violations)

    if isinstance(value, str) and not isinstance(value, bool):
        if "minLength" in schema and len(value) < schema["minLength"]:
            violations.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            violations.append(f"{path}: longer than maxLength")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            violations.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            violations.append(f"{path}: above maximum")

    return violations
