"""Small, deterministic indicator calculations.

Only the requested indicators are implemented: simple moving average, rolling
standard deviation of log returns, and (in :mod:`qresearch.metrics`) maximum
drawdown.  Insufficient history is represented by ``None``; it is never filled
with zero or a back-filled value.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from qresearch.errors import CalculationError, MarketDataError
from qresearch.returns import log_returns
from qresearch.validation import (
    ensure_finite_number,
    ensure_nonnegative_int,
    ensure_positive_finite,
    ensure_positive_int,
)


def _validated_values(values: Sequence[Any]) -> tuple[float, ...]:
    return tuple(
        ensure_finite_number(value, field=f"values[{index}]")
        for index, value in enumerate(values)
    )


def _validated_window(value: Any) -> int:
    try:
        return ensure_positive_int(value, field="window")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc


def simple_moving_average(
    values: Sequence[Any],
    window: int,
) -> tuple[float | None, ...]:
    """Return a simple moving average aligned with ``values``.

    ``window`` must be a positive integer.  The first ``window - 1`` positions
    are ``None`` when history is insufficient.  If ``window`` exceeds the input
    length, every position is ``None``.  No partial-window average is produced.
    """

    size = _validated_window(window)
    numbers = _validated_values(values)
    result: list[float | None] = [None] * len(numbers)
    if size > len(numbers):
        return tuple(result)
    for end in range(size, len(numbers) + 1):
        segment = numbers[end - size : end]
        result[end - 1] = math.fsum(segment) / size
    return tuple(result)


def rolling_volatility_from_log_returns(
    values: Sequence[Any],
    window: int,
    *,
    ddof: int = 1,
    annualization_factor: float | None = None,
) -> tuple[float | None, ...]:
    """Rolling standard deviation of an existing log-return series.

    Standard deviation convention: sample standard deviation by default
    (``ddof=1``); pass ``ddof=0`` for population standard deviation.  A window
    containing ``None`` or fewer than ``window`` observations produces ``None``.

    The result is on the same scale as the input returns.  It is not annualized
    unless the caller explicitly supplies ``annualization_factor``; in that case
    the result is multiplied by ``sqrt(annualization_factor)``.
    """

    size = _validated_window(window)
    try:
        degrees = ensure_nonnegative_int(ddof, field="ddof")
    except MarketDataError as exc:
        raise CalculationError(str(exc)) from exc
    if degrees >= size:
        raise CalculationError(
            f"ddof ({degrees}) must be smaller than window ({size})"
        )

    normalized: list[float | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
        else:
            normalized.append(ensure_finite_number(value, field=f"values[{index}]"))

    factor: float | None = None
    if annualization_factor is not None:
        try:
            factor = ensure_positive_finite(
                annualization_factor, field="annualization_factor"
            )
        except MarketDataError as exc:
            raise CalculationError(str(exc)) from exc

    result: list[float | None] = [None] * len(normalized)
    if size > len(normalized):
        return tuple(result)

    for end in range(size, len(normalized) + 1):
        segment = normalized[end - size : end]
        if any(value is None for value in segment):
            continue
        numeric = [value for value in segment if value is not None]
        mean = math.fsum(numeric) / size
        variance = math.fsum((value - mean) ** 2 for value in numeric) / (
            size - degrees
        )
        standard_deviation = math.sqrt(max(0.0, variance))
        if factor is not None:
            standard_deviation *= math.sqrt(factor)
        result[end - 1] = standard_deviation
    return tuple(result)


def rolling_volatility(
    prices: Sequence[Any],
    window: int,
    *,
    ddof: int = 1,
    annualization_factor: float | None = None,
) -> tuple[float | None, ...]:
    """Rolling standard deviation of log returns derived from close prices.

    The first log return is undefined, so with ``window=n`` the first ``n``
    positions of the returned array are ``None``.  See
    :func:`rolling_volatility_from_log_returns` for the standard-deviation and
    annualization conventions.
    """

    returns = log_returns(prices)
    return rolling_volatility_from_log_returns(
        returns,
        window,
        ddof=ddof,
        annualization_factor=annualization_factor,
    )
