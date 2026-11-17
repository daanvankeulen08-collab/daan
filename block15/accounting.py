"""Canonical failure accounting for all order-v2 / diagnosis / placebo studies.

ONE machine-computed convention, used everywhere (STEP 1 of the placebostudy task):

* ``failed_cells``   = cells with no audited pass (``primary_correct`` is False).
* ``failure_flags``  = per-cell list drawn from the FIXED enumerated set
                       ``FAILURE_FLAG_SET`` below.
* ``failure_events`` = sum of ``len(failure_flags)`` over NON-PASS cells only.
                       Passing cells contribute ZERO failure events.

This module is additive and read-only with respect to stored result cells: it
recomputes flags from the raw fields each harness persisted (re-parsing
``raw_content`` with the same fresh parser), so it works whether or not a row
happens to carry a precomputed ``failure_flags`` field.  No result cell is
mutated.
"""

from __future__ import annotations

from pathlib import Path

from block15 import order_v2_research as O

# FIXED enumerated set — never extended ad hoc within a report.
FAILURE_FLAG_SET: frozenset[str] = frozenset({
    "call_error",
    "parse_failed",
    "schema_violation",
    "truncated",
    "primary_wrong",
    "confidence_out_of_range",
    "copy_possible",
})

_CALL_ERROR_STATUSES = frozenset({"timeout", "model_error", "error", "output_error"})


def failure_flags(row: dict) -> list[str]:
    """Return the sorted subset of FAILURE_FLAG_SET that applies to a cell.

    Derived from raw persisted fields only.  ``parseable`` is re-derived with
    a fresh parse of ``raw_content`` rather than trusting a stored boolean, so
    ORDER_V2 rows and DIAGNOSIS/PLACEBO rows are handled identically.
    """
    flags: set[str] = set()

    if row.get("status") in _CALL_ERROR_STATUSES:
        flags.add("call_error")

    parsed = O.fresh_parse(row.get("raw_content"))
    parseable = parsed is not None
    if not parseable:
        flags.add("parse_failed")
    elif not row.get("validate_v2_ok", False):
        flags.add("schema_violation")

    if row.get("done_reason") == "length":
        flags.add("truncated")

    if not row.get("primary_correct", False):
        flags.add("primary_wrong")

    conf = row.get("confidence_raw")
    if not (
        isinstance(conf, (int, float))
        and not isinstance(conf, bool)
        and 0.0 <= float(conf) <= 1.0
    ):
        flags.add("confidence_out_of_range")

    if row.get("copy_possible", False):
        flags.add("copy_possible")

    assert flags.issubset(FAILURE_FLAG_SET), f"unknown flag(s): {flags - FAILURE_FLAG_SET}"
    return sorted(flags)


def failed_cells(rows: list[dict]) -> int:
    """Cells with no audited pass."""
    return sum(1 for r in rows if not r.get("primary_correct", False))


def failure_events(rows: list[dict]) -> int:
    """Sum of len(failure_flags) over NON-PASS cells only.

    A passing cell contributes zero even if one of its raw fields looks
    anomalous (e.g. a stray confidence value): the pass is authoritative for
    the endpoint, and failure accounting quantifies how cells failed to pass.
    """
    total = 0
    for r in rows:
        if r.get("primary_correct", False):
            continue
        total += len(failure_flags(r))
    return total


def account(rows: list[dict]) -> dict:
    """Full accounting summary for a list of cells under the single convention."""
    passing = [r for r in rows if r.get("primary_correct", False)]
    return {
        "cells": len(rows),
        "audited_passes": len(passing),
        "failed_cells": failed_cells(rows),
        "failure_events": failure_events(rows),
    }


def partition(rows: list[dict]) -> dict:
    """Distribution of individual failure flags over NON-PASS cells only."""
    dist: dict[str, int] = {}
    for r in rows:
        if r.get("primary_correct", False):
            continue
        for flag in failure_flags(r):
            dist[flag] = dist.get(flag, 0) + 1
    return dict(sorted(dist.items()))
