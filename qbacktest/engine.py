"""Deterministic, cost-aware backtest engine.

The engine replays a discrete position signal over a validated
:class:`qresearch.models.MarketSeries` and reports equity, trades and costs.

Execution contract
------------------

* ``signal[t]`` is the desired position *after* observing bar ``t``'s close.
* A change of desired position observed at bar ``t`` is executed at bar
  ``t + 1``'s **open**.  A signal is never executed at the close of the bar
  that produced it.
* A change observed on the final bar has no next open: it is counted in
  ``unexecuted_signals`` and ignored.
* The position is long (1) or flat (0) only.  Full notional, no leverage, no
  shorting, no partial sizing, one symbol per run.
* Equity is marked to market at every bar's close:
  ``equity = cash + units * close``.  Initial equity is ``1.0``.
* There is no forced liquidation at the end of the run.  The remaining
  position is reported through ``final_position`` and ``final_units``.

Cost contract
-------------

* ``commission_bps`` and ``slippage_bps`` are required keyword arguments.
* Buy fill price: ``open * (1 + slippage)``; sell fill price:
  ``open * (1 - slippage)``.  Slippage is always adverse.
* Commission is charged on the traded notional of every fill.
* A buy commits the whole available cash budget: the commission is deducted
  from that budget and the remainder is converted into units at the fill
  price, so the strategy never borrows and never shorts.

Nothing in this module is random, time-dependent or stateful.
"""

from __future__ import annotations

from typing import Any, Sequence

from qresearch.metrics import maximum_drawdown
from qresearch.models import MarketSeries

from qbacktest.costs import CostModel
from qbacktest.errors import InvalidSeriesError, InvalidSignalError
from qbacktest.metrics import (
    commission_total,
    exposure_fraction,
    slippage_total,
    total_return,
    trade_count,
)
from qbacktest.models import BacktestResult, TradeRecord

#: Every run starts with one unit of equity.
INITIAL_EQUITY = 1.0


def _validate_series(series: object) -> MarketSeries:
    if not isinstance(series, MarketSeries):
        raise InvalidSeriesError(
            f"series must be a MarketSeries; got {type(series).__name__}"
        )
    if len(series.bars) == 0:
        raise InvalidSeriesError("market series must contain at least one bar")
    return series


def _validate_signal(signal: object, *, bar_count: int) -> tuple[int, ...]:
    """Return the signal as a tuple of ``0``/``1`` positions, one per bar."""

    if isinstance(signal, (str, bytes, bytearray)):
        raise InvalidSignalError(
            "signal must be a sequence of int/bool positions, not text"
        )
    try:
        raw = tuple(signal)  # type: ignore[arg-type]
    except TypeError as exc:
        raise InvalidSignalError(
            "signal must be an iterable of int/bool positions"
        ) from exc

    if len(raw) != bar_count:
        raise InvalidSignalError(
            f"signal length {len(raw)} does not match bar count {bar_count}"
        )

    positions: list[int] = []
    for index, value in enumerate(raw):
        if isinstance(value, bool):
            positions.append(1 if value else 0)
        elif isinstance(value, int):
            if value not in (0, 1):
                raise InvalidSignalError(
                    f"signal[{index}] must be 0 (flat) or 1 (long); got {value!r}"
                )
            positions.append(value)
        else:
            raise InvalidSignalError(
                f"signal[{index}] must be an int or bool; got {type(value).__name__}"
            )
    return tuple(positions)


def run_backtest(
    series: MarketSeries,
    signal: Sequence[int | bool],
    *,
    commission_bps: float,
    slippage_bps: float,
) -> BacktestResult:
    """Replay ``signal`` over ``series`` and return a deterministic result.

    Args:
        series: a validated, non-empty, single-symbol market series.
        signal: one int/bool position per bar, aligned to the bars.
        commission_bps: commission in basis points; required, finite, ``>= 0``.
        slippage_bps: adverse slippage in basis points; required, finite,
            ``>= 0``.

    Raises:
        InvalidSeriesError: if ``series`` is not a non-empty ``MarketSeries``.
        InvalidSignalError: if ``signal`` is malformed or misaligned.
        InvalidCostError: if a cost parameter is invalid.
    """

    validated_series = _validate_series(series)
    costs = CostModel(commission_bps=commission_bps, slippage_bps=slippage_bps)
    positions = _validate_signal(signal, bar_count=len(validated_series.bars))

    bars = validated_series.bars
    final_index = len(bars) - 1

    cash = INITIAL_EQUITY
    units = 0.0
    position = 0
    desired = 0
    pending: int | None = None

    equity_curve: list[float] = []
    trades: list[TradeRecord] = []
    open_trade: TradeRecord | None = None
    exposed_bars = 0
    unexecuted_signals = 0

    for index, bar in enumerate(bars):
        # 1. Execute the order scheduled by the previous bar's close, at this
        #    bar's open.
        if pending is not None:
            target = pending
            pending = None
            if target == 1 and position == 0:
                fill_price = costs.buy_fill_price(bar.open)
                budget = cash
                commission = costs.commission_for(budget)
                bought_units = (budget - commission) / fill_price
                slippage_cost = bought_units * (fill_price - bar.open)
                cash = cash - budget
                units = bought_units
                position = 1
                open_trade = TradeRecord(
                    entry_index=index,
                    entry_timestamp=bar.timestamp,
                    entry_price=fill_price,
                    exit_index=None,
                    exit_timestamp=None,
                    exit_price=None,
                    units=bought_units,
                    commission_paid=commission,
                    slippage_paid=slippage_cost,
                    pnl=None,
                )
            elif target == 0 and position == 1:
                fill_price = costs.sell_fill_price(bar.open)
                sold_units = units
                notional = sold_units * fill_price
                commission = costs.commission_for(notional)
                slippage_cost = sold_units * (bar.open - fill_price)
                cash = cash + notional - commission
                units = 0.0
                position = 0
                if open_trade is None:  # pragma: no cover - defensive
                    raise InvalidSeriesError(
                        "internal error: sell without an open trade"
                    )
                trade_commission = open_trade.commission_paid + commission
                trade_slippage = open_trade.slippage_paid + slippage_cost
                trades.append(
                    TradeRecord(
                        entry_index=open_trade.entry_index,
                        entry_timestamp=open_trade.entry_timestamp,
                        entry_price=open_trade.entry_price,
                        exit_index=index,
                        exit_timestamp=bar.timestamp,
                        exit_price=fill_price,
                        units=sold_units,
                        commission_paid=trade_commission,
                        slippage_paid=trade_slippage,
                        pnl=(
                            sold_units * (fill_price - open_trade.entry_price)
                            - trade_commission
                        ),
                    )
                )
                open_trade = None

        # 2. Mark the portfolio to market at this bar's close.
        equity = cash + units * bar.close
        equity_curve.append(equity)
        if position == 1:
            exposed_bars += 1

        # 3. Observe the signal at this bar's close and schedule any change of
        #    desired position for the next bar's open.
        target = positions[index]
        if target != desired:
            desired = target
            if index == final_index:
                unexecuted_signals += 1
            else:
                pending = target

    if open_trade is not None:
        trades.append(open_trade)

    drawdown = maximum_drawdown(equity_curve)

    return BacktestResult(
        symbol=validated_series.symbol,
        timeframe=validated_series.timeframe,
        bar_count=len(bars),
        first_timestamp=validated_series.first_timestamp,
        last_timestamp=validated_series.last_timestamp,
        equity_curve=tuple(equity_curve),
        trades=tuple(trades),
        commission_total=commission_total(trades),
        slippage_total=slippage_total(trades),
        exposure_fraction=exposure_fraction(exposed_bars, len(bars)),
        trade_count=trade_count(trades),
        unexecuted_signals=unexecuted_signals,
        final_position=position,
        final_units=units,
        max_drawdown=drawdown,
        total_return=total_return(equity_curve, INITIAL_EQUITY),
        commission_bps=costs.commission_bps,
        slippage_bps=costs.slippage_bps,
    )


def backtest(
    series: MarketSeries,
    signal: Sequence[int | bool],
    *,
    commission_bps: float,
    slippage_bps: float,
) -> BacktestResult:
    """Alias of :func:`run_backtest`."""

    return run_backtest(
        series,
        signal,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


__all__ = [
    "INITIAL_EQUITY",
    "backtest",
    "run_backtest",
]
