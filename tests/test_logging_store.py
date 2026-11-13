"""Tests for SQLite storage and the append-only JSONL journal."""

from __future__ import annotations

import json

from mdl.logging_store import ResearchStore


def test_experiment_is_stored_in_sqlite_and_jsonl(store):
    experiment_id = store.create_experiment(
        seed="seed-1",
        model="lfm3:latest",
        model_digest="sha256:abc",
        parameters={"temperature": 0.1},
        context_limit=8192,
    )
    store.log_step(
        experiment_id,
        "hypothesis",
        "ok",
        {"statement": "All coefficients are non-negative."},
        latency_ms=1.5,
    )
    store.log_step(
        experiment_id,
        "verification",
        "passed",
        {"status": "passed"},
        latency_ms=2.5,
    )
    store.set_experiment_fields(
        experiment_id,
        hypothesis_json={"statement": "All coefficients are non-negative."},
    )
    store.finish_experiment(
        experiment_id,
        "completed",
        latency_ms=3.5,
        token_usage={"eval_count": 5},
    )

    row = store.get_experiment(experiment_id)
    assert row is not None
    assert row["status"] == "completed"
    assert row["model_digest"] == "sha256:abc"
    assert json.loads(row["hypothesis_json"])["statement"].startswith("All")
    assert json.loads(row["token_usage_json"])["eval_count"] == 5

    steps = store.list_steps(experiment_id)
    assert [step["seq"] for step in steps] == [1, 2]
    assert steps[0]["payload"]["statement"].startswith("All")

    events = store.read_events(experiment_id)
    assert events[0]["type"] == "experiment_started"
    assert events[-1]["type"] == "experiment_finished"
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))

    report = store.verify_jsonl()
    assert report["valid"] is True
    assert report["events"] == len(events)


def test_jsonl_is_append_only(store):
    experiment_id = store.create_experiment(
        seed=None,
        model="lfm3:latest",
        model_digest=None,
        parameters={},
        context_limit=8192,
    )
    path = store.jsonl_path
    before = path.read_bytes()
    store.log_step(experiment_id, "plan", "ok", {"steps": ["a"]})
    after = path.read_bytes()
    assert after.startswith(before)
    assert len(after) > len(before)


def test_tampering_is_detected(store):
    experiment_id = store.create_experiment(
        seed=None,
        model="lfm3:latest",
        model_digest=None,
        parameters={},
        context_limit=8192,
    )
    store.log_step(experiment_id, "plan", "ok", {"steps": ["a"]})
    store.log_step(experiment_id, "verification", "passed", {"status": "passed"})

    lines = store.jsonl_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[1])
    event["payload"]["data"]["steps"] = ["tampered"]
    lines[1] = json.dumps(
        event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    store.jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = store.verify_jsonl()
    assert report["valid"] is False
    assert report["line"] == 2


def test_store_can_be_reopened(settings):
    first = ResearchStore(settings.db_path, settings.jsonl_path)
    experiment_id = first.create_experiment(
        seed=None,
        model="lfm3:latest",
        model_digest=None,
        parameters={},
        context_limit=8192,
    )
    first.log_step(experiment_id, "plan", "ok", {"steps": ["a"]})
    first.close()

    second = ResearchStore(settings.db_path, settings.jsonl_path)
    try:
        assert second.verify_jsonl()["valid"] is True
        assert len(second.read_events(experiment_id)) == 2
    finally:
        second.close()
