"""Hand-calculated return, indicator and drawdown tests."""

from __future__ import annotations

import math

import pytest

from qresearch.errors import CalculationError, MarketDataError
from qresearch.indicators import (
    rolling_volatility,
    rolling_volatility_from_log_returns,
    simple_moving_average,
)
from qresearch.metrics import DrawdownResult, max_drawdown, maximum_drawdown
from qresearch.returns import (
    log_return,
    log_returns,
    simple_return,
    simple_returns,
)


def _sample_sd(first: float, second: float) -> float:
    mean = (first + second) / 2.0
    return math.sqrt(
        ((first - mean) ** 2 + (second - mean) ** 2) / (2 - 1)
    )


def test_simple_return_hand_calculation() -> None:
    assert simple_return(110.0, 100.0) == pytest.approx(0.10)
    assert simple_return(99.0, 110.0) == pytest.approx(-0.10)
    assert simple_return(50.0, 50.0) == 0.0


def test_log_return_hand_calculation() -> None:
    assert log_return(110.0, 100.0) == pytest.approx(math.log(1.1))
    assert log_return(50.0, 100.0) == pytest.approx(math.log(0.5))


def test_simple_returns_align_with_prices_and_start_with_none() -> None:
    values = simple_returns([100.0, 110.0, 99.0, 108.9])

    assert values[0] is None
    assert values[1] == pytest.approx(0.10)
    assert values[2] == pytest.approx(-0.10)
    assert values[3] == pytest.approx(0.10)


def test_log_returns_align_with_prices_and_start_with_none() -> None:
    values = log_returns([100.0, 110.0, 99.0, 108.9])

    assert values[0] is None
    assert values[1] == pytest.approx(math.log(1.1))
    assert values[2] == pytest.approx(math.log(0.9))
    assert values[3] == pytest.approx(math.log(1.1))


def test_returns_edge_cases_for_empty_and_single_observation() -> None:
    assert simple_returns([]) == ()
    assert simple_returns([100.0]) == (None,)
    assert log_returns([]) == ()
    assert log_returns([100.0]) == (None,)


@pytest.mark.parametrize("price", [0.0, -1.0, math.nan, math.inf, -math.inf])
def test_returns_reject_invalid_prices(price: float) -> None:
    with pytest.raises(MarketDataError):
        simple_returns([100.0, price])
    with pytest.raises(MarketDataError):
        log_returns([100.0, price])


def test_returns_reject_zero_previous_price() -> None:
    with pytest.raises(MarketDataError, match="must be positive"):
        simple_return(100.0, 0.0)


def test_simple_moving_average_hand_calculation() -> None:
    values = simple_moving_average([1.0, 2.0, 3.0, 4.0, 5.0], 3)

    assert values == (None, None, 2.0, 3.0, 4.0)


def test_simple_moving_average_window_two() -> None:
    values = simple_moving_average([1.0, 2.0, 3.0, 4.0], 2)

    assert values == (None, 1.5, 2.5, 3.5)


def test_simple_moving_average_uses_full_window_only() -> None:
    assert simple_moving_average([10.0, 20.0], 3) == (None, None)
    assert simple_moving_average([10.0, 20.0], 2) == (None, 15.0)


def test_simple_moving_average_window_equal_to_length() -> None:
    assert simple_moving_average([1.0, 2.0, 3.0], 3) == (None, None, 2.0)


def test_simple_moving_average_empty_and_window_one() -> None:
    assert simple_moving_average([], 1) == ()
    assert simple_moving_average([42.0], 1) == (42.0,)


def test_simple_moving_average_handles_decimal_input_without_partial_windows() -> None:
    values = simple_moving_average([0.1, 0.2, 0.3], 3)

    assert values[0] is None
    assert values[1] is None
    assert values[2] == pytest.approx(0.2)


@pytest.mark.parametrize("window", [0, -1, 1.5, True, "2"])
def test_simple_moving_average_rejects_invalid_windows(window: object) -> None:
    with pytest.raises(CalculationError, match="positive integer"):
        simple_moving_average([1.0, 2.0], window)  # type: ignore[arg-type]


def test_simple_moving_average_rejects_nan() -> None:
    with pytest.raises(MarketDataError, match="finite"):
        simple_moving_average([1.0, math.nan], 2)


def test_rolling_volatility_hand_calculation_sample_standard_deviation() -> None:
    values = rolling_volatility_from_log_returns([0.01, 0.02, 0.04], 2)

    assert values[0] is None
    assert values[1] == pytest.approx(math.sqrt(0.00005))
    assert values[2] == pytest.approx(math.sqrt(0.0002))


def test_rolling_volatility_population_standard_deviation() -> None:
    values = rolling_volatility_from_log_returns(
        [0.01, 0.02, 0.04], 2, ddof=0
    )

    assert values[1] == pytest.approx(0.005)
    assert values[2] == pytest.approx(0.01)


def test_rolling_volatility_requires_explicit_annualization() -> None:
    raw = rolling_volatility_from_log_returns([0.01, 0.02], 2)
    annualized = rolling_volatility_from_log_returns(
        [0.01, 0.02], 2, annualization_factor=252.0
    )

    assert raw[1] == pytest.approx(_sample_sd(0.01, 0.02))
    assert annualized[1] == pytest.approx(raw[1] * math.sqrt(252.0))


def test_rolling_volatility_propagates_missing_returns() -> None:
    values = rolling_volatility_from_log_returns(
        [None, 0.01, 0.02, 0.03], 3
    )

    assert values == (None, None, None, pytest.approx(0.01))


def test_rolling_volatility_window_with_missing_observation_is_none() -> None:
    values = rolling_volatility_from_log_returns([None, 0.01, 0.02], 2)

    assert values[0] is None
    assert values[1] is None
    assert values[2] == pytest.approx(_sample_sd(0.01, 0.02))


def test_rolling_volatility_from_prices_aligns_to_observations() -> None:
    values = rolling_volatility([100.0, 110.0, 99.0, 108.9], 2)
    first = math.log(110.0 / 100.0)
    second = math.log(99.0 / 110.0)
    third = math.log(108.9 / 99.0)

    assert values[0] is None
    assert values[1] is None
    assert values[2] == pytest.approx(_sample_sd(first, second))
    assert values[3] == pytest.approx(_sample_sd(second, third))


def test_rolling_volatility_insufficient_data_is_all_none() -> None:
    assert rolling_volatility_from_log_returns([0.01, 0.02], 3) == (None, None)
    assert rolling_volatility([100.0], 2) == (None,)


@pytest.mark.parametrize("window, ddof", [(1, 1), (2, 2), (3, 4)])
def test_rolling_volatility_rejects_ddof_not_below_window(
    window: int, ddof: int
) -> None:
    with pytest.raises(CalculationError, match="smaller than window"):
        rolling_volatility_from_log_returns([0.01, 0.02, 0.03], window, ddof=ddof)


@pytest.mark.parametrize("ddof", [-1, 1.5, True, "1"])
def test_rolling_volatility_rejects_invalid_ddof(ddof: object) -> None:
    with pytest.raises(CalculationError, match="non-negative integer"):
        rolling_volatility_from_log_returns(
            [0.01, 0.02, 0.03], 2, ddof=ddof  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("factor", [0.0, -1.0, math.nan, math.inf])
def test_rolling_volatility_rejects_invalid_annualization(factor: float) -> None:
    with pytest.raises(CalculationError):
        rolling_volatility_from_log_returns(
            [0.01, 0.02], 2, annualization_factor=factor
        )


def test_rolling_volatility_rejects_nan_returns() -> None:
    with pytest.raises(MarketDataError, match="finite"):
        rolling_volatility_from_log_returns([0.01, math.nan], 2)


@pytest.mark.parametrize("window", [0, -2, 2.5, True])
def test_rolling_volatility_rejects_invalid_windows(window: object) -> None:
    with pytest.raises(CalculationError, match="positive integer"):
        rolling_volatility_from_log_returns(
            [0.01, 0.02], window  # type: ignore[arg-type]
        )


def test_rolling_volatility_rejects_invalid_prices() -> None:
    with pytest.raises(MarketDataError, match="must be positive"):
        rolling_volatility([100.0, 0.0], 2)


def test_maximum_drawdown_hand_calculation() -> None:
    result = maximum_drawdown([100.0, 120.0, 90.0, 110.0, 80.0, 130.0])

    assert isinstance(result, DrawdownResult)
    assert result.max_drawdown == pytest.approx(1.0 / 3.0)
    assert result.peak_index == 1
    assert result.trough_index == 4
    assert result.peak_value == 120.0
    assert result.trough_value == 80.0


def test_maximum_drawdown_requires_a_decline() -> None:
    result = maximum_drawdown([100.0, 101.0, 102.0])

    assert result.max_drawdown == 0.0
    assert result.peak_index == 0
    assert result.trough_index == 0
    assert result.peak_value == 100.0
    assert result.trough_value == 100.0


def test_maximum_drawdown_single_observation() -> None:
    result = maximum_drawdown([42.0])

    assert result.max_drawdown == 0.0
    assert result.peak_index == result.trough_index == 0


def test_maximum_drawdown_from_first_observation() -> None:
    result = maximum_drawdown([100.0, 80.0])

    assert result.max_drawdown == pytest.approx(0.20)
    assert (result.peak_index, result.trough_index) == (0, 1)


def test_maximum_drawdown_keeps_earliest_equal_peak() -> None:
    result = maximum_drawdown([100.0, 120.0, 100.0, 120.0, 80.0])

    assert result.max_drawdown == pytest.approx(1.0 / 3.0)
    assert result.peak_index == 1
    assert result.trough_index == 4


def test_maximum_drawdown_recovers_and_continues() -> None:
    result = maximum_drawdown([100.0, 99.0, 105.0, 95.0])

    assert result.max_drawdown == pytest.approx(10.0 / 105.0)
    assert (result.peak_index, result.trough_index) == (2, 3)


def test_maximum_drawdown_alias() -> None:
    assert max_drawdown is maximum_drawdown


@pytest.mark.parametrize("prices", [[], (), [0.0], [100.0, -1.0], [math.nan]])
def test_maximum_drawdown_rejects_invalid_input(prices: object) -> None:
    with pytest.raises((CalculationError, MarketDataError)):
        maximum_drawdown(prices)  # type: ignore[arg-type]


def test_maximum_drawdown_rejects_non_iterable_input() -> None:
    with pytest.raises(CalculationError, match="iterable"):
        maximum_drawdown(42)  # type: ignore[arg-type]
