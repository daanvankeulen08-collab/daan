"""Synthetic-data helpers shared by the qresearch test modules.

These helpers are test-only.  They never read the real ``data/`` directory.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from qresearch.models import MarketBar, MarketSeries

BASE = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
COLUMNS = (
    "timestamp",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


def make_bar(
    index: int = 0,
    *,
    close: float = 100.0,
    open_price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
    symbol: str = "TEST",
    timeframe: str = "1h",
    timestamp: Any = None,
) -> MarketBar:
    """Build a valid bar with deterministic defaults."""

    open_value = close if open_price is None else open_price
    resolved_high = max(open_value, close) * 1.01 if high is None else high
    resolved_low = min(open_value, close) * 0.99 if low is None else low
    resolved_timestamp = (
        BASE + timedelta(hours=index) if timestamp is None else timestamp
    )
    return MarketBar(
        timestamp=resolved_timestamp,
        symbol=symbol,
        timeframe=timeframe,
        open=open_value,
        high=resolved_high,
        low=resolved_low,
        close=close,
        volume=volume,
    )


def make_series(
    closes: Sequence[float],
    *,
    symbol: str = "TEST",
    timeframe: str = "1h",
) -> MarketSeries:
    """Build a chronological series from close prices."""

    return MarketSeries(
        tuple(
            make_bar(index, close=close, symbol=symbol, timeframe=timeframe)
            for index, close in enumerate(closes)
        )
    )


def make_row(
    index: int = 0,
    *,
    close: float = 100.0,
    open_price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
    symbol: str = "TEST",
    timeframe: str = "1h",
    timestamp: Any = None,
) -> dict[str, Any]:
    """Build a CSV row as a dict keyed by the required column names."""

    open_value = close if open_price is None else open_price
    resolved_high = max(open_value, close) * 1.01 if high is None else high
    resolved_low = min(open_value, close) * 0.99 if low is None else low
    resolved_timestamp = (
        (BASE + timedelta(hours=index)).isoformat()
        if timestamp is None
        else str(timestamp)
    )
    return {
        "timestamp": resolved_timestamp,
        "symbol": symbol,
        "timeframe": timeframe,
        "open": open_value,
        "high": resolved_high,
        "low": resolved_low,
        "close": close,
        "volume": volume,
    }


def csv_text(
    rows: Iterable[Mapping[str, Any]],
    *,
    header: Sequence[str] = COLUMNS,
    trailing_newline: bool = True,
) -> str:
    """Render rows as CSV text, looking columns up by name."""

    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(row[column]) for column in header))
    text = "\n".join(lines)
    return text + ("\n" if trailing_newline else "")


def write_text(
    root: Path,
    relative_path: str,
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Write text below ``root`` and return the resulting path."""

    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding, newline="")
    return path


def write_bytes(root: Path, relative_path: str, data: bytes) -> Path:
    """Write bytes below ``root`` and return the resulting path."""

    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
