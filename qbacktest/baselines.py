"""The two baseline signals allowed in Block 2B.

``buy_and_hold_signal`` and ``cash_signal`` are the only strategies in this
package.  They are trivial, fully deterministic and exist so the engine can be
tested against hand-computed expectations.  No indicator, crossover, parameter
search or optimisation logic lives here or anywhere else in ``qbacktest``.
"""

from __future__ import annotations

from qresearch.models import MarketSeries

from qbacktest.errors import InvalidSeriesError


def _require_series(series: object) -> MarketSeries:
    if not isinstance(series, MarketSeries):
        raise InvalidSeriesError(
            f"series must be a MarketSeries; got {type(series).__name__}"
        )
    return series


def buy_and_hold_signal(series: MarketSeries) -> tuple[int, ...]:
    """Return a signal that is long from the very first bar onwards.

    The first bar's signal can only be executed at the second bar's open, so
    the run starts flat for exactly one bar.
    """

    validated = _require_series(series)
    return tuple(1 for _ in validated.bars)


def cash_signal(series: MarketSeries) -> tuple[int, ...]:
    """Return a signal that stays flat for every bar."""

    validated = _require_series(series)
    return tuple(0 for _ in validated.bars)


__all__ = [
    "buy_and_hold_signal",
    "cash_signal",
]
