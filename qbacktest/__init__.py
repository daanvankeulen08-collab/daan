"""Deterministic, cost-aware backtest engine (Block 2B).

``qbacktest`` replays a discrete position signal over a validated
:class:`qresearch.models.MarketSeries` and reports equity, trades and costs.

It is a pure computation: no randomness, no clock, no network, no live data,
no model calls and no optimisation.  The only strategies are the two baselines
in :mod:`qbacktest.baselines`.

See ``README_BLOCK2B.md`` for the full execution, cost and reporting contract.
"""

from __future__ import annotations

__version__ = "0.1.0"

from qbacktest.baselines import buy_and_hold_signal, cash_signal
from qbacktest.costs import (
    BPS_PER_UNIT,
    CostModel,
    buy_fill_price,
    commission_amount,
    sell_fill_price,
)
from qbacktest.engine import INITIAL_EQUITY, backtest, run_backtest
from qbacktest.errors import (
    BacktestError,
    InvalidCostError,
    InvalidSeriesError,
    InvalidSignalError,
)
from qbacktest.metrics import (
    commission_total,
    exposure_fraction,
    slippage_total,
    total_return,
    trade_count,
)
from qbacktest.models import BacktestResult, TradeRecord

__all__ = [
    "BPS_PER_UNIT",
    "BacktestError",
    "BacktestResult",
    "CostModel",
    "INITIAL_EQUITY",
    "InvalidCostError",
    "InvalidSeriesError",
    "InvalidSignalError",
    "TradeRecord",
    "__version__",
    "backtest",
    "buy_and_hold_signal",
    "buy_fill_price",
    "cash_signal",
    "commission_amount",
    "commission_total",
    "exposure_fraction",
    "run_backtest",
    "sell_fill_price",
    "slippage_total",
    "total_return",
    "trade_count",
]
