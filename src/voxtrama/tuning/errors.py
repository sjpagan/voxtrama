"""Errors raised when a tuning file fails to load or to resolve."""

from __future__ import annotations


class TuningError(Exception):
    """Base class for every error tuning file loading and selection can raise."""


class TuningValidationError(TuningError):
    """Raised when a tuning/*.yaml does not match the TuningFile schema."""


class TuningConflictError(TuningError):
    """Raised when two or more tuning files tie for the most specific match.

    Never resolved arbitrarily: a silent pick between two files that both
    match would tune two identical installations differently, with nobody
    able to say why.
    """


class TuningNotFoundError(TuningError):
    """Raised when no tuning file, not even a generic one, applies to this machine."""
