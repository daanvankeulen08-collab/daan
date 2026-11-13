"""Deterministic simple and log returns.

Convention: return arrays are aligned with the input observations.  The first
observation has no prior price and is represented by ``None`` rather than a
fabricated zero.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from qresearch.validation import ensure_positive_finite


def _validated_prices(prices: Sequence[Any]) -> tuple[float, ...]:
    values = tuple(
        ensure_positive_finite(price, field=f"prices[{index}]")
        for index, price in enumerate(prices)
    )
    return values


def simple_return(current: Any, previous: Any) -> float:
    """Return ``(current / previous) - 1`` for two positive finite prices."""

    current_price = ensure_positive_finite(current, field="current")
    previous_price = ensure_positive_finite(previous, field="previous")
    return current_price / previous_price - 1.0


def log_return(current: Any, previous: Any) -> float:
    """Return ``ln(current / previous)`` for two positive finite prices."""

    current_price = ensure_positive_finite(current, field="current")
    previous_price = ensure_positive_finite(previous, field="previous")
    return math.log(current_price / previous_price)


def simple_returns(prices: Sequence[Any]) -> tuple[float | None, ...]:
    """Return simple returns aligned to ``prices``.

    The first element is ``None``.  An empty input yields an empty tuple and a
    single price yields ``(None,)``.  Zero, negative, NaN and infinite prices are
    rejected.
    """

    values = _validated_prices(prices)
    if not values:
        return ()
    result: list[float | None] = [None]
    for previous, current in zip(values, values[1:]):
        result.append(current / previous - 1.0)
    return tuple(result)


def log_returns(prices: Sequence[Any]) -> tuple[float | None, ...]:
    """Return log returns aligned to ``prices``.

    The first element is ``None``.  An empty input yields an empty tuple and a
    single price yields ``(None,)``.  Zero, negative, NaN and infinite prices are
    rejected.
    """

    values = _validated_prices(prices)
    if not values:
        return ()
    result: list[float | None] = [None]
    for previous, current in zip(values, values[1:]):
        result.append(math.log(current / previous))
    return tuple(result)
