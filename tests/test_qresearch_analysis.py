"""End-to-end analysis, serialization, hashing and CSV integration tests."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from _qresearch_helpers import (
    BASE,
    COLUMNS,
    csv_text,
    make_bar,
    make_row,
    make_series,
    write_text,
)
import qresearch
from qresearch import csv_loader
from qresearch.analysis import (
    CANONICAL_FORMAT,
    CANONICAL_HASH_SOURCE,
    CSV_HASH_SOURCE,
    analyze_csv,
    analyze_series,
    canonical_series_bytes,
    canonical_series_payload,
    canonical_series_sha256,
)
from qresearch.errors import CalculationError, CSVValidationError, PathSecurityError
from qresearch.models import MarketSeries


def _sample_sd(first: float, second: float) -> float:
    mean = (first + second) / 2.0
    return math.sqrt(
        ((first - mean) ** 2 + (second - mean) ** 2) / (2 - 1)
    )


@pytest.fixture
def market_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "market_samples"
    root.mkdir()
    monkeypatch.setattr(csv_loader, "MARKET_DATA_DIR", root)
    return root


def test_analyze_series_complete_result() -> None:
    series = make_series([100.0, 110.0, 99.0, 108.9])

    result = analyze_series(
        series,
        moving_average_windows=(2, 3),
        volatility_windows=(2,),
        annualization_factor=252.0,
    )

    assert result.symbol == "TEST"
    assert result.timeframe == "1h"
    assert result.observation_count == 4
    assert result.first_timestamp == BASE
    assert result.last_timestamp == BASE + timedelta(hours=3)
    assert result.content_hash_source == CANONICAL_HASH_SOURCE
    assert result.content_sha256 == canonical_series_sha256(series)
    assert len(result.content_sha256) == 64
    assert result.content_sha256 == result.content_sha256.lower()

    assert result.simple_returns[0] is None
    assert result.simple_returns[1] == pytest.approx(0.10)
    assert result.simple_returns[2] == pytest.approx(-0.10)
    assert result.simple_returns[3] == pytest.approx(0.10)

    assert result.log_returns[0] is None
    assert result.log_returns[1] == pytest.approx(math.log(1.1))
    assert result.log_returns[2] == pytest.approx(math.log(0.9))
    assert result.log_returns[3] == pytest.approx(math.log(1.1))

    first_ma, second_ma = result.moving_averages
    assert first_ma.window == 2
    assert first_ma.values[0] is None
    assert first_ma.values[1] == pytest.approx(105.0)
    assert first_ma.values[2] == pytest.approx(104.5)
    assert first_ma.values[3] == pytest.approx(103.95)
    assert second_ma.window == 3
    assert second_ma.values[:2] == (None, None)
    assert second_ma.values[2] == pytest.approx(103.0)
    assert second_ma.values[3] == pytest.approx(317.9 / 3.0)

    volatility = result.rolling_volatilities[0]
    assert volatility.window == 2
    assert volatility.ddof == 1
    assert volatility.annualization_factor == 252.0
    assert volatility.values[0] is None
    assert volatility.values[1] is None
    first_log = math.log(1.1)
    second_log = math.log(0.9)
    expected = _sample_sd(first_log, second_log) * math.sqrt(252.0)
    assert volatility.values[2] == pytest.approx(expected)
    assert volatility.values[3] == pytest.approx(expected)

    drawdown = result.max_drawdown
    assert drawdown.max_drawdown == pytest.approx(0.10)
    assert drawdown.peak_index == 1
    assert drawdown.trough_index == 2
    assert drawdown.peak_timestamp == BASE + timedelta(hours=1)
    assert drawdown.trough_timestamp == BASE + timedelta(hours=2)
    assert drawdown.peak_price == 110.0
    assert drawdown.trough_price == 99.0

    validation = result.validation
    assert validation.row_count == 4
    assert validation.first_timestamp == BASE
    assert validation.last_timestamp == BASE + timedelta(hours=3)
    assert validation.strictly_chronological is True
    assert validation.unique_timestamps is True
    assert validation.ohlcv_rules_passed is True
    assert validation.timezone == "UTC"
    assert validation.source_path is None
    assert validation.file_size_bytes is None


def test_missing_values_are_distinct_from_numerical_zero() -> None:
    result = analyze_series(make_series([100.0, 100.0]), moving_average_windows=(2,))

    assert result.simple_returns[0] is None
    assert result.simple_returns[1] == 0.0
    assert result.log_returns[0] is None
    assert result.log_returns[1] == 0.0
    assert result.moving_averages[0].values[0] is None
    assert result.moving_averages[0].values[1] == 100.0
    assert result.max_drawdown.max_drawdown == 0.0
    assert result.rolling_volatilities == ()


def test_result_to_dict_is_json_serializable_and_has_no_signal_fields() -> None:
    result = analyze_series(
        make_series([100.0, 100.0]),
        moving_average_windows=(2,),
        volatility_windows=(2,),
    )
    payload = result.to_dict()

    text = json.dumps(payload)
    restored = json.loads(text)

    assert restored["simple_returns"] == [None, 0.0]
    assert restored["moving_averages"][0]["values"] == [None, 100.0]
    assert restored["max_drawdown"]["max_drawdown"] == 0.0
    assert restored["validation"]["timezone"] == "UTC"
    assert "prediction" not in payload
    assert "signal" not in payload
    assert "recommendation" not in payload


def test_analysis_is_deterministic_and_hash_is_reproducible() -> None:
    first = make_series([100.0, 101.0, 99.0])
    second = make_series([100.0, 101.0, 99.0])

    assert canonical_series_bytes(first) == canonical_series_bytes(second)
    assert canonical_series_sha256(first) == canonical_series_sha256(second)
    assert analyze_series(first).to_dict() == analyze_series(second).to_dict()

    different = make_series([100.0, 101.0, 99.5])
    assert canonical_series_sha256(different) != canonical_series_sha256(first)


def test_canonical_hash_normalizes_equivalent_timestamps() -> None:
    utc_series = make_series([100.0])
    offset_bar = make_bar(
        0,
        timestamp=datetime(
            2024, 1, 1, 2, 0, tzinfo=timezone(timedelta(hours=2))
        ),
    )
    offset_series = MarketSeries((offset_bar,))

    assert offset_bar.timestamp == BASE
    assert canonical_series_sha256(offset_series) == canonical_series_sha256(
        utc_series
    )


def test_canonical_payload_has_explicit_format() -> None:
    series = make_series([100.0, 101.0])
    payload = canonical_series_payload(series)

    assert payload["format"] == CANONICAL_FORMAT
    assert payload["symbol"] == "TEST"
    assert payload["timeframe"] == "1h"
    assert len(payload["bars"]) == 2
    assert payload["bars"][0]["timestamp"] == "2024-01-01T00:00:00Z"
    assert b'"format":"qresearch.market-series.v1"' in canonical_series_bytes(series)


def test_volume_changes_the_canonical_hash() -> None:
    first = MarketSeries((make_bar(0, volume=1.0),))
    second = MarketSeries((make_bar(0, volume=2.0),))

    assert canonical_series_sha256(first) != canonical_series_sha256(second)


def test_explicit_content_hash_and_source_are_accepted() -> None:
    digest = hashlib.sha256(b"external input").hexdigest()

    result = analyze_series(
        make_series([100.0]),
        content_sha256=digest.upper(),
        content_hash_source="external-bytes",
    )

    assert result.content_sha256 == digest
    assert result.content_hash_source == "external-bytes"


def test_explicit_content_hash_requires_a_source() -> None:
    with pytest.raises(CalculationError, match="content_hash_source is required"):
        analyze_series(
            make_series([100.0]),
            content_sha256=hashlib.sha256(b"x").hexdigest(),
        )


def test_source_without_explicit_hash_is_rejected() -> None:
    with pytest.raises(CalculationError, match="requires an explicit content_sha256"):
        analyze_series(make_series([100.0]), content_hash_source="label")


@pytest.mark.parametrize("digest", ["abc", "z" * 64, 123, None])
def test_invalid_explicit_content_hash_is_rejected(digest: object) -> None:
    if digest is None:
        with pytest.raises(CalculationError, match="requires an explicit"):
            analyze_series(make_series([100.0]), content_hash_source="label")
        return
    with pytest.raises(CalculationError):
        analyze_series(
            make_series([100.0]),
            content_sha256=digest,  # type: ignore[arg-type]
            content_hash_source="label",
        )


def test_invalid_hash_source_is_rejected() -> None:
    with pytest.raises(CalculationError):
        analyze_series(
            make_series([100.0]),
            content_sha256=hashlib.sha256(b"x").hexdigest(),
            content_hash_source="   ",
        )


def test_analyze_series_rejects_non_series_input() -> None:
    with pytest.raises(CalculationError, match="MarketSeries"):
        analyze_series([100.0, 101.0])  # type: ignore[arg-type]
    with pytest.raises(CalculationError, match="MarketSeries"):
        canonical_series_sha256([100.0])  # type: ignore[arg-type]


def test_requested_windows_keep_their_order() -> None:
    result = analyze_series(
        make_series([100.0, 101.0, 102.0]),
        moving_average_windows=(3, 2),
        volatility_windows=(3, 2),
    )

    assert tuple(item.window for item in result.moving_averages) == (3, 2)
    assert tuple(item.window for item in result.rolling_volatilities) == (3, 2)


def test_windows_accept_generators() -> None:
    result = analyze_series(
        make_series([100.0, 101.0]),
        moving_average_windows=(window for window in (2,)),
    )

    assert result.moving_averages[0].window == 2


def test_duplicate_windows_are_rejected() -> None:
    with pytest.raises(CalculationError, match="duplicate window"):
        analyze_series(
            make_series([100.0]), moving_average_windows=(2, 2)
        )
    with pytest.raises(CalculationError, match="duplicate window"):
        analyze_series(
            make_series([100.0]), volatility_windows=(2, 2)
        )


@pytest.mark.parametrize("window", [0, -1, 1.5, True])
def test_invalid_windows_are_rejected(window: object) -> None:
    with pytest.raises(CalculationError):
        analyze_series(
            make_series([100.0]),
            moving_average_windows=(window,),  # type: ignore[arg-type]
        )


def test_no_requested_windows_yield_empty_tuples() -> None:
    result = analyze_series(make_series([100.0]))

    assert result.moving_averages == ()
    assert result.rolling_volatilities == ()


@pytest.mark.parametrize("ddof", [-1, 1.5, True])
def test_invalid_volatility_ddof_is_rejected(ddof: object) -> None:
    with pytest.raises(CalculationError):
        analyze_series(
            make_series([100.0, 101.0]),
            volatility_windows=(2,),
            volatility_ddof=ddof,  # type: ignore[arg-type]
        )


def test_ddof_must_be_smaller_than_each_window() -> None:
    with pytest.raises(CalculationError, match="smaller than window"):
        analyze_series(
            make_series([100.0, 101.0]),
            volatility_windows=(2,),
            volatility_ddof=2,
        )


@pytest.mark.parametrize("factor", [0.0, -1.0, math.nan, math.inf])
def test_invalid_annualization_factor_is_rejected(factor: float) -> None:
    with pytest.raises(CalculationError):
        analyze_series(
            make_series([100.0, 101.0]),
            volatility_windows=(2,),
            annualization_factor=factor,
        )


def test_invalid_source_metadata_is_rejected() -> None:
    with pytest.raises(CalculationError):
        analyze_series(make_series([100.0]), source_path=" sample.csv")
    with pytest.raises(CalculationError):
        analyze_series(make_series([100.0]), file_size_bytes=-1)
    with pytest.raises(CalculationError):
        analyze_series(make_series([100.0]), file_size_bytes=True)


def test_analyze_csv_end_to_end(market_root: Path) -> None:
    rows = [
        make_row(0, close=100.0),
        make_row(1, close=110.0),
        make_row(2, close=99.0),
        make_row(3, close=108.9),
    ]
    path = write_text(market_root, "sample.csv", csv_text(rows))

    result = analyze_csv(
        "sample.csv",
        moving_average_windows=(2,),
        volatility_windows=(2,),
        annualization_factor=252.0,
    )

    assert result.symbol == "TEST"
    assert result.timeframe == "1h"
    assert result.observation_count == 4
    assert result.first_timestamp == BASE
    assert result.last_timestamp == BASE + timedelta(hours=3)
    assert result.content_hash_source == CSV_HASH_SOURCE
    assert result.content_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.validation.source_path == "sample.csv"
    assert result.validation.file_size_bytes == len(path.read_bytes())
    assert result.validation.row_count == 4
    assert result.simple_returns[1] == pytest.approx(0.10)
    assert result.moving_averages[0].values[3] == pytest.approx(103.95)
    assert result.max_drawdown.max_drawdown == pytest.approx(0.10)


def test_csv_header_order_changes_file_hash_not_series_hash(
    market_root: Path,
) -> None:
    rows = [make_row(0, close=100.0), make_row(1, close=101.0)]
    write_text(market_root, "ordered.csv", csv_text(rows))
    write_text(
        market_root,
        "reversed.csv",
        csv_text(rows, header=tuple(reversed(COLUMNS))),
    )

    ordered = analyze_csv("ordered.csv")
    reversed_result = analyze_csv("reversed.csv")

    assert ordered.content_sha256 != reversed_result.content_sha256
    assert ordered.simple_returns == reversed_result.simple_returns
    ordered_series = csv_loader.load_market_csv("ordered.csv").series
    reversed_series = csv_loader.load_market_csv("reversed.csv").series
    assert canonical_series_sha256(ordered_series) == canonical_series_sha256(
        reversed_series
    )


def test_analyze_csv_rejects_path_traversal(
    market_root: Path, tmp_path: Path
) -> None:
    write_text(tmp_path, "outside.csv", csv_text([make_row(0)]))

    with pytest.raises(PathSecurityError):
        analyze_csv("../outside.csv")


def test_analyze_csv_rejects_missing_file(market_root: Path) -> None:
    with pytest.raises(CSVValidationError, match="does not exist"):
        analyze_csv("missing.csv")


def test_analyze_csv_propagates_market_data_errors(market_root: Path) -> None:
    write_text(
        market_root,
        "invalid.csv",
        csv_text([make_row(0, high=90.0, low=80.0)]),
    )

    with pytest.raises(CSVValidationError, match="invalid market data"):
        analyze_csv("invalid.csv")


def test_public_package_exports_the_supported_api() -> None:
    assert qresearch.analyze_series is analyze_series
    assert qresearch.analyze_csv is analyze_csv
    assert qresearch.canonical_series_sha256 is canonical_series_sha256
    assert qresearch.MarketSeries is MarketSeries
    assert qresearch.MarketBar is make_bar().__class__
    assert qresearch.__version__ == "0.1.0"
