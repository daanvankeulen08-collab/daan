"""Typed market data and analysis-result models.

The market-data model is intentionally strict: it normalizes timestamps to UTC
but never sorts, deduplicates, fills or repairs observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from qresearch.errors import MarketDataError
from qresearch.validation import (
    ensure_nonnegative_finite,
    ensure_positive_finite,
    ensure_text,
    normalize_timestamp,
    validate_ohlcv,
)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class MarketBar:
    """One validated OHLCV observation.

    ``timestamp`` must be timezone-aware and is normalized to UTC.  Prices must
    be finite and positive, volume must be finite and non-negative, and the OHLC
    ordering rules are enforced immediately.
    """

    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        timestamp = normalize_timestamp(self.timestamp)
        symbol = ensure_text(self.symbol, field="symbol")
        timeframe = ensure_text(self.timeframe, field="timeframe")
        open_price = ensure_positive_finite(self.open, field="open")
        high = ensure_positive_finite(self.high, field="high")
        low = ensure_positive_finite(self.low, field="low")
        close = ensure_positive_finite(self.close, field="close")
        volume = ensure_nonnegative_finite(self.volume, field="volume")
        if volume == 0.0:
            # Normalize negative zero so equivalent series hash identically.
            volume = 0.0
        validate_ohlcv(
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "close", close)
        object.__setattr__(self, "volume", volume)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": _iso_utc(self.timestamp),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class MarketSeries:
    """A non-empty, single-symbol, single-timeframe, chronological bar series."""

    bars: tuple[MarketBar, ...]

    def __post_init__(self) -> None:
        try:
            bars = tuple(self.bars)
        except TypeError as exc:
            raise MarketDataError("bars must be an iterable of MarketBar objects") from exc
        if not bars:
            raise MarketDataError("market series must contain at least one bar")

        first = bars[0]
        if not isinstance(first, MarketBar):
            raise MarketDataError(
                "bars[0] must be a MarketBar; got "
                f"{type(first).__name__}"
            )
        symbol = first.symbol
        timeframe = first.timeframe
        previous_timestamp: datetime | None = None

        for index, bar in enumerate(bars):
            if not isinstance(bar, MarketBar):
                raise MarketDataError(
                    f"bars[{index}] must be a MarketBar; got {type(bar).__name__}"
                )
            if bar.symbol != symbol:
                raise MarketDataError(
                    f"mixed symbols in one series: bars[0]={symbol!r}, "
                    f"bars[{index}]={bar.symbol!r}"
                )
            if bar.timeframe != timeframe:
                raise MarketDataError(
                    f"mixed timeframes in one series: bars[0]={timeframe!r}, "
                    f"bars[{index}]={bar.timeframe!r}"
                )
            if previous_timestamp is not None:
                if bar.timestamp == previous_timestamp:
                    raise MarketDataError(
                        f"duplicate timestamp at bars[{index}]: {_iso_utc(bar.timestamp)}"
                    )
                if bar.timestamp < previous_timestamp:
                    raise MarketDataError(
                        "timestamps must be strictly chronological; "
                        f"bars[{index}]={_iso_utc(bar.timestamp)} is earlier than "
                        f"bars[{index - 1}]={_iso_utc(previous_timestamp)}"
                    )
            previous_timestamp = bar.timestamp

        object.__setattr__(self, "bars", bars)

    @property
    def symbol(self) -> str:
        return self.bars[0].symbol

    @property
    def timeframe(self) -> str:
        return self.bars[0].timeframe

    @property
    def first_timestamp(self) -> datetime:
        return self.bars[0].timestamp

    @property
    def last_timestamp(self) -> datetime:
        return self.bars[-1].timestamp

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        return tuple(bar.timestamp for bar in self.bars)

    @property
    def closes(self) -> tuple[float, ...]:
        return tuple(bar.close for bar in self.bars)

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self):
        return iter(self.bars)


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Validation facts attached to an analysis result."""

    row_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    strictly_chronological: bool = True
    unique_timestamps: bool = True
    ohlcv_rules_passed: bool = True
    timezone: str = "UTC"
    source_path: str | None = None
    file_size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "first_timestamp": _iso_utc(self.first_timestamp),
            "last_timestamp": _iso_utc(self.last_timestamp),
            "strictly_chronological": self.strictly_chronological,
            "unique_timestamps": self.unique_timestamps,
            "ohlcv_rules_passed": self.ohlcv_rules_passed,
            "timezone": self.timezone,
            "source_path": self.source_path,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class MovingAverageResult:
    window: int
    values: tuple[float | None, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"window": self.window, "values": list(self.values)}


@dataclass(frozen=True, slots=True)
class RollingVolatilityResult:
    window: int
    ddof: int
    annualization_factor: float | None
    values: tuple[float | None, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "ddof": self.ddof,
            "annualization_factor": self.annualization_factor,
            "values": list(self.values),
        }


@dataclass(frozen=True, slots=True)
class DrawdownObservation:
    """Maximum drawdown plus the timestamps of the relevant peak and trough."""

    max_drawdown: float
    peak_index: int
    trough_index: int
    peak_timestamp: datetime
    trough_timestamp: datetime
    peak_price: float
    trough_price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_drawdown": self.max_drawdown,
            "peak_index": self.peak_index,
            "trough_index": self.trough_index,
            "peak_timestamp": _iso_utc(self.peak_timestamp),
            "trough_timestamp": _iso_utc(self.trough_timestamp),
            "peak_price": self.peak_price,
            "trough_price": self.trough_price,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Deterministic analysis output suitable for later structured consumption."""

    symbol: str
    timeframe: str
    observation_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    content_sha256: str
    content_hash_source: str
    simple_returns: tuple[float | None, ...]
    log_returns: tuple[float | None, ...]
    moving_averages: tuple[MovingAverageResult, ...]
    rolling_volatilities: tuple[RollingVolatilityResult, ...]
    max_drawdown: DrawdownObservation
    validation: ValidationSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "observation_count": self.observation_count,
            "first_timestamp": _iso_utc(self.first_timestamp),
            "last_timestamp": _iso_utc(self.last_timestamp),
            "content_sha256": self.content_sha256,
            "content_hash_source": self.content_hash_source,
            "simple_returns": list(self.simple_returns),
            "log_returns": list(self.log_returns),
            "moving_averages": [item.to_dict() for item in self.moving_averages],
            "rolling_volatilities": [
                item.to_dict() for item in self.rolling_volatilities
            ],
            "max_drawdown": self.max_drawdown.to_dict(),
            "validation": self.validation.to_dict(),
        }
