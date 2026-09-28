"""Where the demo's audio lives, so `voxtrama demo` needs nothing from anyone.

A first run should hit no walls, and the last of them is "now go
find an audio file", the point where most people close the tab. The demo
uses the fixture the repository already ships for its tests, so it
adds no extra weight.

Finding it is the awkward part. Installed in the image the package lives
in site-packages, far from the repository tree, so the image copies the
fixture to a known path. Run from a clone, the file is still in tests/.
Both are checked, and if neither is there the failure names what is
missing instead of raising FileNotFoundError from somewhere deeper.
"""

from __future__ import annotations

from pathlib import Path

# Where the Dockerfile puts the fixture. Outside /app/src, because
# the image installs the package and does not run from the source tree.
IMAGE_DEMO_AUDIO = Path("/app/demo/public-fixture.wav")

# Where it lives in a clone, relative to the repository root.
REPO_DEMO_AUDIO = Path("tests/fixtures/public-fixture.wav")

DEMO_WORKFLOW = "transcribe-only"


class DemoAudioMissing(RuntimeError):
    """Raised when the demo fixture cannot be found in any known location."""


def candidate_paths(start: Path | None = None) -> list[Path]:
    """Every place the demo audio might be, most specific first."""
    here = (start or Path.cwd()).resolve()
    candidates = [IMAGE_DEMO_AUDIO]
    candidates.extend(parent / REPO_DEMO_AUDIO for parent in [here, *here.parents])
    return candidates


def find_demo_audio(start: Path | None = None) -> Path:
    """Return the demo fixture, or say where it was looked for and not found."""
    for candidate in candidate_paths(start):
        if candidate.is_file():
            return candidate
    raise DemoAudioMissing(
        f"the demo audio was not found at {IMAGE_DEMO_AUDIO}, nor as "
        f"{REPO_DEMO_AUDIO} in this directory or any parent of it"
    )
