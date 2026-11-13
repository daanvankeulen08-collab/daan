"""Configuration for Block 1.

Only environment variables prefixed with ``MDL_`` are read.  No ``.env`` file is
read or written.  Every limit is explicit so the resource policy from the
specification is visible in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    # Local model
    ollama_base_url: str = "http://127.0.0.1:11434"
    model: str = "lfm3:latest"
    context_limit: int = 8192
    think: bool = False

    # Output budgets (deliberately small for an 8 GB / 4-core machine)
    hypothesis_max_tokens: int = 320
    plan_max_tokens: int = 420
    tool_request_max_tokens: int = 220
    interpretation_max_tokens: int = 700

    # Sampling
    temperature: float = 0.1
    top_p: float = 1.0
    repeat_penalty: float = 1.1
    seed: int = 42

    # Timeouts
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 300.0
    tool_timeout_s: float = 5.0
    keep_alive: str = "10m"

    # Storage
    db_path: Path = field(default_factory=lambda: DEFAULT_DATA_DIR / "mdl.sqlite3")
    jsonl_path: Path = field(
        default_factory=lambda: DEFAULT_DATA_DIR / "research_events.jsonl"
    )

    def ensure_data_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)


def load_settings(**overrides: object) -> Settings:
    """Build settings, allowing ``MDL_*`` environment overrides.

    Explicit keyword overrides win over environment variables.
    """

    values: dict[str, object] = {}

    if os.environ.get("MDL_OLLAMA_URL"):
        values["ollama_base_url"] = os.environ["MDL_OLLAMA_URL"]
    if os.environ.get("MDL_MODEL"):
        values["model"] = os.environ["MDL_MODEL"]
    if os.environ.get("MDL_DATA_DIR"):
        data_dir = Path(os.environ["MDL_DATA_DIR"])
        values["db_path"] = data_dir / "mdl.sqlite3"
        values["jsonl_path"] = data_dir / "research_events.jsonl"

    values.update(overrides)
    return Settings(**values)
