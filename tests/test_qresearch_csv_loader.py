"""Strict CSV loader, sandbox and limit tests using temporary directories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from _qresearch_helpers import (
    COLUMNS,
    csv_text,
    make_row,
    write_bytes,
    write_text,
)
from qresearch import csv_loader
from qresearch.csv_loader import load_market_csv
from qresearch.errors import CSVValidationError, PathSecurityError


@pytest.fixture
def market_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "market_samples"
    root.mkdir()
    monkeypatch.setattr(csv_loader, "MARKET_DATA_DIR", root)
    return root


def _valid_text(row_count: int = 3) -> str:
    return csv_text(make_row(index) for index in range(row_count))


def test_loads_valid_csv_and_reports_metadata(market_root: Path) -> None:
    path = write_text(market_root, "valid.csv", _valid_text(3))

    loaded = load_market_csv("valid.csv")

    assert loaded.row_count == 3
    assert loaded.symbol == "TEST"
    assert loaded.timeframe == "1h"
    assert loaded.series.closes == (100.0, 100.0, 100.0)
    assert [bar.timestamp.hour for bar in loaded.series] == [0, 1, 2]
    assert loaded.source_path == "valid.csv"
    assert loaded.file_size_bytes == len(path.read_bytes())
    assert loaded.content_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(loaded.content_sha256) == 64
    assert loaded.content_sha256 == loaded.content_sha256.lower()


def test_valid_csv_dict_is_json_ready(market_root: Path) -> None:
    write_text(market_root, "valid.csv", _valid_text(2))
    payload = load_market_csv("valid.csv").to_dict()
    assert payload["source_path"] == "valid.csv"
    assert payload["first_timestamp"] == "2024-01-01T00:00:00Z"
    assert payload["last_timestamp"] == "2024-01-01T01:00:00Z"
    json.dumps(payload)


def test_header_order_is_irrelevant(market_root: Path) -> None:
    rows = [make_row(0, close=100.0), make_row(1, close=101.0)]
    header = tuple(reversed(COLUMNS))
    write_text(market_root, "reversed.csv", csv_text(rows, header=header))

    loaded = load_market_csv("reversed.csv")

    assert loaded.series.closes == (100.0, 101.0)
    assert loaded.symbol == "TEST"


def test_nested_relative_path_is_allowed(market_root: Path) -> None:
    write_text(market_root, "sub/dir/sample.csv", _valid_text(2))

    loaded = load_market_csv("sub/dir/sample.csv")

    assert loaded.source_path == "sub/dir/sample.csv"
    assert loaded.row_count == 2


def test_loading_does_not_modify_the_file(market_root: Path) -> None:
    path = write_text(market_root, "readonly.csv", _valid_text(3))
    before = path.read_bytes()

    load_market_csv("readonly.csv")

    assert path.read_bytes() == before


def test_utf8_bom_is_accepted(market_root: Path) -> None:
    text = _valid_text(2)
    write_bytes(market_root, "bom.csv", b"\xef\xbb\xbf" + text.encode("utf-8"))

    loaded = load_market_csv("bom.csv")

    assert loaded.row_count == 2
    assert loaded.symbol == "TEST"


def test_missing_required_column_is_rejected(market_root: Path) -> None:
    header = [column for column in COLUMNS if column != "volume"]
    rows = [
        {key: value for key, value in make_row(0).items() if key != "volume"}
    ]
    write_text(market_root, "missing.csv", csv_text(rows, header=header))

    with pytest.raises(CSVValidationError, match="missing=.*volume"):
        load_market_csv("missing.csv")


def test_extra_column_is_rejected(market_root: Path) -> None:
    header = list(COLUMNS) + ["extra"]
    rows = [{**make_row(0), "extra": "x"}]
    write_text(market_root, "extra.csv", csv_text(rows, header=header))

    with pytest.raises(CSVValidationError, match="extra=.*extra"):
        load_market_csv("extra.csv")


def test_duplicate_header_column_is_rejected(market_root: Path) -> None:
    header = list(COLUMNS) + ["close"]
    text = ",".join(header) + "\n" + ",".join(str(v) for v in make_row(0).values()) + ",100\n"
    write_text(market_root, "duplicate_header.csv", text)

    with pytest.raises(CSVValidationError, match="duplicate column"):
        load_market_csv("duplicate_header.csv")


def test_too_many_fields_is_rejected(market_root: Path) -> None:
    header = ",".join(COLUMNS)
    row = ",".join(str(make_row(0)[column]) for column in COLUMNS)
    write_text(market_root, "wide.csv", f"{header}\n{row},EXTRA\n")

    with pytest.raises(CSVValidationError, match="too many fields"):
        load_market_csv("wide.csv")


def test_missing_row_value_is_rejected(market_root: Path) -> None:
    header = ",".join(COLUMNS)
    values = [str(make_row(0)[column]) for column in COLUMNS[:-1]]
    write_text(market_root, "short.csv", f"{header}\n{','.join(values)}\n")

    with pytest.raises(CSVValidationError, match="missing value for column 'volume'"):
        load_market_csv("short.csv")


def test_empty_row_value_is_rejected(market_root: Path) -> None:
    row = make_row(0)
    row["symbol"] = ""
    write_text(market_root, "empty_value.csv", csv_text([row]))

    with pytest.raises(CSVValidationError, match="empty value for column 'symbol'"):
        load_market_csv("empty_value.csv")


def test_surrounding_whitespace_in_value_is_rejected(market_root: Path) -> None:
    row = make_row(0)
    row["symbol"] = " TEST"
    write_text(market_root, "whitespace.csv", csv_text([row]))

    with pytest.raises(CSVValidationError, match="leading or trailing whitespace"):
        load_market_csv("whitespace.csv")


def test_invalid_ohlc_row_reports_line_number(market_root: Path) -> None:
    row = make_row(0, open_price=100.0, close=100.0, high=90.0, low=80.0)
    write_text(market_root, "invalid_ohlc.csv", csv_text([row]))

    with pytest.raises(
        CSVValidationError, match="invalid market data at line 2.*high"
    ):
        load_market_csv("invalid_ohlc.csv")


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
def test_nan_and_infinite_csv_values_are_rejected(
    market_root: Path, field: str
) -> None:
    row = make_row(0)
    row[field] = "nan"
    write_text(market_root, f"nan_{field}.csv", csv_text([row]))

    with pytest.raises(CSVValidationError, match=f"invalid market data at line 2"):
        load_market_csv(f"nan_{field}.csv")


def test_naive_csv_timestamp_is_rejected(market_root: Path) -> None:
    row = make_row(0)
    row["timestamp"] = "2024-01-01T00:00:00"
    write_text(market_root, "naive.csv", csv_text([row]))

    with pytest.raises(CSVValidationError, match="timezone-aware"):
        load_market_csv("naive.csv")


def test_non_numeric_price_is_rejected(market_root: Path) -> None:
    row = make_row(0)
    row["close"] = "not-a-number"
    write_text(market_root, "bad_number.csv", csv_text([row]))

    with pytest.raises(CSVValidationError, match="finite number"):
        load_market_csv("bad_number.csv")


def test_duplicate_timestamps_are_rejected(market_root: Path) -> None:
    rows = [make_row(0), make_row(1, timestamp=make_row(0)["timestamp"])]
    write_text(market_root, "duplicate_time.csv", csv_text(rows))

    with pytest.raises(CSVValidationError, match="duplicate timestamp"):
        load_market_csv("duplicate_time.csv")


def test_out_of_order_rows_are_rejected_not_sorted(market_root: Path) -> None:
    rows = [make_row(1), make_row(0)]
    write_text(market_root, "unordered.csv", csv_text(rows))

    with pytest.raises(CSVValidationError, match="strictly chronological"):
        load_market_csv("unordered.csv")


def test_mixed_symbols_are_rejected(market_root: Path) -> None:
    rows = [make_row(0), make_row(1, symbol="OTHER")]
    write_text(market_root, "mixed_symbols.csv", csv_text(rows))

    with pytest.raises(CSVValidationError, match="mixed symbols"):
        load_market_csv("mixed_symbols.csv")


def test_mixed_timeframes_are_rejected(market_root: Path) -> None:
    rows = [make_row(0), make_row(1, timeframe="1d")]
    write_text(market_root, "mixed_timeframes.csv", csv_text(rows))

    with pytest.raises(CSVValidationError, match="mixed timeframes"):
        load_market_csv("mixed_timeframes.csv")


def test_blank_line_is_rejected(market_root: Path) -> None:
    text = csv_text([make_row(0)], trailing_newline=False) + "\n\n"
    write_text(market_root, "blank_line.csv", text)

    with pytest.raises(CSVValidationError, match="blank line at line 3"):
        load_market_csv("blank_line.csv")


def test_unterminated_quote_is_rejected(market_root: Path) -> None:
    header = ",".join(COLUMNS)
    row = ",".join(str(make_row(0)[column]) for column in COLUMNS[:-1])
    write_text(market_root, "quote.csv", f'{header}\n{row},"unterminated\n')

    with pytest.raises(CSVValidationError, match="malformed CSV"):
        load_market_csv("quote.csv")


def test_invalid_utf8_is_rejected(market_root: Path) -> None:
    write_bytes(market_root, "binary.csv", b"\xff\xfe\x00\x00")

    with pytest.raises(CSVValidationError, match="not valid utf-8-sig"):
        load_market_csv("binary.csv")


def test_empty_file_is_rejected(market_root: Path) -> None:
    write_text(market_root, "empty.csv", "")

    with pytest.raises(CSVValidationError, match="empty"):
        load_market_csv("empty.csv")


def test_header_only_file_is_rejected(market_root: Path) -> None:
    write_text(market_root, "header_only.csv", ",".join(COLUMNS) + "\n")

    with pytest.raises(CSVValidationError, match="no data rows"):
        load_market_csv("header_only.csv")


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside.csv",
        "sub/../../outside.csv",
        "./../outside.csv",
    ],
)
def test_path_traversal_is_rejected(
    market_root: Path, tmp_path: Path, relative_path: str
) -> None:
    write_text(tmp_path, "outside.csv", _valid_text(1))

    with pytest.raises(PathSecurityError, match="traversal"):
        load_market_csv(relative_path)


def test_absolute_path_is_rejected(market_root: Path, tmp_path: Path) -> None:
    outside = write_text(tmp_path, "outside.csv", _valid_text(1))

    with pytest.raises(PathSecurityError, match="absolute paths"):
        load_market_csv(outside)


def test_market_root_directory_itself_is_rejected(market_root: Path) -> None:
    with pytest.raises(CSVValidationError, match="identify a file"):
        load_market_csv(".")


def test_empty_path_is_rejected(market_root: Path) -> None:
    with pytest.raises(CSVValidationError, match="must not be empty"):
        load_market_csv("")


def test_missing_file_is_rejected(market_root: Path) -> None:
    with pytest.raises(CSVValidationError, match="does not exist"):
        load_market_csv("missing.csv")


def test_directory_instead_of_file_is_rejected(market_root: Path) -> None:
    (market_root / "directory").mkdir()

    with pytest.raises(CSVValidationError, match="not a regular file"):
        load_market_csv("directory")


def test_missing_root_is_not_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "does_not_exist"
    monkeypatch.setattr(csv_loader, "MARKET_DATA_DIR", root)

    with pytest.raises(CSVValidationError, match="does not exist"):
        load_market_csv("sample.csv")

    assert not root.exists()


def test_file_size_limit_is_enforced(
    market_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_text(market_root, "large.csv", _valid_text(3))
    monkeypatch.setattr(csv_loader, "MAX_FILE_BYTES", 10)

    with pytest.raises(CSVValidationError, match="too large"):
        load_market_csv("large.csv")


def test_file_at_exact_size_limit_is_accepted(
    market_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_text(market_root, "exact.csv", _valid_text(2))
    monkeypatch.setattr(csv_loader, "MAX_FILE_BYTES", len(path.read_bytes()))

    loaded = load_market_csv("exact.csv")

    assert loaded.row_count == 2


def test_record_limit_is_enforced(
    market_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_text(market_root, "many.csv", _valid_text(3))
    monkeypatch.setattr(csv_loader, "MAX_RECORDS", 2)

    with pytest.raises(CSVValidationError, match="MAX_RECORDS=2"):
        load_market_csv("many.csv")


def test_record_count_at_limit_is_accepted(
    market_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_text(market_root, "exact_rows.csv", _valid_text(2))
    monkeypatch.setattr(csv_loader, "MAX_RECORDS", 2)

    loaded = load_market_csv("exact_rows.csv")

    assert loaded.row_count == 2


def test_default_limits_match_the_documented_policy() -> None:
    assert csv_loader.MAX_FILE_BYTES == 10 * 1024 * 1024
    assert csv_loader.MAX_RECORDS == 100_000
    assert csv_loader.MARKET_DATA_DIR.name == "market_samples"
    assert csv_loader.MARKET_DATA_DIR.parent.name == "data"


def test_loader_does_not_offer_writing_api() -> None:
    assert not hasattr(csv_loader, "save_market_csv")
    assert not hasattr(csv_loader, "download_market_csv")
