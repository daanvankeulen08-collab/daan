"""Exception hierarchy for the deterministic backtest package.

Every error raised by ``qbacktest`` derives from :class:`BacktestError`, so a
caller can distinguish an invalid request from an unexpected runtime failure.
No error is ever swallowed, clamped or repaired silently.
"""

from __future__ import annotations


class BacktestError(Exception):
    """Base class for every qbacktest-specific error."""


class InvalidCostError(BacktestError):
    """A commission or slippage parameter is invalid."""


class InvalidSignalError(BacktestError):
    """A signal sequence violates the signal contract."""


class InvalidSeriesError(BacktestError):
    """The market series cannot be backtested."""


__all__ = [
    "BacktestError",
    "InvalidCostError",
    "InvalidSeriesError",
    "InvalidSignalError",
]
