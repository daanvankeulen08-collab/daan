"""Strict market-data model tests using synthetic observations."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from _qresearch_helpers import BASE, make_bar, make_series
from qresearch.errors import MarketDataError
from qresearch.models import MarketSeries


def test_bar_normalizes_offset_timestamp_to_utc() -> None:
    bar = make_bar(
        timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    )
    assert bar.timestamp == datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert bar.to_dict()["timestamp"] == "2024-01-01T08:00:00Z"


def test_bar_accepts_zulu_timestamp_string() -> None:
    bar = make_bar(timestamp="2024-01-01T00:00:00Z")
    assert bar.timestamp == BASE
    assert bar.to_dict()["timestamp"] == "2024-01-01T00:00:00Z"


def test_bar_rejects_naive_timestamp() -> None:
    with pytest.raises(MarketDataError, match="timezone-aware"):
        make_bar(timestamp=datetime(2024, 1, 1))


@pytest.mark.parametrize(
    "timestamp",
    ["", "   ", "not-a-timestamp", "2024-13-01T00:00:00Z", 123.0],
)
def test_bar_rejects_invalid_timestamp_values(timestamp: object) -> None:
    with pytest.raises(MarketDataError):
        make_bar(timestamp=timestamp)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"high": 80.0, "low": 90.0}, "high must be greater than or equal to low"),
        ({"high": 90.0, "low": 80.0, "open_price": 100.0, "close": 95.0},
         "high must be greater than or equal to open"),
        ({"high": 95.0, "low": 80.0, "open_price": 90.0, "close": 100.0},
         "high must be greater than or equal to close"),
        ({"high": 110.0, "low": 101.0, "open_price": 100.0, "close": 105.0},
         "low must be less than or equal to open"),
        ({"high": 110.0, "low": 95.0, "open_price": 100.0, "close": 90.0},
         "low must be less than or equal to close"),
    ],
)
def test_bar_rejects_invalid_ohlc_relationships(
    kwargs: dict[str, float], message: str
) -> None:
    with pytest.raises(MarketDataError, match=message):
        make_bar(**kwargs)


def test_bar_rejects_negative_volume() -> None:
    with pytest.raises(MarketDataError, match="volume must be non-negative"):
        make_bar(volume=-1.0)


def test_bar_accepts_zero_volume() -> None:
    assert make_bar(volume=0.0).volume == 0.0


def test_bar_normalizes_negative_zero_volume() -> None:
    bar = make_bar(volume=-0.0)
    assert bar.volume == 0.0
    assert math.copysign(1.0, bar.volume) == 1.0


@pytest.mark.parametrize("field", ["open_price", "high", "low", "close"])
@pytest.mark.parametrize("bad_value", [0.0, -1.0, -100.0])
def test_bar_rejects_zero_and_negative_prices(
    field: str, bad_value: float
) -> None:
    with pytest.raises(MarketDataError, match="must be positive"):
        make_bar(**{field: bad_value})


@pytest.mark.parametrize("field", ["open_price", "high", "low", "close", "volume"])
@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_bar_rejects_nan_and_infinite_values(
    field: str, bad_value: float
) -> None:
    with pytest.raises(MarketDataError, match="finite"):
        make_bar(**{field: bad_value})


@pytest.mark.parametrize("field", ["open_price", "high", "low", "close", "volume"])
def test_bar_rejects_boolean_numbers(field: str) -> None:
    with pytest.raises(MarketDataError, match="bool is not allowed"):
        make_bar(**{field: True})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", ""),
        ("symbol", "   "),
        ("symbol", " TEST"),
        ("symbol", "TEST "),
        ("timeframe", ""),
        ("timeframe", " 1h"),
        ("timeframe", 5),
    ],
)
def test_bar_rejects_invalid_text_fields(field: str, value: object) -> None:
    with pytest.raises(MarketDataError):
        make_bar(**{field: value})


def test_series_preserves_order_and_exposes_properties() -> None:
    bars = (make_bar(0, close=100.0), make_bar(1, close=101.0))
    series = MarketSeries(bars)

    assert len(series) == 2
    assert series.symbol == "TEST"
    assert series.timeframe == "1h"
    assert tuple(series) == bars
    assert series.first_timestamp == bars[0].timestamp
    assert series.last_timestamp == bars[1].timestamp
    assert series.timestamps == (bars[0].timestamp, bars[1].timestamp)
    assert series.closes == (100.0, 101.0)


def test_series_rejects_empty_input() -> None:
    with pytest.raises(MarketDataError, match="at least one bar"):
        MarketSeries(())


def test_series_rejects_non_iterable_input() -> None:
    with pytest.raises(MarketDataError, match="iterable"):
        MarketSeries(42)  # type: ignore[arg-type]


def test_series_rejects_non_bar_members() -> None:
    with pytest.raises(MarketDataError, match="must be a MarketBar"):
        MarketSeries((make_bar(0), "not-a-bar"))  # type: ignore[arg-type]


def test_series_rejects_mixed_symbols() -> None:
    with pytest.raises(MarketDataError, match="mixed symbols"):
        MarketSeries((make_bar(0), make_bar(1, symbol="OTHER")))


def test_series_rejects_mixed_timeframes() -> None:
    with pytest.raises(MarketDataError, match="mixed timeframes"):
        MarketSeries((make_bar(0), make_bar(1, timeframe="1d")))


def test_series_rejects_duplicate_timestamps() -> None:
    with pytest.raises(MarketDataError, match="duplicate timestamp"):
        MarketSeries((make_bar(0), make_bar(1, timestamp=BASE)))


def test_series_rejects_out_of_order_timestamps() -> None:
    with pytest.raises(MarketDataError, match="strictly chronological"):
        MarketSeries((make_bar(1), make_bar(0)))


def test_series_accepts_dst_style_gap_without_filling() -> None:
    """A missing interval is not an error and is never filled in."""

    first = make_bar(0)
    third = make_bar(2)
    series = MarketSeries((first, third))
    assert len(series) == 2
    assert series.timestamps == (first.timestamp, third.timestamp)


def test_bar_to_dict_is_json_ready() -> None:
    import json

    payload = make_series((100.0, 101.0)).bars[1].to_dict()
    assert payload["timestamp"] == "2024-01-01T01:00:00Z"
    json.dumps(payload)
