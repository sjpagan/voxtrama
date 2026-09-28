"""Errors raised while importing an audio file into Voxtrama."""

from __future__ import annotations


class UnsupportedMediaError(Exception):
    """Raised when ffprobe or ffmpeg cannot make sense of the given file.

    Covers "no audio stream at all" (ingest.probe) and "ffmpeg could not
    resample it" (ingest.resample) alike: both fail the same way to
    a caller that only asked for a Recording.
    """
