"""Exceptions raised by Queue implementations."""

from __future__ import annotations


class QueueError(Exception):
    """Base class for every error a Queue implementation can raise."""


class JobNotFound(QueueError):
    """Raised when a job id has no matching job in the queue."""


class QueueUnavailable(QueueError):
    """Raised when the queue backend cannot be reached."""


class JobTimeoutError(QueueError):
    """Raised when a job is stopped for exceeding its granted timeout."""
