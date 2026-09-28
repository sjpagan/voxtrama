"""`.env.example` is a tested file, not documentation.

Its promise is that it can be copied unchanged and everything still
works, and that promise decays silently the first time a variable is
added, renamed or given a different default. These tests are what stops
the decay being discovered by whoever is trying Voxtrama for the first
time.
"""

from __future__ import annotations

import re
from pathlib import Path

from voxtrama.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

ASSIGNMENT = re.compile(r"^(?P<name>[A-Z0-9_]+)=", re.MULTILINE)

# Variables that are real but belong to something other than Settings:
# the build reads the first, the container entrypoint the other two.
# They are documented here on purpose.
NON_SETTINGS_VARIABLES = {
    "VOXTRAMA_EXTRAS",
    "VOXTRAMA_RUN_AS_UID",
    "VOXTRAMA_RUN_AS_GID",
    # Documented here, but nothing reads it yet: it is
    # left to be mounted by hand. Listed so this test says "known
    # and not wired" rather than going quiet about it.
    "VOXTRAMA_EXTRA_ROOTS",
    # Read by compose.yaml's port mapping, not by the application.
    # Deliberately not VOXTRAMA_PORT: that name is Settings.port, an
    # unused field that would collide in meaning the day something binds
    # to it: the host's published port and the container's internal one
    # are not the same value once VOXTRAMA_HOST_PORT overrides the former.
    "VOXTRAMA_HOST_PORT",
}


def env_example_text() -> str:
    return ENV_EXAMPLE.read_text(encoding="utf-8")


def test_copying_it_unchanged_sets_nothing() -> None:
    """Every line is a comment: copied as-is it imposes no decision at all.

    This is the configuration's whole principle in one assertion: "zero
    decisions before the first success". An uncommented assignment here
    would be a value someone has to understand before they can start.
    """
    active = [
        line
        for line in env_example_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert active == [], f"uncommented assignments in .env.example: {active}"


def test_every_variable_it_mentions_is_one_we_read() -> None:
    """A documented variable nobody reads is a promise that does nothing."""
    mentioned = {
        match.group("name") for match in ASSIGNMENT.finditer(env_example_text().replace("# ", ""))
    }
    fields = {f"VOXTRAMA_{field.upper()}" for field in Settings.model_fields}
    known = fields | NON_SETTINGS_VARIABLES

    assert mentioned <= known, f"unknown variables documented: {sorted(mentioned - known)}"


def test_the_variables_that_decide_the_first_run_are_documented() -> None:
    """The three walls the configuration removes: data, profile, and who writes."""
    text = env_example_text()

    for variable in ("VOXTRAMA_DATA_DIR", "VOXTRAMA_HARDWARE_PROFILE", "VOXTRAMA_RUN_AS_UID"):
        assert variable in text, f"{variable} is not documented in .env.example"
