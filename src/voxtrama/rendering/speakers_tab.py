"""The Speakers tab of a concluded job.

One row per voice diarisation told apart, then one per speaker added by
hand (db.speaker_naming.add_speaker). Each row counts what the transcript
shows under that speaker's name: the turns moved to them in Explore count,
the turns moved away do not. So the numbers here and the chips there never
disagree, and neither does the colour, taken from the same rows.

`clips` are the first turns of that speaker, up to LISTEN_SECONDS, which
static/js/run_speakers.js plays one after the other on the job's own
player, and draws as a small waveform beside the button.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.speaker_name import ADDED_PREFIX
from voxtrama.db.models.transcript import Segment
from voxtrama.humanize import human_clock
from voxtrama.rendering.run_transcript import SPEAKER_COLOR_COUNT, TranscriptRowView

LISTEN_SECONDS = 60.0


@dataclass(frozen=True)
class SpeakerTabRow:
    """One speaker: the form field's label, the name it carries (empty when
    nobody named the voice yet), and what the transcript holds for them."""

    label: str
    added: bool
    name: str
    color: int
    turns: int
    time: str
    percent: int
    clips: tuple[tuple[float, float], ...]


def _clips(rows: list[TranscriptRowView]) -> tuple[tuple[float, float], ...]:
    clips, heard = [], 0.0
    for row in rows:
        if heard >= LISTEN_SECONDS:
            break
        end = min(row.end, row.start + LISTEN_SECONDS - heard)
        clips.append((row.start, end))
        heard += end - row.start
    return tuple(clips)


def _labels(segments: list[Segment]) -> list[str]:
    return list(dict.fromkeys(s.speaker_label for s in segments if s.speaker_label))


def _owns(segment: Segment, label: str, person_id: str | None) -> bool:
    """Whether `segment` is shown under this speaker: moved to them, or theirs and never moved."""
    if segment.person_id is not None:
        return segment.person_id == person_id
    return segment.speaker_label == label


def speaker_tab_rows(
    segments: list[Segment],
    rows: tuple[TranscriptRowView, ...],
    named: dict[str, tuple[str, str]],
) -> tuple[SpeakerTabRow, ...]:
    """Detected voices by how long they speak, then the added ones in order.

    `named` maps a label (a voice's, or an added speaker's "+n") to the
    person and the name it carries (db.speaker_naming.recording_speakers).
    `rows` are `segments` as the transcript shows them, in the same order.
    """
    pairs = list(zip(segments, rows, strict=True))
    total = sum(row.end - row.start for row in rows) or 1.0
    used = {row.speaker_color for row in rows}
    added = sorted((lb for lb in named if lb.startswith(ADDED_PREFIX)), key=lambda lb: int(lb[1:]))
    result = []
    for label in _labels(segments) + added:
        person_id, name = named.get(label, (None, ""))
        own = [row for segment, row in pairs if _owns(segment, label, person_id)]
        seconds = sum(row.end - row.start for row in own)
        color = own[0].speaker_color if own else (len(used) % SPEAKER_COLOR_COUNT) + 1
        result.append(
            SpeakerTabRow(
                label=label,
                added=label.startswith(ADDED_PREFIX),
                name=name,
                color=color,
                turns=len(own),
                time=human_clock(seconds),
                percent=round(100 * seconds / total),
                clips=_clips(own),
            )
        )
    by_time = sorted((r for r in result if not r.added), key=lambda r: r.percent, reverse=True)
    return tuple(by_time + [r for r in result if r.added])
