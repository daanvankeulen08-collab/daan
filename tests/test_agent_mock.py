"""Deterministic agent tests using a scripted fake LFM3 client."""

from __future__ import annotations

from conftest import (
    EXPECTED_EXPANSION,
    HYPOTHESIS,
    INTERPRETATION,
    PLAN,
    REQUEST,
    FakeClient,
)
from mdl.agent import ResearchAgent
from mdl.context_engine import ResearchContext
from mdl.errors import ModelOutputError
from mdl.orchestrator import ToolOrchestrator
from mdl.verifier import VerificationStatus


def _agent(settings, store, script):
    client = FakeClient(script)
    agent = ResearchAgent(
        settings, client, ToolOrchestrator(timeout_s=10.0), store
    )
    return agent, client


def test_full_loop_with_mocked_model(settings, store):
    agent, client = _agent(
        settings,
        store,
        [HYPOTHESIS, PLAN, REQUEST, INTERPRETATION],
    )
    outcome = agent.run(seed="test seed", allow_repair=False)

    assert outcome.status == "completed"
    assert outcome.verification is not None
    assert outcome.verification.status is VerificationStatus.PASSED
    assert outcome.tool_result is not None
    assert outcome.tool_result.expanded == EXPECTED_EXPANSION
    assert outcome.tool_result.term_count == 9
    assert outcome.tool_result.total_degree == 8
    assert outcome.interpretation is not None
    assert outcome.interpretation.supports_hypothesis is True
    assert len(client.calls) == 4

    row = store.get_experiment(outcome.experiment_id)
    assert row["status"] == "completed"
    assert row["model_digest"] == "sha256:fake-digest"
    assert "non-negative" in row["hypothesis_json"]

    steps = store.list_steps(outcome.experiment_id)
    statuses = {(step["kind"], step["status"]) for step in steps}
    assert ("tool_validation", "accepted") in statuses
    assert ("tool_execution", "ok") in statuses
    assert ("verification", "passed") in statuses
    assert ("context_encode", "ok") in statuses

    events = store.read_events(outcome.experiment_id)
    assert events[0]["type"] == "experiment_started"
    assert events[-1]["type"] == "experiment_finished"
    assert store.verify_jsonl()["valid"] is True

    assert outcome.context is not None
    decoded = ResearchContext.decode(outcome.context.encode())
    assert decoded == outcome.context
    assert decoded.hypotheses[0].status == "supported"
    assert decoded.relations[0].lhs == "(x + 1)**8"


def test_invalid_tool_request_is_repaired(settings, store):
    invalid = {"tool": "symbolic_expand", "arguments": {"expression": "x/y"}}
    agent, _ = _agent(
        settings,
        store,
        [HYPOTHESIS, PLAN, invalid, REQUEST, INTERPRETATION],
    )
    outcome = agent.run(seed="repair", allow_repair=True)

    assert outcome.status == "completed"
    assert outcome.verification.status is VerificationStatus.PASSED

    steps = store.list_steps(outcome.experiment_id)
    validations = [step for step in steps if step["kind"] == "tool_validation"]
    assert validations[0]["status"] == "rejected"
    assert validations[-1]["status"] == "accepted_after_repair"


def test_invalid_tool_request_rejected_without_repair(settings, store):
    invalid = {"tool": "symbolic_expand", "arguments": {"expression": "x/y"}}
    agent, _ = _agent(settings, store, [HYPOTHESIS, PLAN, invalid])
    outcome = agent.run(seed="reject", allow_repair=False)

    assert outcome.status == "rejected"
    assert outcome.rejection is not None
    assert "illegal character" in outcome.rejection
    assert outcome.tool_result is None

    steps = store.list_steps(outcome.experiment_id)
    assert not any(step["kind"] == "tool_execution" for step in steps)
    assert any(
        step["kind"] == "tool_validation" and step["status"] == "rejected"
        for step in steps
    )
    assert store.verify_jsonl()["valid"] is True


def test_invalid_json_is_retried_once(settings, store):
    agent, client = _agent(
        settings,
        store,
        [
            ModelOutputError("not json"),
            HYPOTHESIS,
            PLAN,
            REQUEST,
            INTERPRETATION,
        ],
    )
    outcome = agent.run(seed="retry-json")

    assert outcome.status == "completed"
    assert len(client.calls) == 5
    steps = store.list_steps(outcome.experiment_id)
    assert any(
        step["kind"] == "model_call" and step["status"] == "invalid_json"
        for step in steps
    )


def test_invalid_schema_is_retried_once(settings, store):
    agent, client = _agent(
        settings,
        store,
        [{}, HYPOTHESIS, PLAN, REQUEST, INTERPRETATION],
    )
    outcome = agent.run(seed="retry-schema")

    assert outcome.status == "completed"
    assert len(client.calls) == 5
    steps = store.list_steps(outcome.experiment_id)
    assert any(
        step["kind"] == "model_call" and step["status"] == "invalid_schema"
        for step in steps
    )
