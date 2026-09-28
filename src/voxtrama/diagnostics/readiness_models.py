"""Whether the ASR weights the configured profile needs are already downloaded.

Reuses weights.is_cached as the pre-run download announcement does
(transcription.asr.weights_for, engine.downloads): a local check against
the Hugging Face cache directory, local_files_only=True, that never reaches
the network, instead of a second profile-to-model table invented here.
That is also its limit: a cache left incomplete by a killed download
would still read as cached, the same limit is_cached already has for its
existing callers.
"""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.readiness_state import ModelsReadyCheck, Readiness
from voxtrama.transcription.asr import weights_for
from voxtrama.transcription.profiles import resolve_profile
from voxtrama.weights import is_cached


def check_models_ready(settings: Settings) -> ModelsReadyCheck:
    """Check whether `settings.hardware_profile`'s ASR weights are already in models_dir."""
    profile = settings.hardware_profile
    try:
        model_size = resolve_profile(profile).model_size
    except ValueError:
        return ModelsReadyCheck(
            state=Readiness.UNKNOWN,
            reason=f"hardware profile '{profile}' is not recognised, so no model can be named",
            model=None,
        )
    models_dir = settings.models_dir
    if models_dir is None:
        return ModelsReadyCheck(
            state=Readiness.UNKNOWN, reason="models_dir is not configured", model=model_size
        )
    if is_cached(weights_for(profile), models_dir):
        return ModelsReadyCheck(
            state=Readiness.READY, reason=f"model '{model_size}' is downloaded", model=model_size
        )
    return ModelsReadyCheck(
        state=Readiness.NOT_READY,
        reason=f"model '{model_size}' has not been downloaded yet",
        model=model_size,
    )
