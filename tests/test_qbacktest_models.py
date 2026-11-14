"""Immutability and JSON serialization of the qbacktest records."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from _qbacktest_helpers import make_fixture_series
from qbacktest import (
    BacktestResult,
    TradeRecord,
    buy_and_hold_signal,
    run_backtest,
)


def _result() -> BacktestResult:
    series = make_fixture_series()
    return run_backtest(
        series,
        buy_and_hold_signal(series),
        commission_bps=10.0,
        slippage_bps=5.0,
    )


def test_trade_record_is_frozen_and_slotted() -> None:
    trade = _result().trades[0]

    with pytest.raises(FrozenInstanceError):
        trade.units = 1.0  # type: ignore[misc]
    assert not hasattr(trade, "__dict__")


def test_backtest_result_is_frozen_and_slotted() -> None:
    result = _result()

    with pytest.raises(FrozenInstanceError):
        result.final_units = 1.0  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


def test_result_to_dict_is_json_serialisable() -> None:
    payload = _result().to_dict()

    text = json.dumps(payload, sort_keys=True, allow_nan=False)
    assert isinstance(text, str)
    assert json.loads(text) == payload


def test_open_trade_keeps_none_as_null() -> None:
    payload = _result().to_dict()
    trade = payload["trades"][0]

    assert trade["exit_index"] is None
    assert trade["exit_timestamp"] is None
    assert trade["exit_price"] is None
    assert trade["pnl"] is None
    # a genuine zero is still a number and must not become null
    assert trade["commission_paid"] == pytest.approx(0.001, abs=1e-12)


def test_result_to_dict_reports_the_documented_keys() -> None:
    payload = _result().to_dict()

    assert set(payload) == {
        "symbol",
        "timeframe",
        "bar_count",
        "first_timestamp",
        "last_timestamp",
        "equity_curve",
        "trades",
        "commission_total",
        "slippage_total",
        "exposure_fraction",
        "trade_count",
        "unexecuted_signals",
        "final_position",
        "final_units",
        "max_drawdown",
        "total_return",
        "commission_bps",
        "slippage_bps",
    }
    assert payload["symbol"] == "SYNTH"
    assert payload["timeframe"] == "1m"
    assert payload["bar_count"] == 4
    assert payload["first_timestamp"] == "2024-01-01T00:00:00Z"
    assert payload["last_timestamp"] == "2024-01-01T00:03:00Z"
    assert isinstance(payload["equity_curve"], list)
    assert isinstance(payload["trades"], list)


def test_max_drawdown_is_serialised_as_a_plain_dictionary() -> None:
    payload = _result().to_dict()

    assert set(payload["max_drawdown"]) == {
        "max_drawdown",
        "peak_index",
        "trough_index",
        "peak_value",
        "trough_value",
    }


def test_sequences_are_coerced_to_tuples() -> None:
    result = _result()

    assert isinstance(result.equity_curve, tuple)
    assert isinstance(result.trades, tuple)
    assert all(isinstance(trade, TradeRecord) for trade in result.trades)
