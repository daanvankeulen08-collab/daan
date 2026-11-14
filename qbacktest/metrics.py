"""Pure metric helpers used by the backtest engine.

The metric set is deliberately small and closed:

* ``total_return``
* ``exposure_fraction``
* ``commission_total``
* ``slippage_total``
* ``trade_count``

Risk-adjusted metrics (Sharpe, Sortino, any annualisation convention) are
**not** implemented: the annualisation convention is an open decision deferred
to Block 2C.
"""

from __future__ import annotations

from typing import Sequence

from qbacktest.errors import BacktestError
from qbacktest.models import TradeRecord


def total_return(equity_curve: Sequence[float], initial_equity: float = 1.0) -> float:
    """Return ``final_equity / initial_equity - 1`` as a decimal fraction."""

    values = tuple(equity_curve)
    if not values:
        raise BacktestError("total_return requires at least one equity value")
    if not initial_equity > 0.0:
        raise BacktestError("initial_equity must be positive")
    return values[-1] / initial_equity - 1.0


def exposure_fraction(exposed_bars: int, bar_count: int) -> float:
    """Return the fraction of bars that were marked with an open position."""

    if bar_count <= 0:
        raise BacktestError("bar_count must be positive")
    if exposed_bars < 0 or exposed_bars > bar_count:
        raise BacktestError("exposed_bars must be between 0 and bar_count")
    return exposed_bars / bar_count


def commission_total(trades: Sequence[TradeRecord]) -> float:
    """Return the commission charged across every trade (0.0 when there are none)."""

    return float(sum(trade.commission_paid for trade in trades))


def slippage_total(trades: Sequence[TradeRecord]) -> float:
    """Return the slippage cost paid across every trade (0.0 when there are none)."""

    return float(sum(trade.slippage_paid for trade in trades))


def trade_count(trades: Sequence[TradeRecord]) -> int:
    """Return the number of trades, including a trade that is still open."""

    return len(tuple(trades))


__all__ = [
    "commission_total",
    "exposure_fraction",
    "slippage_total",
    "total_return",
    "trade_count",
]
