"""The `voxtrama demo` command: the whole chain, on audio nobody had to find.

There are three walls before a first result, and this removes the
one that sends people away: "now go and get an audio file". The demo runs
the shipped fixture through the shipped workflow, so the first
question a newcomer answers is "is this useful to me?" rather than "what
do I feed it?".

It is deliberately a thin wrapper over `run`: same import, same
announcement, same progress. A demo that took a different path through
the code would prove something the product does not do.
"""

from __future__ import annotations

import typer

from voxtrama.cli.commands.run import run_command
from voxtrama.demo import DEMO_WORKFLOW, DemoAudioMissing, find_demo_audio


def demo_command() -> None:
    """Run the bundled sample recording through the bundled workflow."""
    try:
        audio_path = find_demo_audio()
    except DemoAudioMissing as exc:
        typer.echo(f"Demo audio missing: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"Running the '{DEMO_WORKFLOW}' workflow on the bundled sample "
        f"({audio_path.name}): two speakers, about thirteen seconds."
    )
    run_command(DEMO_WORKFLOW, str(audio_path))
