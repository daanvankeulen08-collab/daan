"""Strict parsing and validation helpers shared by qresearch modules.

The helpers deliberately fail loudly.  They never clamp, sort, fill or otherwise
repair a value that violates the data contract.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from numbers import Integral, Real
from typing import Any

from qresearch.errors import MarketDataError


def normalize_timestamp(value: datetime | str, *, field: str = "timestamp") -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC.

    Naive timestamps are rejected because an ambiguous local time cannot be
    placed on the required timezone-aware timeline.
    """

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise MarketDataError(f"{field} must not be empty")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise MarketDataError(
                f"{field} is not a valid ISO-8601 timestamp: {value!r}"
            ) from exc
    else:
        raise MarketDataError(
            f"{field} must be a datetime or ISO-8601 string; got {type(value).__name__}"
        )

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MarketDataError(
            f"{field} must be timezone-aware; naive timestamp {value!r} is not allowed"
        )
    return parsed.astimezone(timezone.utc)


def ensure_text(value: Any, *, field: str) -> str:
    """Require a non-empty string without leading or trailing whitespace."""

    if not isinstance(value, str):
        raise MarketDataError(f"{field} must be a string; got {type(value).__name__}")
    if not value or not value.strip():
        raise MarketDataError(f"{field} must not be empty")
    if value != value.strip():
        raise MarketDataError(
            f"{field} must not contain leading or trailing whitespace: {value!r}"
        )
    return value


def ensure_finite_number(value: Any, *, field: str) -> float:
    """Convert a real number or numeric string to a finite float."""

    if isinstance(value, bool):
        raise MarketDataError(f"{field} must be a finite number; bool is not allowed")
    if isinstance(value, Real):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise MarketDataError(f"{field} must not be empty")
        try:
            number = float(text)
        except ValueError as exc:
            raise MarketDataError(
                f"{field} must be a finite number; got {value!r}"
            ) from exc
    else:
        raise MarketDataError(
            f"{field} must be a finite number; got {type(value).__name__}"
        )
    if not math.isfinite(number):
        raise MarketDataError(f"{field} must be finite; got {value!r}")
    return number


def ensure_positive_finite(value: Any, *, field: str) -> float:
    """Require a finite number strictly greater than zero."""

    number = ensure_finite_number(value, field=field)
    if number <= 0.0:
        raise MarketDataError(f"{field} must be positive; got {value!r}")
    return number


def ensure_nonnegative_finite(value: Any, *, field: str) -> float:
    """Require a finite number greater than or equal to zero."""

    number = ensure_finite_number(value, field=field)
    if number < 0.0:
        raise MarketDataError(f"{field} must be non-negative; got {value!r}")
    return number


def ensure_positive_int(value: Any, *, field: str) -> int:
    """Require a positive integer (booleans are rejected)."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise MarketDataError(
            f"{field} must be a positive integer; got {type(value).__name__}"
        )
    number = int(value)
    if number <= 0:
        raise MarketDataError(f"{field} must be a positive integer; got {value!r}")
    return number


def ensure_nonnegative_int(value: Any, *, field: str) -> int:
    """Require a non-negative integer (booleans are rejected)."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise MarketDataError(
            f"{field} must be a non-negative integer; got {type(value).__name__}"
        )
    number = int(value)
    if number < 0:
        raise MarketDataError(f"{field} must be a non-negative integer; got {value!r}")
    return number


def validate_ohlcv(
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> None:
    """Validate the OHLC ordering and volume constraints for one bar."""

    if high < low:
        raise MarketDataError(
            f"high must be greater than or equal to low; got high={high}, low={low}"
        )
    if high < open_price:
        raise MarketDataError(
            f"high must be greater than or equal to open; got high={high}, "
            f"open={open_price}"
        )
    if high < close:
        raise MarketDataError(
            f"high must be greater than or equal to close; got high={high}, "
            f"close={close}"
        )
    if low > open_price:
        raise MarketDataError(
            f"low must be less than or equal to open; got low={low}, "
            f"open={open_price}"
        )
    if low > close:
        raise MarketDataError(
            f"low must be less than or equal to close; got low={low}, "
            f"close={close}"
        )
    if volume < 0.0:
        raise MarketDataError(f"volume must be non-negative; got {volume!r}")
