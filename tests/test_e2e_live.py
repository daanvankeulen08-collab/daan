"""One real end-to-end research loop against the local LFM3 model.

Marked ``live``; it is excluded from the default test run and executed once
during Block 1 verification.
"""

from __future__ import annotations

import pytest

from mdl.agent import ResearchAgent
from mdl.config import load_settings
from mdl.errors import ToolValidationError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient
from mdl.orchestrator import ToolOrchestrator
from mdl.verifier import VerificationStatus

pytestmark = pytest.mark.live

SEED = (
    "Investigate whether the expansion of (x + 1)^8 has only non-negative "
    "integer coefficients."
)


def test_live_lfm3_research_loop(tmp_path):
    settings = load_settings(
        db_path=tmp_path / "live.sqlite3",
        jsonl_path=tmp_path / "live_events.jsonl",
    )
    client = OllamaClient(settings)
    try:
        if not client.health():
            pytest.skip("local Ollama service is not reachable")
        info = client.model_info()
        if info is None:
            pytest.skip(f"model {settings.model!r} is not installed")

        store = ResearchStore(settings.db_path, settings.jsonl_path)
        orchestrator = ToolOrchestrator(settings.tool_timeout_s)
        agent = ResearchAgent(settings, client, orchestrator, store)
        try:
            outcome = agent.run(SEED, allow_repair=True)

            assert outcome.status == "completed"
            assert outcome.verification is not None
            assert outcome.verification.status is VerificationStatus.PASSED
            assert outcome.tool_result is not None
            assert outcome.tool_result.term_count >= 1
            assert outcome.interpretation is not None
            assert outcome.interpretation.conclusion.strip()
            assert outcome.context is not None
            assert store.verify_jsonl()["valid"] is True

            row = store.get_experiment(outcome.experiment_id)
            assert row is not None
            assert row["status"] == "completed"
            if info.get("digest"):
                assert row["model_digest"] == info["digest"]

            steps = store.list_steps(outcome.experiment_id)
            assert any(
                step["kind"] == "verification" and step["status"] == "passed"
                for step in steps
            )
            assert any(
                step["kind"] == "tool_execution" for step in steps
            )
            assert (outcome.token_usage or {}).get("eval_count", 0) > 0

            # Safe rejection is demonstrated in the same live process.
            with pytest.raises(ToolValidationError):
                orchestrator.execute(
                    {"tool": "shell", "arguments": {"command": "dir"}}
                )
        finally:
            store.close()
    finally:
        client.close()
