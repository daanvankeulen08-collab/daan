"""Exception hierarchy for the Mathematical Discovery Lab."""

from __future__ import annotations


class MdlError(Exception):
    """Base class for every project-specific error."""


class ConfigError(MdlError):
    """Invalid or missing configuration."""


class ModelError(MdlError):
    """The local model could not be reached or returned an unusable response."""


class ModelTimeoutError(ModelError):
    """The model did not answer within the configured timeout."""


class ModelOutputError(ModelError):
    """The model response was not valid JSON or failed schema validation."""


class ToolError(MdlError):
    """Base class for tool orchestration errors."""


class ToolValidationError(ToolError):
    """A tool request was rejected before execution."""


class ToolExecutionError(ToolError):
    """A tool failed while executing in the isolated worker."""


class ToolTimeoutError(ToolError):
    """A tool exceeded its execution budget and was terminated."""


class VerificationError(MdlError):
    """The verification layer could not produce a trustworthy verdict."""


class ContextError(MdlError):
    """The research context could not be encoded or reconstructed."""


class LogIntegrityError(MdlError):
    """The append-only research log failed its integrity check."""
