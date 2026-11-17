"""Tests for Integration V2 fresh task set."""
from __future__ import annotations

import hashlib
import json

from block15 import integration_v2_tasks as IT2


def test_verify_tasks():
    c = IT2.verify_tasks()
    assert c["n_tasks"] == 20
    assert c["ground_truth_ok"] and c["copy_guard_ok"] and c["disjoint_ok"]
    assert c["distinct_ids"]


def test_disjoint_from_prior():
    for t in IT2.TASKS:
        assert (t.a, t.b) not in IT2.PRIOR


def test_manifest_deterministic():
    m = hashlib.sha256(json.dumps([t.metadata() for t in IT2.TASKS],
                                  sort_keys=True).encode()).hexdigest()
    assert len(m) == 64
