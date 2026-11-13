"""Exception hierarchy for the deterministic quantitative-research package."""

from __future__ import annotations


class QResearchError(Exception):
    """Base class for every qresearch-specific error."""


class MarketDataError(QResearchError):
    """A market observation or series violates the data contract."""


class CSVValidationError(MarketDataError):
    """A CSV file is not a valid market-data file."""


class PathSecurityError(CSVValidationError):
    """A path would escape the dedicated market-data directory."""


class CalculationError(QResearchError):
    """A calculation request is invalid or cannot be completed."""
