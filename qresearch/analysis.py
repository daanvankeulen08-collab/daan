"""Deterministic end-to-end analysis of validated market series.

Two entry points are provided:

* :func:`analyze_series` analyses an in-memory :class:`MarketSeries`.
* :func:`analyze_csv` loads a CSV through the strict, sandboxed loader and
  analyses the resulting series.

Both return the same serializable :class:`AnalysisResult`.  Nothing in this
module predicts prices, emits signals or calls a language model.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from qresearch.csv_loader import (
    CSVLoadResult,
    load_market_csv,
)
from qresearch.errors import CalculationError, MarketDataError
from qresearch.indicators import rolling_volatility, simple_moving_average
from qresearch.metrics import maximum_drawdown
from qresearch.models import (
    AnalysisResult,
    DrawdownObservation,
    MarketSeries,
    MovingAverageResult,
    RollingVolatilityResult,
    ValidationSummary,
)
from qresearch.returns import log_returns, simple_returns
from qresearch.validation import (
    ensure_finite_number,
    ensure_nonnegative_int,
    ensure_positive_int,
    ensure_text,
)

CANONICAL_FORMAT = "qresearch.market-series.v1"
CANONICAL_HASH_SOURCE = "canonical-series-sha256"
CSV_HASH_SOURCE = "csv-file-sha256"
_HEX_DIGEST = re.compile(r"[0-9a-fA-F]{64}\Z")


def _normalize_content_hash(value: Any) -> str:
    if not isinstance(value, str):
        raise CalculationError(
            "content_sha256 must be a hexadecimal string; "
            f"got {type(value).__name__}"
        )
    if _HEX_DIGEST.fullmatch(value) is None:
        raise CalculationError(
            "content_sha256 must contain exactly 64 hexadecimal characters"
        )
    return value.lower()


def _validate_hash_source(value: Any) -> str:
    try:
        return ensure_text(value, field="content_hash_source")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc


def _validate_source_path(value: Any) -> str:
    try:
        return ensure_text(value, field="source_path")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc


def _validate_windows(value: Iterable[Any], *, name: str) -> tuple[int, ...]:
    try:
        raw_windows = tuple(value)
    except TypeError as exc:
        raise CalculationError(f"{name} must be an iterable of integers") from exc

    windows: list[int] = []
    seen: set[int] = set()
    for index, window in enumerate(raw_windows):
        try:
            size = ensure_positive_int(window, field=f"{name}[{index}]")
        except MarketDataError as exc:
            raise CalculationError(str(exc)) from exc
        if size in seen:
            raise CalculationError(
                f"{name} contains a duplicate window: {size}"
            )
        seen.add(size)
        windows.append(size)
    return tuple(windows)


def _validate_ddof(value: Any) -> int:
    try:
        return ensure_nonnegative_int(value, field="volatility_ddof")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc


def _validate_annualization_factor(value: Any) -> float | None:
    if value is None:
        return None
    try:
        factor = ensure_finite_number(value, field="annualization_factor")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc
    if factor <= 0.0:
        raise CalculationError(
            f"annualization_factor must be positive; got {value!r}"
        )
    return factor


def _validate_file_size(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return ensure_nonnegative_int(value, field="file_size_bytes")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc


def canonical_series_payload(series: MarketSeries) -> dict[str, Any]:
    """Return the format-versioned payload used for canonical hashing."""

    if not isinstance(series, MarketSeries):
        raise CalculationError(
            "series must be a MarketSeries; "
            f"got {type(series).__name__}"
        )
    return {
        "format": CANONICAL_FORMAT,
        "symbol": series.symbol,
        "timeframe": series.timeframe,
        "bars": [bar.to_dict() for bar in series.bars],
    }


def canonical_series_bytes(series: MarketSeries) -> bytes:
    """Serialize a series to deterministic UTF-8 bytes.

    The representation is compact, key-sorted JSON with no locale-dependent
    formatting.  Timestamps are UTC ISO-8601 strings and floats use Python's
    shortest round-trip representation.
    """

    payload = canonical_series_payload(series)
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CalculationError(
            f"market series cannot be serialized canonically: {exc}"
        ) from exc
    return text.encode("utf-8")


def canonical_series_sha256(series: MarketSeries) -> str:
    """Return the SHA-256 hex digest of a series' canonical bytes."""

    return hashlib.sha256(canonical_series_bytes(series)).hexdigest()


def _validation_summary(
    series: MarketSeries,
    *,
    source_path: str | None,
    file_size_bytes: int | None,
) -> ValidationSummary:
    return ValidationSummary(
        row_count=len(series),
        first_timestamp=series.first_timestamp,
        last_timestamp=series.last_timestamp,
        strictly_chronological=True,
        unique_timestamps=True,
        ohlcv_rules_passed=True,
        timezone="UTC",
        source_path=source_path,
        file_size_bytes=file_size_bytes,
    )


def _analyze_validated_series(
    series: MarketSeries,
    *,
    moving_average_windows: Iterable[Any],
    volatility_windows: Iterable[Any],
    volatility_ddof: Any,
    annualization_factor: Any,
    content_sha256: str | None,
    content_hash_source: str | None,
    source_path: str | None,
    file_size_bytes: int | None,
) -> AnalysisResult:
    ma_windows = _validate_windows(
        moving_average_windows, name="moving_average_windows"
    )
    vol_windows = _validate_windows(
        volatility_windows, name="volatility_windows"
    )
    ddof = _validate_ddof(volatility_ddof)
    factor = _validate_annualization_factor(annualization_factor)
    size_bytes = _validate_file_size(file_size_bytes)
    validated_source = (
        None if source_path is None else _validate_source_path(source_path)
    )

    if content_sha256 is None:
        if content_hash_source is not None:
            raise CalculationError(
                "content_hash_source requires an explicit content_sha256"
            )
        digest = canonical_series_sha256(series)
        hash_source = CANONICAL_HASH_SOURCE
    else:
        digest = _normalize_content_hash(content_sha256)
        if content_hash_source is None:
            raise CalculationError(
                "content_hash_source is required when content_sha256 is supplied"
            )
        hash_source = _validate_hash_source(content_hash_source)

    closes = series.closes
    drawdown = maximum_drawdown(closes)
    drawdown_observation = DrawdownObservation(
        max_drawdown=drawdown.max_drawdown,
        peak_index=drawdown.peak_index,
        trough_index=drawdown.trough_index,
        peak_timestamp=series.bars[drawdown.peak_index].timestamp,
        trough_timestamp=series.bars[drawdown.trough_index].timestamp,
        peak_price=drawdown.peak_value,
        trough_price=drawdown.trough_value,
    )

    moving_averages = tuple(
        MovingAverageResult(
            window=window,
            values=simple_moving_average(closes, window),
        )
        for window in ma_windows
    )
    volatilities = tuple(
        RollingVolatilityResult(
            window=window,
            ddof=ddof,
            annualization_factor=factor,
            values=rolling_volatility(
                closes,
                window,
                ddof=ddof,
                annualization_factor=factor,
            ),
        )
        for window in vol_windows
    )

    return AnalysisResult(
        symbol=series.symbol,
        timeframe=series.timeframe,
        observation_count=len(series),
        first_timestamp=series.first_timestamp,
        last_timestamp=series.last_timestamp,
        content_sha256=digest,
        content_hash_source=hash_source,
        simple_returns=simple_returns(closes),
        log_returns=log_returns(closes),
        moving_averages=moving_averages,
        rolling_volatilities=volatilities,
        max_drawdown=drawdown_observation,
        validation=_validation_summary(
            series,
            source_path=validated_source,
            file_size_bytes=size_bytes,
        ),
    )


def analyze_series(
    series: MarketSeries,
    *,
    moving_average_windows: Iterable[int] = (),
    volatility_windows: Iterable[int] = (),
    volatility_ddof: int = 1,
    annualization_factor: float | None = None,
    content_sha256: str | None = None,
    content_hash_source: str | None = None,
    source_path: str | None = None,
    file_size_bytes: int | None = None,
) -> AnalysisResult:
    """Analyse a validated in-memory series.

    The default content hash is SHA-256 over the canonical series bytes.  A
    caller may supply an already-computed digest (for example a raw CSV file
    digest); doing so requires an explicit ``content_hash_source`` label.

    Rolling volatility uses sample standard deviation by default (``ddof=1``)
    and is not annualized unless ``annualization_factor`` is supplied.
    """

    if not isinstance(series, MarketSeries):
        raise CalculationError(
            "series must be a MarketSeries; "
            f"got {type(series).__name__}"
        )
    return _analyze_validated_series(
        series,
        moving_average_windows=moving_average_windows,
        volatility_windows=volatility_windows,
        volatility_ddof=volatility_ddof,
        annualization_factor=annualization_factor,
        content_sha256=content_sha256,
        content_hash_source=content_hash_source,
        source_path=source_path,
        file_size_bytes=file_size_bytes,
    )


def analyze_csv(
    relative_path: str | Path,
    *,
    moving_average_windows: Iterable[int] = (),
    volatility_windows: Iterable[int] = (),
    volatility_ddof: int = 1,
    annualization_factor: float | None = None,
) -> AnalysisResult:
    """Load and analyse a CSV from ``data/market_samples/``.

    The content hash is the SHA-256 of the raw file bytes, so the analysis can
    be tied back to the exact input file.  The canonical series hash remains
    available through :func:`canonical_series_sha256`.
    """

    loaded: CSVLoadResult = load_market_csv(relative_path)
    return _analyze_validated_series(
        loaded.series,
        moving_average_windows=moving_average_windows,
        volatility_windows=volatility_windows,
        volatility_ddof=volatility_ddof,
        annualization_factor=annualization_factor,
        content_sha256=loaded.content_sha256,
        content_hash_source=CSV_HASH_SOURCE,
        source_path=loaded.source_path,
        file_size_bytes=loaded.file_size_bytes,
    )


__all__ = [
    "CANONICAL_FORMAT",
    "CANONICAL_HASH_SOURCE",
    "CSV_HASH_SOURCE",
    "analyze_csv",
    "analyze_series",
    "canonical_series_bytes",
    "canonical_series_payload",
    "canonical_series_sha256",
]
