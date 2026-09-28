"""Voxtrama: local-first audio intelligence workflows."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("voxtrama")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
