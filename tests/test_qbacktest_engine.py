"""Deterministic behaviour of the qbacktest engine.

Every expectation in this module is hand-computed from the synthetic fixture

    t0 open=100 close=100 | t1 open=100 close=110
    t2 open=110 close=90  | t3 open=90  close=120

with zero or explicitly priced costs.  No real market data is used.
"""

from __future__ import annotations

import json

import pytest

from _qbacktest_helpers import (
    FIXTURE_OHLC,
    make_empty_series,
    make_fixture_series,
    make_series_from,
)
from qbacktest import (
    InvalidCostError,
    InvalidSeriesError,
    InvalidSignalError,
    buy_and_hold_signal,
    cash_signal,
    run_backtest,
)
from qresearch.models import MarketSeries


def _run(signal, *, commission_bps=0.0, slippage_bps=0.0):
    return run_backtest(
        make_fixture_series(),
        signal,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


# --------------------------------------------------------------------------
# Baseline behaviour
# --------------------------------------------------------------------------


def test_buy_and_hold_zero_cost_total_return_is_20_percent() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()))

    assert result.total_return == pytest.approx(0.20, abs=1e-12)


def test_buy_and_hold_equity_path() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()))

    expected = (1.0, 1.10, 0.90, 1.20)
    assert len(result.equity_curve) == len(expected)
    for actual, wanted in zip(result.equity_curve, expected):
        assert actual == pytest.approx(wanted, abs=1e-12)


def test_buy_and_hold_max_drawdown_is_two_elevenths() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()))

    # peak 1.10 -> trough 0.90: (1.10 - 0.90) / 1.10 == 2 / 11
    assert result.max_drawdown.max_drawdown == pytest.approx(2 / 11, abs=1e-12)
    assert result.max_drawdown.peak_index == 1
    assert result.max_drawdown.trough_index == 2


def test_buy_and_hold_trade_is_open_at_the_end() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()))

    assert result.trade_count == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.entry_price == pytest.approx(100.0, abs=1e-12)
    assert trade.units == pytest.approx(0.01, abs=1e-12)
    assert trade.exit_index is None
    assert trade.exit_timestamp is None
    assert trade.exit_price is None
    assert trade.pnl is None
    assert result.final_position == 1
    assert result.final_units == pytest.approx(0.01, abs=1e-12)
    assert result.unexecuted_signals == 0
    assert result.exposure_fraction == pytest.approx(0.75, abs=1e-12)
    assert result.commission_total == pytest.approx(0.0, abs=1e-12)
    assert result.slippage_total == pytest.approx(0.0, abs=1e-12)


def test_cash_baseline_is_flat_and_has_no_trades() -> None:
    result = _run(cash_signal(make_fixture_series()))

    assert result.equity_curve == (1.0, 1.0, 1.0, 1.0)
    assert result.trade_count == 0
    assert result.trades == ()
    assert result.max_drawdown.max_drawdown == 0.0
    assert result.total_return == 0.0
    assert result.final_position == 0
    assert result.final_units == 0.0
    assert result.exposure_fraction == 0.0
    assert result.unexecuted_signals == 0


# --------------------------------------------------------------------------
# Costs
# --------------------------------------------------------------------------


def test_commission_reduces_units_and_final_equity() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()), commission_bps=10.0)

    # 1.0 of budget - 0.001 commission == 0.999 invested at 100 == 0.00999 units
    assert result.final_units == pytest.approx(0.999 / 100, abs=1e-12)
    # cash is fully committed, so equity is just the marked position
    assert result.equity_curve[-1] == pytest.approx(0.00999 * 120, abs=1e-12)
    assert result.equity_curve[-1] == pytest.approx(1.1988, abs=1e-12)
    assert result.commission_total == pytest.approx(0.001, abs=1e-12)
    assert result.trades[0].commission_paid == pytest.approx(0.001, abs=1e-12)


def test_slippage_moves_the_fill_price_up_on_a_buy() -> None:
    result = _run(buy_and_hold_signal(make_fixture_series()), slippage_bps=10.0)

    # buy fill == open * (1 + 0.001) == 100.1, never the close of the bar
    assert result.trades[0].entry_price == pytest.approx(100.1, abs=1e-9)
    assert result.trades[0].entry_index == 1
    assert result.slippage_total > 0.0
    assert result.commission_total == pytest.approx(0.0, abs=1e-12)


def test_slippage_moves_the_fill_price_down_on_a_sell() -> None:
    series = make_series_from(((100.0, 100.0), (100.0, 110.0), (110.0, 90.0)))
    result = run_backtest(
        series,
        (1, 0, 0),
        commission_bps=0.0,
        slippage_bps=10.0,
    )

    # the sell is scheduled after t1's close and fills at t2's open
    assert result.trades[0].exit_index == 2
    assert result.trades[0].exit_price == pytest.approx(110.0 * 0.999, abs=1e-9)


def test_costs_are_required_keyword_arguments() -> None:
    series = make_fixture_series()
    signal = buy_and_hold_signal(series)

    with pytest.raises(TypeError):
        run_backtest(series, signal)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        run_backtest(series, signal, 0.0, 0.0)  # type: ignore[misc]


def test_higher_costs_never_increase_final_equity() -> None:
    series = make_fixture_series()
    signal = buy_and_hold_signal(series)

    commission_levels = (0.0, 1.0, 5.0, 10.0, 25.0, 100.0)
    finals = [
        run_backtest(
            series,
            signal,
            commission_bps=level,
            slippage_bps=0.0,
        ).equity_curve[-1]
        for level in commission_levels
    ]
    for previous, current in zip(finals, finals[1:]):
        assert current <= previous

    slippage_levels = (0.0, 1.0, 5.0, 10.0, 25.0, 100.0)
    finals = [
        run_backtest(
            series,
            signal,
            commission_bps=0.0,
            slippage_bps=level,
        ).equity_curve[-1]
        for level in slippage_levels
    ]
    for previous, current in zip(finals, finals[1:]):
        assert current <= previous

    combined = [
        run_backtest(
            series,
            signal,
            commission_bps=commission,
            slippage_bps=slippage,
        ).equity_curve[-1]
        for commission in commission_levels
        for slippage in slippage_levels
    ]
    assert min(combined) <= finals[0]
    assert combined[-1] <= combined[0]


# --------------------------------------------------------------------------
# Next-bar execution (no look-ahead)
# --------------------------------------------------------------------------


def test_signal_is_executed_at_the_next_bar_open() -> None:
    result = _run([0, 0, 1, 0])

    # the change is observed after t2's close and fills at t3's open (90)
    assert result.trades[0].entry_index == 3
    assert result.trades[0].entry_price == pytest.approx(90.0, abs=1e-12)
    assert result.trades[0].entry_timestamp == make_fixture_series().bars[3].timestamp


def test_lookahead_signal_leaves_earlier_bars_untouched() -> None:
    result = _run([0, 0, 1, 0])

    assert result.equity_curve[:3] == (1.0, 1.0, 1.0)
    assert result.equity_curve[3] == pytest.approx(120 / 90, abs=1e-12)
    assert result.trade_count == 1
    assert result.final_position == 1
    assert result.final_units == pytest.approx(1 / 90, abs=1e-12)
    assert result.exposure_fraction == pytest.approx(0.25, abs=1e-12)


def test_execution_never_uses_the_signal_bar_close() -> None:
    series = make_series_from(((100.0, 100.0), (105.0, 110.0), (105.0, 120.0)))
    result = run_backtest(series, (1, 1, 1), commission_bps=0.0, slippage_bps=0.0)

    # t0's signal fills at t1's open (105), not at t0's close (100) and not at
    # t1's close (110)
    assert result.trades[0].entry_index == 1
    assert result.trades[0].entry_price == pytest.approx(105.0, abs=1e-12)


def test_signal_on_the_final_bar_is_unexecuted() -> None:
    result = _run([0, 0, 0, 1])

    assert result.unexecuted_signals == 1
    assert result.trades == ()
    assert result.trade_count == 0
    assert result.equity_curve == (1.0, 1.0, 1.0, 1.0)
    assert result.final_position == 0
    assert result.final_units == 0.0


def test_signal_that_does_not_change_the_position_is_not_unexecuted() -> None:
    result = _run([0, 0, 1, 1])

    assert result.unexecuted_signals == 0
    assert result.trade_count == 1


def test_a_round_trip_records_both_fills_and_a_net_pnl() -> None:
    result = _run([1, 0, 0, 0])

    assert result.trade_count == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.entry_price == pytest.approx(100.0, abs=1e-12)
    assert trade.exit_index == 2
    assert trade.exit_price == pytest.approx(110.0, abs=1e-12)
    assert trade.units == pytest.approx(0.01, abs=1e-12)
    assert trade.pnl == pytest.approx(0.01 * (110.0 - 100.0), abs=1e-12)
    assert result.final_position == 0
    assert result.final_units == 0.0
    assert result.equity_curve[-1] == pytest.approx(1.1, abs=1e-12)
    assert result.total_return == pytest.approx(0.1, abs=1e-12)


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_identical_inputs_produce_byte_identical_json() -> None:
    series = make_fixture_series()
    signal = buy_and_hold_signal(series)

    first = run_backtest(series, signal, commission_bps=10.0, slippage_bps=5.0)
    second = run_backtest(series, signal, commission_bps=10.0, slippage_bps=5.0)

    first_bytes = json.dumps(
        first.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    second_bytes = json.dumps(
        second.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

    assert first_bytes == second_bytes


def test_repeated_runs_of_the_same_series_are_equal() -> None:
    series = make_fixture_series()
    signal = buy_and_hold_signal(series)

    first = run_backtest(series, signal, commission_bps=0.0, slippage_bps=0.0)
    second = run_backtest(
        make_fixture_series(),
        buy_and_hold_signal(make_fixture_series()),
        commission_bps=0.0,
        slippage_bps=0.0,
    )

    assert first == second


# --------------------------------------------------------------------------
# Invalid input
# --------------------------------------------------------------------------


@pytest.mark.parametrize("commission_bps", [-1.0, -0.1, -100.0])
def test_negative_commission_is_rejected(commission_bps: float) -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidCostError):
        run_backtest(
            series,
            buy_and_hold_signal(series),
            commission_bps=commission_bps,
            slippage_bps=0.0,
        )


@pytest.mark.parametrize("slippage_bps", [-1.0, -0.1, -100.0])
def test_negative_slippage_is_rejected(slippage_bps: float) -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidCostError):
        run_backtest(
            series,
            buy_and_hold_signal(series),
            commission_bps=0.0,
            slippage_bps=slippage_bps,
        )


@pytest.mark.parametrize(
    "commission_bps", [float("nan"), float("inf"), float("-inf")]
)
def test_non_finite_commission_is_rejected(commission_bps: float) -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidCostError):
        run_backtest(
            series,
            buy_and_hold_signal(series),
            commission_bps=commission_bps,
            slippage_bps=0.0,
        )


@pytest.mark.parametrize(
    "slippage_bps", [float("nan"), float("inf"), float("-inf")]
)
def test_non_finite_slippage_is_rejected(slippage_bps: float) -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidCostError):
        run_backtest(
            series,
            buy_and_hold_signal(series),
            commission_bps=0.0,
            slippage_bps=slippage_bps,
        )


def test_signal_length_mismatch_is_rejected() -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidSignalError):
        run_backtest(
            series,
            (1, 0, 1),
            commission_bps=0.0,
            slippage_bps=0.0,
        )


def test_non_integer_signal_values_are_rejected() -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidSignalError):
        run_backtest(
            series,
            (0.5, 0.0, 1.0, 1.0),
            commission_bps=0.0,
            slippage_bps=0.0,
        )


def test_signal_values_outside_zero_and_one_are_rejected() -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidSignalError):
        run_backtest(
            series,
            (0, 0, 2, 0),
            commission_bps=0.0,
            slippage_bps=0.0,
        )


def test_text_signal_is_rejected() -> None:
    series = make_fixture_series()
    with pytest.raises(InvalidSignalError):
        run_backtest(
            series,
            "1010",
            commission_bps=0.0,
            slippage_bps=0.0,
        )


def test_empty_series_is_rejected() -> None:
    with pytest.raises(InvalidSeriesError):
        run_backtest(
            make_empty_series(),
            (),
            commission_bps=0.0,
            slippage_bps=0.0,
        )


@pytest.mark.parametrize("series", [None, "SYNTH", 42, [(100.0, 100.0)]])
def test_non_market_series_input_is_rejected(series: object) -> None:
    with pytest.raises(InvalidSeriesError):
        run_backtest(
            series,  # type: ignore[arg-type]
            (0, 0, 0, 0),
            commission_bps=0.0,
            slippage_bps=0.0,
        )


def test_bool_signals_are_accepted() -> None:
    series = make_fixture_series()
    result = run_backtest(
        series,
        (False, True, True, True),
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    expected = run_backtest(
        series,
        (0, 1, 1, 1),
        commission_bps=0.0,
        slippage_bps=0.0,
    )

    assert result == expected


def test_fixture_geometry_is_the_documented_one() -> None:
    series = make_fixture_series()

    assert isinstance(series, MarketSeries)
    assert len(series) == 4
    assert [(bar.open, bar.close) for bar in series] == list(FIXTURE_OHLC)
    assert [bar.volume for bar in series] == [1000.0] * 4
    assert series.symbol == "SYNTH"
    assert series.timeframe == "1m"
