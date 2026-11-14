"""Immutable backtest records and their JSON serialization.

``to_dict()`` returns JSON-native types only.  ``None`` is preserved as
``None`` (JSON ``null``) and is never replaced by ``0`` or ``0.0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from qresearch.metrics import DrawdownResult


def _iso_utc(value: datetime) -> str:
    """Return a UTC ISO-8601 timestamp with a ``Z`` suffix."""

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One round trip (or the still-open part of one).

    An open trade keeps ``exit_index``, ``exit_timestamp``, ``exit_price`` and
    ``pnl`` as ``None``.  ``commission_paid`` and ``slippage_paid`` always hold
    the costs charged to this trade so far (entry fills for an open trade,
    entry plus exit fills for a closed trade).
    """

    entry_index: int
    entry_timestamp: datetime
    entry_price: float
    exit_index: int | None
    exit_timestamp: datetime | None
    exit_price: float | None
    units: float
    commission_paid: float
    slippage_paid: float
    pnl: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready view of the trade."""

        return {
            "entry_index": self.entry_index,
            "entry_timestamp": _iso_utc(self.entry_timestamp),
            "entry_price": self.entry_price,
            "exit_index": self.exit_index,
            "exit_timestamp": (
                None if self.exit_timestamp is None else _iso_utc(self.exit_timestamp)
            ),
            "exit_price": self.exit_price,
            "units": self.units,
            "commission_paid": self.commission_paid,
            "slippage_paid": self.slippage_paid,
            "pnl": self.pnl,
        }


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """The complete, deterministic outcome of one backtest run."""

    symbol: str
    timeframe: str
    bar_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    equity_curve: tuple[float, ...]
    trades: tuple[TradeRecord, ...]
    commission_total: float
    slippage_total: float
    exposure_fraction: float
    trade_count: int
    unexecuted_signals: int
    final_position: int
    final_units: float
    max_drawdown: DrawdownResult
    total_return: float
    commission_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "equity_curve", tuple(self.equity_curve))
        object.__setattr__(self, "trades", tuple(self.trades))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready view of the result.

        Timestamps become UTC ISO-8601 strings, tuples become lists and the
        drawdown observation becomes a plain dictionary.  ``None`` stays
        ``None`` (JSON ``null``).
        """

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bar_count": self.bar_count,
            "first_timestamp": _iso_utc(self.first_timestamp),
            "last_timestamp": _iso_utc(self.last_timestamp),
            "equity_curve": list(self.equity_curve),
            "trades": [trade.to_dict() for trade in self.trades],
            "commission_total": self.commission_total,
            "slippage_total": self.slippage_total,
            "exposure_fraction": self.exposure_fraction,
            "trade_count": self.trade_count,
            "unexecuted_signals": self.unexecuted_signals,
            "final_position": self.final_position,
            "final_units": self.final_units,
            "max_drawdown": {
                "max_drawdown": self.max_drawdown.max_drawdown,
                "peak_index": self.max_drawdown.peak_index,
                "trough_index": self.max_drawdown.trough_index,
                "peak_value": self.max_drawdown.peak_value,
                "trough_value": self.max_drawdown.trough_value,
            },
            "total_return": self.total_return,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
        }


__all__ = [
    "BacktestResult",
    "TradeRecord",
]
