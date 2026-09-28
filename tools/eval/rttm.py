"""Read and write RTTM, the standard format for diarization reference labels.

One line per speaker turn:

    SPEAKER <file-id> 1 <start> <dur> <NA> <NA> <speaker> <NA> <NA>

The bench never invents this format: it consumes RTTM produced by the
fixture generator and writes it back only for backend output
that a human wants to inspect with an RTTM-aware tool.
"""

from __future__ import annotations

from pathlib import Path

from backends.base import Segment

FIELD_COUNT = 10
TYPE_FIELD = "SPEAKER"
CHANNEL_FIELD = "1"
NA_FIELD = "<NA>"


def read_rttm(path: Path) -> list[Segment]:
    """Parse `path` into segments, ignoring blank lines and comments."""
    segments = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        fields = stripped.split()
        if len(fields) < FIELD_COUNT or fields[0] != TYPE_FIELD:
            raise ValueError(f"{path}: not a SPEAKER line: {line!r}")
        start = float(fields[3])
        duration = float(fields[4])
        speaker = fields[7]
        segments.append(Segment(start=start, end=start + duration, speaker=speaker))
    return segments


def write_rttm(path: Path, file_id: str, segments: list[Segment]) -> None:
    """Write `segments` as RTTM, sorted by start time (RTTM has no ordering rule,
    but a sorted file is easier for a human to check by eye).
    """
    lines = [
        " ".join(
            [
                TYPE_FIELD,
                file_id,
                CHANNEL_FIELD,
                f"{segment.start:.3f}",
                f"{segment.end - segment.start:.3f}",
                NA_FIELD,
                NA_FIELD,
                segment.speaker,
                NA_FIELD,
                NA_FIELD,
            ]
        )
        for segment in sorted(segments, key=lambda s: s.start)
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
