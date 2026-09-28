"""The shape of a readiness check: what it says, not how it decided.

Split out from readiness.py to stay under the project's file-length limit,
the same reason engine.progress_state is split from engine.progress_file:
one file for the data three separate checks and their aggregate report
move, none of it for the reasoning behind any single verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Readiness(StrEnum):
    """The three verdicts a status card can show, and never a fourth."""

    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LocalProcessingCheck:
    """Whether the configured hardware profile resolves to something the engine can run."""

    state: Readiness
    reason: str
    hardware_profile: str


@dataclass(frozen=True)
class ModelsReadyCheck:
    """Whether the ASR weights the configured profile needs are already on disk.

    `model` names the model_size the profile requires (e.g. "medium"),
    populated whenever the profile is recognised, including when the
    state is NOT_READY, so a reader can say which model is missing and
    not only that something is.
    """

    state: Readiness
    reason: str
    model: str | None


@dataclass(frozen=True)
class PrivateStorageCheck:
    """Whether the data directory exists, accepts a write, and has room to spare."""

    state: Readiness
    reason: str
    free_disk_bytes: int | None


@dataclass(frozen=True)
class SchemaCheck:
    """Whether the database schema is as new as the code that queries it.

    Lives here with the other three and not with the code that reads it:
    reading the schema means touching the database, which is an adapter's
    job, while the upload gate that consumes this verdict is
    core. Only the shape crosses that line. `db.schema_check.check_schema`
    fills it in.
    """

    state: Readiness
    reason: str


@dataclass(frozen=True)
class ReadinessReport:
    """The three states components/status_cards.html declares outright."""

    local_processing: LocalProcessingCheck
    models_ready: ModelsReadyCheck
    private_storage: PrivateStorageCheck
