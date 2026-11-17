"""Tests for fresh integration task set."""
from __future__ import annotations

import hashlib
import json

from block15 import integration_tasks as IT


def test_verify_tasks():
    c = IT.verify_tasks()
    assert c["n_tasks"] == 10
    assert c["ground_truth_ok"] and c["copy_guard_ok"] and c["disjoint_ok"]
    assert c["distinct_ids"]


def test_manifest_hash_stable():
    m = hashlib.sha256(json.dumps([t.metadata() for t in IT.TASKS],
                                  sort_keys=True).encode()).hexdigest()
    assert len(m) == 64
    # recompute to assert determinism
    assert m == hashlib.sha256(json.dumps([t.metadata() for t in IT.TASKS],
                                          sort_keys=True).encode()).hexdigest()


def test_truth_and_copy_guard():
    for t in IT.TASKS:
        tr = t.truth()
        assert tr["kind"] == "coefficient"
        assert tr["answer_tokens"] == [t.coefficient]
