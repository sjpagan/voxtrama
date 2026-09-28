"""A job's transcript as files, whole and in parts.

A job's page ends with every file the job produced, to take
away: the full transcript, and the call cut into pieces small enough to
work on one at a time. This is the text half: the rows
the Explore tab shows (rendering.run_transcript, speaker names included)
written as plain text, Markdown or JSON, and grouped into parts of about
ten minutes. A part always closes on a sentence boundary, so no sentence
is split between two files; its audio (ingest.audio_cut) is cut on the
same boundaries.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from voxtrama.humanize import human_clock
from voxtrama.rendering.run_transcript import TranscriptRowView

PART_SECONDS = 600


@dataclass(frozen=True)
class Part:
    """About ten minutes of the job: its sentences, and the audio span they cover.

    `audio_start` of the first part is 0 and `audio_end` of the last is
    None (the end of the file), so the parts' audio together is the whole
    recording, silence at either end included.
    """

    number: int
    rows: tuple[TranscriptRowView, ...]
    audio_start: float
    audio_end: float | None

    @property
    def stem(self) -> str:
        return f"part-{self.number:02d}-{human_clock(self.audio_start).replace(':', 'm')}s"


def parts_of(rows: Sequence[TranscriptRowView], seconds: float = PART_SECONDS) -> list[Part]:
    """`rows` grouped so that each part starts at the first sentence past a ten-minute mark."""
    groups: list[list[TranscriptRowView]] = []
    limit = seconds
    for row in rows:
        if groups and row.start >= limit:
            groups.append([])
            while row.start >= limit:
                limit += seconds
        elif not groups:
            groups.append([])
        groups[-1].append(row)
    parts = []
    for index, group in enumerate(groups):
        start = 0.0 if index == 0 else group[0].start
        end = groups[index + 1][0].start if index + 1 < len(groups) else None
        parts.append(Part(index + 1, tuple(group), start, end))
    return parts


def _who(row: TranscriptRowView) -> str:
    return f"{row.speaker}: " if row.speaker else ""


def as_text(rows: Sequence[TranscriptRowView]) -> str:
    """One line per sentence: `[12:04] Anna: text`."""
    return "".join(f"[{row.time}] {_who(row)}{row.text}\n" for row in rows)


def as_markdown(title: str, rows: Sequence[TranscriptRowView]) -> str:
    """A heading, then one paragraph per sentence with its time and speaker in bold."""
    lines = [f"# {title}\n"]
    for row in rows:
        who = f" · {row.speaker}" if row.speaker else ""
        lines.append(f"**{row.time}{who}** {row.text}\n")
    return "\n".join(lines)


def as_json(title: str, rows: Sequence[TranscriptRowView]) -> str:
    """Every sentence with its start and end in seconds, for another program to read."""
    segments = [
        {"start": row.start, "end": row.end, "speaker": row.speaker, "text": row.text}
        for row in rows
    ]
    return json.dumps({"title": title, "segments": segments}, indent=2, ensure_ascii=False)


def as_jsonl(rows: Sequence[TranscriptRowView]) -> str:
    """One JSON object per line and sentence, as segments.jsonl."""
    return "".join(
        json.dumps(
            {"start": r.start, "end": r.end, "speaker": r.speaker, "text": r.text},
            ensure_ascii=False,
        )
        + "\n"
        for r in rows
    )
