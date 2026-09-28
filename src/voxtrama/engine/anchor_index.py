"""A normalized index over a Transcript's segments.

Built once per step's anchoring pass, from the Transcript in context: where
a stretch of text is inside the concatenated, normalized transcript, and
which segment interval covers a given time range. engine.anchoring is the
only caller. Kept apart because it is a data structure with two queries,
not a decision about extractive versus generative skills.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.transcript import Transcript


def normalize(text: str) -> str:
    """casefold() plus collapsed whitespace, nothing more.

    Punctuation is left as it is. A looser match (dropping punctuation,
    say) would anchor a quote the model paraphrased instead of one it took
    from the transcript: invented evidence that happens to pass the check.
    """
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class _SegmentSpan:
    """One segment's time interval, and the slice of the index text it owns.

    text_end includes the single-space separator that follows the
    segment's own words: the separator belongs to the segment that
    precedes it, not to the one after, so every offset in the index text
    maps to exactly one segment.
    """

    start: float
    end: float
    text_start: int
    text_end: int


def build_index(transcript: Transcript) -> AnchorIndex:
    """Concatenate `transcript.segments`, normalized, into one indexed text.

    Segments are ordered by start before concatenation, so the resulting
    text reads in playback order regardless of how the database returned
    them, and so that find_interval's "first" and "last" covering segment
    are first and last in time, not in row order.
    """
    segments = sorted(transcript.segments, key=lambda segment: segment.start)
    spans: list[_SegmentSpan] = []
    pieces: list[str] = []
    offset = 0
    for segment in segments:
        piece = normalize(segment.text) + " "
        spans.append(_SegmentSpan(segment.start, segment.end, offset, offset + len(piece)))
        pieces.append(piece)
        offset += len(piece)
    text = "".join(pieces)[:-1] if pieces else ""
    return AnchorIndex(text=text, spans=spans)


@dataclass(frozen=True)
class AnchorIndex:
    """Answers the two questions engine.anchoring needs of a Transcript.

    find_interval and covers share the same normalization and the same
    notion of "which segments does this offset range belong to" (see
    _interval_for, which both build on).
    """

    text: str
    spans: list[_SegmentSpan]

    def find_interval(self, quote: str) -> tuple[float, float] | None:
        """Where `quote` sits in the transcript, or None if absent or ambiguous.

        GENERATIVE skills use this: a generative
        model's declared interval is never trusted, so the engine locates the quote itself.
        A quote occurring more than once is not anchored: picking the first
        of several occurrences would be an arbitrary, plausible-looking
        guess, the kind of invented evidence this file keeps out.
        """
        needle = normalize(quote)
        if not needle:
            return None
        positions = _find_all(self.text, needle)
        if len(positions) != 1:
            return None
        return self._interval_for(positions[0], positions[0] + len(needle))

    def covers(self, start: float, end: float, quote: str) -> bool:
        """Whether segments intersecting [start, end) contain `quote`.

        EXTRACTIVE skills use this to verify their declared interval, never
        to search for the quote elsewhere: a skill that names the wrong
        interval has not done its job, and searching would hide that.
        """
        needle = normalize(quote)
        if not needle:
            return False
        intersecting = [span for span in self.spans if span.start < end and span.end > start]
        if not intersecting:
            return False
        window = self.text[intersecting[0].text_start : intersecting[-1].text_end]
        return needle in window

    def _interval_for(self, offset_start: int, offset_end: int) -> tuple[float, float] | None:
        covering = [
            span
            for span in self.spans
            if span.text_start < offset_end and span.text_end > offset_start
        ]
        if not covering:
            return None
        return covering[0].start, covering[-1].end


def _find_all(text: str, needle: str) -> list[int]:
    """Every offset at which `needle` occurs in `text`, without overlap-skipping tricks."""
    positions = []
    start = 0
    while (found := text.find(needle, start)) != -1:
        positions.append(found)
        start = found + 1
    return positions
