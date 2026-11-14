"""The two baseline signals allowed in Block 2B."""

from __future__ import annotations

import pytest

from _qbacktest_helpers import make_fixture_series
from qbacktest import InvalidSeriesError, buy_and_hold_signal, cash_signal


def test_buy_and_hold_signal_is_all_ones() -> None:
    series = make_fixture_series()

    signal = buy_and_hold_signal(series)

    assert signal == (1, 1, 1, 1)
    assert len(signal) == len(series)


def test_cash_signal_is_all_zeros() -> None:
    series = make_fixture_series()

    signal = cash_signal(series)

    assert signal == (0, 0, 0, 0)
    assert len(signal) == len(series)


def test_baselines_reject_a_non_market_series() -> None:
    with pytest.raises(InvalidSeriesError):
        buy_and_hold_signal("SYNTH")  # type: ignore[arg-type]
    with pytest.raises(InvalidSeriesError):
        cash_signal(None)  # type: ignore[arg-type]


def test_baselines_are_deterministic() -> None:
    series = make_fixture_series()

    assert buy_and_hold_signal(series) == buy_and_hold_signal(series)
    assert cash_signal(series) == cash_signal(series)
