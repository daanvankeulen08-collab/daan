"""Local Ollama client for LFM3.

Guarantees:
* one generation at a time (process-wide lock);
* explicit context window (8192) and output budgets;
* ``think`` disabled by default;
* hard HTTP timeouts;
* constrained JSON output via ``format`` (with safe fallbacks).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from time import perf_counter

import httpx

from .config import Settings
from .errors import ModelError, ModelOutputError, ModelTimeoutError


@dataclass(frozen=True)
class ModelResponse:
    content: str
    parsed: dict
    prompt_eval_count: int | None
    eval_count: int | None
    total_duration_ns: int | None
    load_duration_ns: int | None
    eval_duration_ns: int | None
    wall_ms: float
    raw: dict
    done_reason: str | None = None
    # Provenance of the payload variant that produced the accepted response.
    # Defaults keep every pre-existing construction working unchanged.
    protocol_variant: str = "primary"
    schema_enforced: bool = False
    think_sent: bool | None = None


def _extract_json(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ModelOutputError("model returned an empty response")

    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    if start < 0:
        raise ModelOutputError("model response does not contain a JSON object")
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"model response is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ModelOutputError("model response JSON is not an object")
    return parsed


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=settings.ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(
                settings.read_timeout_s,
                connect=settings.connect_timeout_s,
                write=30.0,
                pool=10.0,
            ),
            headers={"Content-Type": "application/json"},
        )

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- discovery -------------------------------------------------------
    def health(self) -> bool:
        try:
            response = self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def model_info(self) -> dict | None:
        try:
            response = self._client.get("/api/tags")
        except httpx.HTTPError as exc:
            raise ModelError(f"cannot reach Ollama: {exc}") from exc
        if response.status_code != 200:
            raise ModelError(f"Ollama /api/tags returned {response.status_code}")
        data = response.json()
        wanted = self.settings.model
        for item in data.get("models", []):
            name = item.get("name") or item.get("model") or ""
            if name == wanted or name.split(":", 1)[0] == wanted.split(":", 1)[0]:
                return item
        return None

    # -- generation ------------------------------------------------------
    def chat_json(
        self,
        messages: list[dict],
        schema: dict | None,
        *,
        num_predict: int,
    ) -> ModelResponse:
        payload: dict = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
            "format": schema if schema is not None else "json",
            "think": self.settings.think,
            "options": {
                "num_ctx": self.settings.context_limit,
                "num_predict": int(num_predict),
                "temperature": self.settings.temperature,
                "top_p": self.settings.top_p,
                "repeat_penalty": self.settings.repeat_penalty,
                "seed": self.settings.seed,
            },
            "keep_alive": self.settings.keep_alive,
        }

        variants: list[tuple[str, dict]] = [("primary", payload)]
        if isinstance(payload.get("format"), dict):
            fallback = dict(payload)
            fallback["format"] = "json"
            variants.append(("json_fallback", fallback))
        without_think = dict(variants[-1][1])
        without_think.pop("think", None)
        variants.append(("json_without_think", without_think))

        started = perf_counter()
        # Single-flight: no two LFM3 generations may overlap in this process.
        with self._lock:
            response = None
            last_error = "unknown error"
            accepted_variant = "primary"
            accepted_payload = payload
            for variant_name, variant in variants:
                response = self._post("/api/chat", variant)
                if response.status_code < 400:
                    accepted_variant = variant_name
                    accepted_payload = variant
                    break
                last_error = f"HTTP {response.status_code}: {response.text[:400]}"
            wall_ms = (perf_counter() - started) * 1000.0

        if response is None or response.status_code >= 400:
            raise ModelError(f"Ollama chat failed: {last_error}")

        schema_enforced = isinstance(accepted_payload.get("format"), dict)
        think_sent = accepted_payload.get("think")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ModelOutputError(
                f"Ollama returned non-JSON: {exc}",
                protocol_variant=accepted_variant,
                schema_enforced=schema_enforced,
                think_sent=think_sent,
            ) from exc

        message = data.get("message") or {}
        content = message.get("content", "")
        prompt_eval_count = _optional_int(data.get("prompt_eval_count"))
        eval_count = _optional_int(data.get("eval_count"))
        done_reason = data.get("done_reason")
        try:
            parsed = _extract_json(content)
        except ModelOutputError as exc:
            # Preserve the failed output and generation metadata so callers can
            # log them; today they would be discarded before ModelResponse exists.
            raise ModelOutputError(
                str(exc),
                raw_content=content,
                done_reason=done_reason,
                prompt_eval_count=prompt_eval_count,
                eval_count=eval_count,
                protocol_variant=accepted_variant,
                schema_enforced=schema_enforced,
                think_sent=think_sent,
            ) from exc

        return ModelResponse(
            content=content,
            parsed=parsed,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
            total_duration_ns=_optional_int(data.get("total_duration")),
            load_duration_ns=_optional_int(data.get("load_duration")),
            eval_duration_ns=_optional_int(data.get("eval_duration")),
            wall_ms=wall_ms,
            raw=data,
            done_reason=done_reason,
            protocol_variant=accepted_variant,
            schema_enforced=schema_enforced,
            think_sent=think_sent,
        )

    def _post(self, path: str, payload: dict) -> httpx.Response:
        try:
            return self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError(
                f"Ollama did not answer within {self.settings.read_timeout_s:.0f}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(f"Ollama request failed: {exc}") from exc


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
