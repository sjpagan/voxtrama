"""Whether a first visit goes to the guided setup.

On a new installation the home page sent nobody to the guided setup: it
opened on the new-job form with the machine's proposal, and the setup was
reachable only from Settings. Now, until the setup is finished
(voxtrama.toml exists) or skipped once, the home page redirects to its
first step. Skipping leaves a marker in the data folder, so the proposal
stays in force and voxtrama.toml is still born from the first job
(setup.first_run), as before.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.config.paths import installation_config_path

SKIPPED_MARKER = "setup-skipped"
FIRST_STEP_PATH = "/setup/local-processing"


def skipped_marker_path(data_dir: Path) -> Path:
    return data_dir / SKIPPED_MARKER


def setup_pending(data_dir: Path) -> bool:
    """True while the guided setup has been neither finished nor skipped."""
    if installation_config_path(data_dir).is_file():
        return False
    return not skipped_marker_path(data_dir).is_file()


def skip_setup(data_dir: Path) -> None:
    """Remember that the person chose the proposal over the guided setup."""
    data_dir.mkdir(parents=True, exist_ok=True)
    skipped_marker_path(data_dir).write_text(
        "The guided setup was skipped: the machine's proposal is in force.\n",
        encoding="utf-8",
    )
