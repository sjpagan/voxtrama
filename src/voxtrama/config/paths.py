"""Filesystem paths derived from the configured data directory.

The layout is the project's fixed one, and the same one docker-entrypoint.sh
creates: recordings, runs, models, logs, and the database alongside them.

Nothing here is a hardcoded absolute constant: every path is built from
the data directory the caller supplies, which itself comes from
VOXTRAMA_DATA_DIR (see config.settings) or from the per-OS default below.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    """Return the per-OS default location for Voxtrama's data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "voxtrama"
    if sys.platform.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "voxtrama"
    return Path.home() / ".local" / "share" / "voxtrama"


# The guided setup's output file (setup.installation) lives at this
# fixed name inside the data directory. The name belongs here, not in
# setup.installation, because config.settings now has to locate the same
# file. settings.py cannot import from voxtrama.setup without creating an
# import cycle (setup.generative_step already imports config.settings), so
# the one piece both sides need sits in config, the layer below both
# (tests/_architecture.py). setup.installation keeps re-exporting the old
# names for its call sites and tests.
INSTALLATION_CONFIG_FILENAME = "voxtrama.toml"
# The machine's proposal, in force until the first job writes
# voxtrama.toml with the values it used.
PROPOSAL_FILENAME = "proposal.toml"


def installation_config_path(data_dir: Path) -> Path:
    """Where the guided setup reads and writes its outcome, inside the data directory."""
    return data_dir / INSTALLATION_CONFIG_FILENAME


def proposal_path(data_dir: Path) -> Path:
    """Where the machine's proposal waits for the first job."""
    return data_dir / PROPOSAL_FILENAME


@dataclass(frozen=True)
class Paths:
    """The set of filesystem locations Voxtrama reads from and writes to."""

    data_dir: Path
    recordings_dir: Path
    runs_dir: Path
    models_dir: Path
    logs_dir: Path
    db_path: Path


def get_paths(data_dir: Path) -> Paths:
    """Derive the standard Voxtrama paths from the given data directory."""
    return Paths(
        data_dir=data_dir,
        recordings_dir=data_dir / "recordings",
        runs_dir=data_dir / "runs",
        models_dir=data_dir / "models",
        logs_dir=data_dir / "logs",
        db_path=data_dir / "voxtrama.db",
    )
