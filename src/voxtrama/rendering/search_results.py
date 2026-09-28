"""The navbar search's results page.

A simple page. Results are grouped by job (the job's name
highlighted, with workflow and date), and under it every occurrence in
that job: time, speaker, the sentence with the searched words marked.
Each occurrence links to the job's view at that line of the transcript
(`#vx-transcript-row-<segment id>`), and the job's name links to the job.

A presenter: groups and marks what the route already found, never a query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Segment
from voxtrama.humanize import human_clock
from voxtrama.i18n.formatting import format_date
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.run_produced import speaker_name


@dataclass(frozen=True)
class SearchHit:
    """One occurrence: where, who, and the sentence split into (text, is_match) parts."""

    time: str
    speaker: str | None
    parts: list[tuple[str, bool]]
    href: str


@dataclass
class SearchGroup:
    """One job and every occurrence found in it."""

    run_id: str
    name: str
    workflow: str
    date: str
    hits: list[SearchHit] = field(default_factory=list)


def marked(text: str, query: str) -> list[tuple[str, bool]]:
    """`text` split around every case-insensitive occurrence of `query`."""
    pieces = re.split(f"({re.escape(query)})", text, flags=re.IGNORECASE)
    return [(piece, piece.lower() == query.lower()) for piece in pieces if piece]


def search_groups(
    query: str,
    hits: list[tuple[Segment, Run]],
    title_matches: list[Run],
    names: dict[str, str],
    titles: dict[str, str],
    translator: Translator,
) -> list[SearchGroup]:
    """Group segment hits and title matches by job, newest job first."""
    groups: dict[str, SearchGroup] = {}
    runs = {run.id: run for _, run in hits} | {run.id: run for run in title_matches}
    for run in sorted(runs.values(), key=lambda run: run.created_at, reverse=True):
        groups[run.id] = SearchGroup(
            run_id=run.id,
            name=names.get(run.id, run.workflow_name),
            workflow=titles.get(run.workflow_name, run.workflow_name),
            date=format_date(translator, run.created_at),
        )
    for segment, run in hits:
        groups[run.id].hits.append(
            SearchHit(
                time=human_clock(segment.start),
                speaker=speaker_name(segment),
                parts=marked(segment.text, query),
                href=f"/runs/{run.id}/view#vx-transcript-row-{segment.id}",
            )
        )
    return list(groups.values())
