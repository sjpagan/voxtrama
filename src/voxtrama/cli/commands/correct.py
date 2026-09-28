"""The `voxtrama correct` command: fix a Recording's source title or URL after the fact.

Only recordings imported before the URL import was removed carry
them; the fields stay readable and correctable
without rerunning anything. This only writes the database row. See
db.recordings.correct_source for why a manifest already on disk is
never touched.
"""

from __future__ import annotations

from typing import Annotated

import typer

from voxtrama.db.recordings import RecordingNotFoundError, correct_source
from voxtrama.db.session import build_session_factory, session_scope


def correct_command(
    recording_id: Annotated[str, typer.Argument(help="Id of the recording to correct.")],
    label: Annotated[
        str | None,
        typer.Option("--label", help="Corrected source_title (e.g. the recording's title)."),
    ] = None,
    url: Annotated[str | None, typer.Option("--url", help="Corrected source_url.")] = None,
) -> None:
    """Correct a Recording's source_title and/or source_url.

    Later runs see the correction. Manifests already written for runs on
    this recording do not (see db.recordings.correct_source).
    """
    if label is None and url is None:
        typer.echo("Nothing to correct: pass --label and/or --url.", err=True)
        raise typer.Exit(code=1)

    with session_scope(build_session_factory()) as session:
        try:
            recording = correct_source(session, recording_id, source_title=label, source_url=url)
        except RecordingNotFoundError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(
            f"recording {recording.id}: "
            f"source_title={recording.source_title!r} source_url={recording.source_url!r}"
        )
