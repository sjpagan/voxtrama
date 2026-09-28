"""A concluded job's recap as a plain sequence of blocks, for export.

The Recap tab exports to PDF, HTML and DOCX. HTML is a
template (web/templates/exports/recap.html). The two binary formats are
written by rendering.recap_docx and rendering.recap_pdf from the blocks
below, so both say the same thing in the same order: the job's name, its
settings line, then every section with its points (each with its source)
and its provenance.

The words that are not data (section titles, «Needs review») arrive
already translated by the route's Translator.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.rendering.job_recap import RecapSection
from voxtrama.rendering.job_settings_line import SettingsLine


@dataclass(frozen=True)
class Block:
    """`kind` is one of: title, meta, heading, bullet, note."""

    kind: str
    text: str


def settings_text(line: SettingsLine, detail_word: str, cores_word: str) -> str:
    parts = [line.workflow]
    if line.transcription_model:
        parts.append(f"Whisper {line.transcription_model}")
    if line.summary_model:
        parts.append(line.summary_model)
    if line.summary_detail:
        parts.append(f"{detail_word} {line.summary_detail}/5")
    if line.cores:
        parts.append(f"{line.cores} {cores_word}")
    return " · ".join(parts)


def recap_blocks(
    title: str,
    meta: str,
    sections: tuple[RecapSection, ...],
    words: dict[str, str],
) -> list[Block]:
    """`words` maps each section kind, and "needs_review", to its translation."""
    blocks = [Block("title", title), Block("meta", meta)]
    for section in sections:
        blocks.append(Block("heading", words[section.kind]))
        for point in section.points:
            text = point.text
            if point.time:
                source = f"{point.speaker} · {point.time}" if point.speaker else point.time
                text = f"{text} ({source})"
            if point.needs_review:
                text = f"{text} [{words['needs_review']}]"
            blocks.append(Block("bullet", text))
        provenance = section.provenance
        parts = [provenance.workflow, provenance.skill, provenance.model or ""]
        blocks.append(Block("note", " · ".join(part for part in parts if part)))
    return blocks
