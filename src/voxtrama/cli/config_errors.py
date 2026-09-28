"""Configuration problems, said in one line that tells you what to do.

Every missing or malformed variable produces one line saying what is
missing and how to fix it, not a pydantic traceback. This is the
part of a product that gets postponed and then paid for in support
threads. An error that explains itself is a report nobody has to open.

It lives in the CLI because it formats for a reader, which the core
must not do.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.config.settings import Settings, SettingsError


def explain(exc: SettingsError) -> str:
    """One readable line for a settings error, plus where to fix it."""
    return f"{exc}\nSet it in .env, or export it in the environment before running."


def data_dir_problem(settings: Settings) -> str | None:
    """Why the data directory cannot be used, or None when it can.

    Checked before a command does anything expensive: the alternative is
    failing later, inside an import or a worker, with an OSError that
    names a path but not the variable that chose it.
    """
    data_dir = settings.data_dir
    if not data_dir.exists():
        return (
            f"VOXTRAMA_DATA_DIR points at {data_dir}, which does not exist.\n"
            "Create it, or change the variable in .env."
        )
    if not data_dir.is_dir():
        return (
            f"VOXTRAMA_DATA_DIR points at {data_dir}, which is a file, not a directory.\n"
            "Change the variable in .env to a directory."
        )
    if not _is_writable(data_dir):
        return (
            f"VOXTRAMA_DATA_DIR points at {data_dir}, which this process cannot write to.\n"
            "Run `voxtrama doctor` to see which identity does not match, and how to fix it."
        )
    return None


def _is_writable(directory: Path) -> bool:
    """Whether a file can be created here: tried, not inferred."""
    probe = directory / ".voxtrama-write-check"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        return False
    return True
