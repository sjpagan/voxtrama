"""Downloading model weights while saying how much is left.

faster-whisper fetches its own weights, and it does so with Hugging Face's
progress bars explicitly disabled (`tqdm_class=disabled_tqdm` in
`faster_whisper.utils.download_model`). That is why the first run is silent
for minutes. The same is true of speechbrain.

So the download happens here instead, before the library is asked to load
anything: same repository, same revision, same file patterns, into the same
cache the library will then look in. It finds the files already there and
fetches nothing. What changes is that this one reports bytes while it works.

Sizes below are nominal, and used only to say "this will download about X"
before the transfer starts. Actual bytes come from the transfer itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voxtrama.weights.reporting import ProgressCallback, reporting_tqdm

ECAPA_REPO = "speechbrain/spkrec-ecapa-voxceleb"

# The library's own name for ecapa_weights(): not a hardware
# profile, so a caller that also accepts one (worker.tasks,
# api.routes.models) tells the two apart against this constant.
ECAPA_KEY = "ecapa"

# What faster_whisper.utils.download_model asks for. Kept in step with it
# rather than guessed: fetching a different set would leave the library to
# download the remainder, silently, which is the problem this module exists
# to remove.
_WHISPER_PATTERNS = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]

_ECAPA_PATTERNS = ["*.yaml", "*.ckpt", "*.txt"]

# Nominal download sizes, in bytes. Approximate by nature: they exist to
# print "about 460 MB" before the first byte moves, not to be arithmetic.
_NOMINAL_SIZES = {
    "small": 484 * 1024 * 1024,
    "medium": 1_530 * 1024 * 1024,
    "large-v3": 3_090 * 1024 * 1024,
    ECAPA_REPO: 83 * 1024 * 1024,
}


@dataclass(frozen=True)
class WeightSet:
    """One set of weights a run may need, and where it comes from."""

    label: str
    repo_id: str
    revision: str | None
    patterns: list[str]
    nominal_bytes: int
    # A model shown to whoever reads it must say under what licence. Not a
    # constant chosen once for every model here, since ecapa_weights() below
    # is not the same licence as whisper_weights().
    licence: str
    page_url: str


def whisper_weights(model_size: str, revision: str) -> WeightSet:
    """The weight set faster-whisper will load for `model_size`."""
    from faster_whisper.utils import _MODELS

    repo_id = _MODELS.get(model_size)
    if repo_id is None:
        raise ValueError(f"unknown whisper model size: {model_size!r}")
    return WeightSet(
        label=f"ASR model {model_size}",
        repo_id=repo_id,
        revision=revision,
        patterns=list(_WHISPER_PATTERNS),
        nominal_bytes=_NOMINAL_SIZES.get(model_size, 0),
        licence="MIT",
        page_url=f"https://huggingface.co/{repo_id}",
    )


def ecapa_weights() -> WeightSet:
    """The speaker-embedding weights chosen for diarisation."""
    return WeightSet(
        label="speaker model ECAPA-TDNN",
        repo_id=ECAPA_REPO,
        # Pinned for security: speechbrain builds objects from hyperparams.yaml.
        revision="0f99f2d0ebe89ac095bcc5903c4dd8f72b367286",
        patterns=list(_ECAPA_PATTERNS),
        nominal_bytes=_NOMINAL_SIZES[ECAPA_REPO],
        # SpeechBrain, not OpenAI Whisper: Apache 2.0, not MIT.
        licence="Apache-2.0",
        page_url=f"https://huggingface.co/{ECAPA_REPO}",
    )


def is_cached(weights: WeightSet, models_dir: Path) -> bool:
    """Whether `weights` are already on disk, so nothing will be downloaded.

    Asked before a run starts, to keep the announcement honest: warning about
    a download that will not happen trains people to ignore the warning.
    """
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import HFValidationError, LocalEntryNotFoundError

    try:
        snapshot_download(
            weights.repo_id,
            revision=weights.revision,
            cache_dir=str(models_dir),
            allow_patterns=weights.patterns,
            local_files_only=True,
        )
    except (LocalEntryNotFoundError, HFValidationError, OSError, ValueError):
        return False
    return True


def fetch_weights(
    weights: WeightSet, models_dir: Path, on_progress: ProgressCallback | None = None
) -> str:
    """Download `weights` into `models_dir`, reporting bytes as they arrive.

    Returns the local path, which is also where the library that needs these
    weights will find them.
    """
    from huggingface_hub import snapshot_download

    # The nominal size stands in until Hugging Face knows the real one: the
    # announcement before the run already quoted it, so the two figures agree.
    tqdm_class = (
        reporting_tqdm(on_progress, fallback_total=weights.nominal_bytes or None)
        if on_progress is not None
        else None
    )
    kwargs: dict[str, object] = {
        "revision": weights.revision,
        "cache_dir": str(models_dir),
        "allow_patterns": weights.patterns,
    }
    if tqdm_class is not None:
        kwargs["tqdm_class"] = tqdm_class
    return snapshot_download(weights.repo_id, **kwargs)
