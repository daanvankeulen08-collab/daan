"""Structured SQLite storage plus an append-only hash-chained JSONL log.

SQLite keeps the relational/tabular experiment record.  JSONL is the
authoritative append-only event journal; each line contains the hash of the
previous line, so silent edits are detectable via ``verify_jsonl``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .errors import LogIntegrityError

GENESIS_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    seed TEXT,
    model TEXT NOT NULL,
    model_digest TEXT,
    parameters_json TEXT NOT NULL,
    context_limit INTEGER NOT NULL,
    hypothesis_json TEXT,
    plan_json TEXT,
    tool_request_json TEXT,
    tool_result_json TEXT,
    verification_json TEXT,
    interpretation_json TEXT,
    context_json TEXT,
    latency_ms REAL,
    token_usage_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL REFERENCES experiments(id),
    seq INTEGER NOT NULL,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms REAL,
    payload_json TEXT NOT NULL,
    UNIQUE(experiment_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_steps_experiment
    ON steps(experiment_id, seq);
"""

_JSON_COLUMNS = {
    "parameters_json",
    "hypothesis_json",
    "plan_json",
    "tool_request_json",
    "tool_result_json",
    "verification_json",
    "interpretation_json",
    "context_json",
    "token_usage_json",
}

_UPDATEABLE = {
    "updated_at",
    "status",
    "seed",
    "model",
    "model_digest",
    "parameters_json",
    "context_limit",
    "hypothesis_json",
    "plan_json",
    "tool_request_json",
    "tool_result_json",
    "verification_json",
    "interpretation_json",
    "context_json",
    "latency_ms",
    "token_usage_json",
    "error",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _new_experiment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"exp_{stamp}_{uuid.uuid4().hex[:8]}"


class ResearchStore:
    def __init__(self, db_path: str | Path, jsonl_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)

        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._prev_hash = self._read_last_hash()

    # -- low-level helpers ------------------------------------------------
    def _read_last_hash(self) -> str:
        if not self.jsonl_path.exists():
            return GENESIS_HASH
        last = GENESIS_HASH
        with self.jsonl_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LogIntegrityError(
                        f"invalid JSONL at line {line_number}: {exc}"
                    ) from exc
                last = event.get("hash", last)
        return last

    def _next_event_seq(self, experiment_id: str) -> int:
        highest = 0
        if not self.jsonl_path.exists():
            return 1
        with self.jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LogIntegrityError(
                        f"invalid JSONL while appending: {exc}"
                    ) from exc
                if event.get("experiment_id") == experiment_id:
                    highest = max(highest, int(event.get("seq", 0)))
        return highest + 1

    def _next_step_seq(self, experiment_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM steps WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        return int(row["seq"]) + 1

    def _append_event(self, experiment_id: str, event_type: str, payload: dict) -> dict:
        event = {
            "event_id": f"evt_{uuid.uuid4().hex}",
            "experiment_id": experiment_id,
            "seq": self._next_event_seq(experiment_id),
            "ts": _utc_now(),
            "type": event_type,
            "payload": payload,
            "prev_hash": self._prev_hash,
        }
        digest = hashlib.sha256(
            (self._prev_hash + _canonical(event)).encode("utf-8")
        ).hexdigest()
        event["hash"] = digest
        line = _canonical(event)
        with self.jsonl_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._prev_hash = digest
        return event

    # -- public API -------------------------------------------------------
    def create_experiment(
        self,
        *,
        seed: str | None,
        model: str,
        model_digest: str | None,
        parameters: dict,
        context_limit: int,
    ) -> str:
        experiment_id = _new_experiment_id()
        now = _utc_now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO experiments (
                    id, created_at, updated_at, status, seed, model,
                    model_digest, parameters_json, context_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    now,
                    now,
                    "running",
                    seed,
                    model,
                    model_digest,
                    _canonical(parameters),
                    int(context_limit),
                ),
            )
            self._conn.commit()
            self._append_event(
                experiment_id,
                "experiment_started",
                {
                    "model": model,
                    "model_digest": model_digest,
                    "context_limit": int(context_limit),
                    "parameters": parameters,
                    "seed": seed,
                },
            )
        return experiment_id

    def log_event(self, experiment_id: str, event_type: str, payload: dict) -> dict:
        with self._lock:
            return self._append_event(experiment_id, event_type, payload)

    def log_step(
        self,
        experiment_id: str,
        kind: str,
        status: str,
        payload: dict,
        latency_ms: float | None = None,
    ) -> int:
        now = _utc_now()
        with self._lock:
            seq = self._next_step_seq(experiment_id)
            self._conn.execute(
                """
                INSERT INTO steps (
                    experiment_id, seq, ts, kind, status, latency_ms, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    seq,
                    now,
                    kind,
                    status,
                    latency_ms,
                    _canonical(payload),
                ),
            )
            self._conn.commit()
            self._append_event(
                experiment_id,
                f"step.{kind}",
                {
                    "step_seq": seq,
                    "status": status,
                    "latency_ms": latency_ms,
                    "data": payload,
                },
            )
        return seq

    def set_experiment_fields(self, experiment_id: str, **fields: object) -> None:
        if not fields:
            return
        columns: list[str] = []
        values: list[object] = []
        for key, value in fields.items():
            if key not in _UPDATEABLE:
                raise ValueError(f"column {key!r} cannot be updated")
            if key in _JSON_COLUMNS and not isinstance(value, str):
                value = _canonical(value)
            columns.append(f"{key} = ?")
            values.append(value)
        if "updated_at" not in fields:
            columns.append("updated_at = ?")
            values.append(_utc_now())
        values.append(experiment_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE experiments SET {', '.join(columns)} WHERE id = ?",
                values,
            )
            self._conn.commit()

    def finish_experiment(
        self,
        experiment_id: str,
        status: str,
        *,
        error: str | None = None,
        latency_ms: float | None = None,
        token_usage: dict | None = None,
        **extra: object,
    ) -> None:
        fields: dict[str, object] = {"status": status}
        if error is not None:
            fields["error"] = error
        if latency_ms is not None:
            fields["latency_ms"] = latency_ms
        if token_usage is not None:
            fields["token_usage_json"] = token_usage
        fields.update(extra)
        self.set_experiment_fields(experiment_id, **fields)
        self.log_event(
            experiment_id,
            "experiment_finished",
            {
                "status": status,
                "error": error,
                "latency_ms": latency_ms,
                "token_usage": token_usage,
            },
        )

    def get_experiment(self, experiment_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_steps(self, experiment_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM steps WHERE experiment_id = ? ORDER BY seq",
            (experiment_id,),
        ).fetchall()
        steps = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            steps.append(item)
        return steps

    def read_events(self, experiment_id: str | None = None) -> list[dict]:
        events: list[dict] = []
        if not self.jsonl_path.exists():
            return events
        with self.jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if experiment_id is None or event.get("experiment_id") == experiment_id:
                    events.append(event)
        return events

    def verify_jsonl(self) -> dict:
        """Recompute the hash chain and report the first inconsistency."""

        previous = GENESIS_HASH
        count = 0
        if not self.jsonl_path.exists():
            return {"valid": True, "events": 0, "error": None, "line": None}

        with self.jsonl_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    return {
                        "valid": False,
                        "events": count,
                        "error": f"invalid JSON: {exc}",
                        "line": line_number,
                    }
                claimed = event.pop("hash", None)
                if event.get("prev_hash") != previous:
                    return {
                        "valid": False,
                        "events": count,
                        "error": "prev_hash does not match the chain",
                        "line": line_number,
                    }
                expected = hashlib.sha256(
                    (previous + _canonical(event)).encode("utf-8")
                ).hexdigest()
                if claimed != expected:
                    return {
                        "valid": False,
                        "events": count,
                        "error": "hash mismatch (line was modified)",
                        "line": line_number,
                    }
                previous = claimed

        return {"valid": True, "events": count, "error": None, "line": None}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
