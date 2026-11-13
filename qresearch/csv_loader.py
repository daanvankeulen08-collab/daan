"""Strict, read-only CSV importer for the dedicated market-sample directory.

Security policy:
* the input path is interpreted relative to ``data/market_samples/``;
* absolute paths, drive-relative paths and any ``..`` component are rejected;
* the resolved path must remain inside the resolved market-data root;
* file size and record count are bounded before/while reading.

The loader never sorts, deduplicates, fills gaps or writes a data file.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from qresearch.errors import CSVValidationError, MarketDataError, PathSecurityError
from qresearch.models import MarketBar, MarketSeries

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKET_DATA_DIR = PROJECT_ROOT / "data" / "market_samples"
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 100_000
REQUIRED_COLUMNS = (
    "timestamp",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
ENCODING = "utf-8-sig"


def _iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CSVLoadResult:
    """Loaded series plus reproducibility and reporting metadata."""

    series: MarketSeries
    content_sha256: str
    row_count: int
    file_size_bytes: int
    source_path: str
    symbol: str
    timeframe: str
    first_timestamp: datetime
    last_timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "row_count": self.row_count,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "first_timestamp": _iso_utc(self.first_timestamp),
            "last_timestamp": _iso_utc(self.last_timestamp),
            "content_sha256": self.content_sha256,
            "file_size_bytes": self.file_size_bytes,
        }


def _resolve_market_path(relative_path: str | Path) -> tuple[Path, str]:
    raw = str(relative_path)
    if not raw:
        raise CSVValidationError("market CSV path must not be empty")
    if raw != raw.strip():
        raise CSVValidationError(
            f"market CSV path must not contain leading or trailing whitespace: {raw!r}"
        )

    candidate_input = Path(raw)
    if candidate_input.is_absolute() or candidate_input.drive or candidate_input.anchor:
        raise PathSecurityError(
            f"absolute paths are not allowed; use a path relative to {MARKET_DATA_DIR}"
        )
    if any(part == ".." for part in candidate_input.parts):
        raise PathSecurityError(
            f"path traversal is not allowed; use a path inside {MARKET_DATA_DIR}"
        )

    root = MARKET_DATA_DIR.resolve()
    candidate = (root / candidate_input).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathSecurityError(
            f"path resolves outside the dedicated market-data directory: {raw!r}"
        ) from exc
    if candidate == root:
        raise CSVValidationError("market CSV path must identify a file, not the directory")

    return candidate, candidate_input.as_posix()


def load_market_csv(relative_path: str | Path) -> CSVLoadResult:
    """Load one CSV file from ``data/market_samples/`` with strict validation."""

    path, source_path = _resolve_market_path(relative_path)
    if not path.exists():
        raise CSVValidationError(f"market CSV file does not exist: {source_path!r}")
    if not path.is_file():
        raise CSVValidationError(f"market CSV path is not a regular file: {source_path!r}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_BYTES:
        raise CSVValidationError(
            f"market CSV file is too large: {file_size} bytes exceeds "
            f"MAX_FILE_BYTES={MAX_FILE_BYTES}"
        )

    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise CSVValidationError(
            f"market CSV file is too large: {len(data)} bytes exceeds "
            f"MAX_FILE_BYTES={MAX_FILE_BYTES}"
        )
    digest = hashlib.sha256(data).hexdigest()

    try:
        text = data.decode(ENCODING)
    except UnicodeDecodeError as exc:
        raise CSVValidationError(
            f"market CSV file is not valid {ENCODING}: {source_path!r}"
        ) from exc
    if not text.strip():
        raise CSVValidationError(f"market CSV file is empty: {source_path!r}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise CSVValidationError(
                f"blank line at line {line_number} in market CSV: {source_path!r}"
            )

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    fieldnames = reader.fieldnames
    if fieldnames is None:
        raise CSVValidationError(f"market CSV file has no header: {source_path!r}")
    if len(fieldnames) != len(set(fieldnames)):
        raise CSVValidationError(
            f"market CSV header contains duplicate column names: {fieldnames!r}"
        )
    expected = set(REQUIRED_COLUMNS)
    actual = set(fieldnames)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise CSVValidationError(
            "market CSV header must contain exactly the required columns; "
            f"missing={missing}, extra={extra}, got={fieldnames!r}"
        )

    bars: list[MarketBar] = []
    try:
        for row in reader:
            line_number = reader.line_num
            if None in row:
                raise CSVValidationError(
                    f"malformed CSV row at line {line_number}: too many fields"
                )
            if set(row) != expected:
                raise CSVValidationError(
                    f"malformed CSV row at line {line_number}: unexpected fields"
                )

            values: dict[str, str] = {}
            for column in REQUIRED_COLUMNS:
                raw = row.get(column)
                if raw is None:
                    raise CSVValidationError(
                        f"missing value for column {column!r} at line {line_number}"
                    )
                if raw != raw.strip():
                    raise CSVValidationError(
                        f"value for column {column!r} at line {line_number} contains "
                        "leading or trailing whitespace"
                    )
                if not raw:
                    raise CSVValidationError(
                        f"empty value for column {column!r} at line {line_number}"
                    )
                values[column] = raw

            try:
                bar = MarketBar(
                    timestamp=values["timestamp"],
                    symbol=values["symbol"],
                    timeframe=values["timeframe"],
                    open=values["open"],
                    high=values["high"],
                    low=values["low"],
                    close=values["close"],
                    volume=values["volume"],
                )
            except MarketDataError as exc:
                raise CSVValidationError(
                    f"invalid market data at line {line_number}: {exc}"
                ) from exc

            bars.append(bar)
            if len(bars) > MAX_RECORDS:
                raise CSVValidationError(
                    f"market CSV contains more than MAX_RECORDS={MAX_RECORDS} records"
                )
    except csv.Error as exc:
        raise CSVValidationError(
            f"malformed CSV at line {reader.line_num}: {exc}"
        ) from exc

    if not bars:
        raise CSVValidationError(f"market CSV contains no data rows: {source_path!r}")

    try:
        series = MarketSeries(tuple(bars))
    except MarketDataError as exc:
        raise CSVValidationError(f"CSV series validation failed: {exc}") from exc

    return CSVLoadResult(
        series=series,
        content_sha256=digest,
        row_count=len(bars),
        file_size_bytes=len(data),
        source_path=source_path,
        symbol=series.symbol,
        timeframe=series.timeframe,
        first_timestamp=series.first_timestamp,
        last_timestamp=series.last_timestamp,
    )


__all__ = [
    "CSVLoadResult",
    "ENCODING",
    "MARKET_DATA_DIR",
    "MAX_FILE_BYTES",
    "MAX_RECORDS",
    "REQUIRED_COLUMNS",
    "load_market_csv",
]
