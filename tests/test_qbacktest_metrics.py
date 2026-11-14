"""The closed metric set exposed by qbacktest.metrics."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from qbacktest import (
    BacktestError,
    TradeRecord,
    commission_total,
    exposure_fraction,
    slippage_total,
    total_return,
    trade_count,
)


def _trade(
    *,
    commission_paid: float = 0.0,
    slippage_paid: float = 0.0,
) -> TradeRecord:
    return TradeRecord(
        entry_index=0,
        entry_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=100.0,
        exit_index=1,
        exit_timestamp=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
        exit_price=110.0,
        units=0.01,
        commission_paid=commission_paid,
        slippage_paid=slippage_paid,
        pnl=0.1,
    )


def test_total_return_is_a_decimal_fraction() -> None:
    assert total_return((1.0, 1.1, 1.2)) == pytest.approx(0.2, abs=1e-12)
    assert total_return((1.0,)) == 0.0
    assert total_return((2.0, 1.0), initial_equity=2.0) == pytest.approx(-0.5)


def test_total_return_rejects_an_empty_curve() -> None:
    with pytest.raises(BacktestError):
        total_return(())


def test_total_return_rejects_a_non_positive_initial_equity() -> None:
    with pytest.raises(BacktestError):
        total_return((1.0,), initial_equity=0.0)


def test_exposure_fraction() -> None:
    assert exposure_fraction(3, 4) == pytest.approx(0.75, abs=1e-12)
    assert exposure_fraction(0, 4) == 0.0
    assert exposure_fraction(4, 4) == 1.0


def test_exposure_fraction_rejects_invalid_counts() -> None:
    with pytest.raises(BacktestError):
        exposure_fraction(0, 0)
    with pytest.raises(BacktestError):
        exposure_fraction(5, 4)
    with pytest.raises(BacktestError):
        exposure_fraction(-1, 4)


def test_cost_totals_sum_the_trades() -> None:
    trades = (
        _trade(commission_paid=0.001, slippage_paid=0.01),
        _trade(commission_paid=0.002, slippage_paid=0.02),
    )

    assert commission_total(trades) == pytest.approx(0.003, abs=1e-12)
    assert slippage_total(trades) == pytest.approx(0.03, abs=1e-12)
    assert trade_count(trades) == 2


def test_cost_totals_are_zero_without_trades() -> None:
    assert commission_total(()) == 0.0
    assert slippage_total(()) == 0.0
    assert trade_count(()) == 0


def test_no_risk_adjusted_metric_is_exposed() -> None:
    import qbacktest.metrics as metrics_module

    exported = set(metrics_module.__all__)
    assert exported == {
        "commission_total",
        "exposure_fraction",
        "slippage_total",
        "total_return",
        "trade_count",
    }
    assert not hasattr(metrics_module, "sharpe_ratio")
    assert not hasattr(metrics_module, "sortino_ratio")
