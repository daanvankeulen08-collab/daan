"""Deterministic performance metric calculations.

Only maximum drawdown is implemented.  It is a descriptive statistic, not a
trading signal or recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from qresearch.errors import CalculationError
from qresearch.validation import ensure_positive_finite


@dataclass(frozen=True, slots=True)
class DrawdownResult:
    """Peak-to-trough close-price decline.

    ``max_drawdown`` is a non-negative decimal proportion, not a percentage.
    ``peak_index`` and ``trough_index`` identify the observations that produce
    the largest decline.
    """

    max_drawdown: float
    peak_index: int
    trough_index: int
    peak_value: float
    trough_value: float


def maximum_drawdown(prices: Sequence[Any]) -> DrawdownResult:
    """Return the maximum peak-to-trough close-price drawdown.

    Edge cases:
    * An empty series is invalid.
    * A single observation, or a series with no decline, has drawdown ``0.0``;
      indices 0/0 are returned as the neutral peak/trough pair.
    * Equal highs keep the earliest peak; equal drawdowns keep the first trough.
    * Prices must be finite and strictly positive.
    """

    try:
        raw_values = tuple(prices)
    except TypeError as exc:
        raise CalculationError("prices must be an iterable of numbers") from exc
    if not raw_values:
        raise CalculationError("maximum drawdown requires at least one price")

    values = tuple(
        ensure_positive_finite(value, field=f"prices[{index}]")
        for index, value in enumerate(raw_values)
    )

    peak_value = values[0]
    peak_index = 0
    best_drawdown = 0.0
    best_peak_index = 0
    best_trough_index = 0

    for index in range(1, len(values)):
        value = values[index]
        if value > peak_value:
            peak_value = value
            peak_index = index
        drawdown = (peak_value - value) / peak_value
        if drawdown > best_drawdown:
            best_drawdown = drawdown
            best_peak_index = peak_index
            best_trough_index = index

    return DrawdownResult(
        max_drawdown=best_drawdown,
        peak_index=best_peak_index,
        trough_index=best_trough_index,
        peak_value=values[best_peak_index],
        trough_value=values[best_trough_index],
    )


# Convenient alias for callers that use the shorter metric name.
max_drawdown = maximum_drawdown
