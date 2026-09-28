"""Whether the engine can run on the hardware profile that is configured.

Narrows "the engine responds" to what a page render can afford: resolving
the configured profile to a model/compute-type pair, the same lookup
transcription.asr performs before it loads a model
(transcription.profiles.resolve_profile). Loading a model, or calling
one, would cost seconds or a download, which is out of scope for a
reading that runs on every page.
"""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.readiness_state import LocalProcessingCheck, Readiness
from voxtrama.transcription.profiles import resolve_profile


def check_local_processing(settings: Settings) -> LocalProcessingCheck:
    """Resolve the configured hardware profile, without loading or calling anything.

    The hardware profiles form a closed table and Settings already rejects
    any value outside it before a Settings instance can exist, so the
    except branch below is a defensive floor, not a case this reaches in
    practice: resolve_profile itself raises "rather than
    falling back to a default", and hiding that behind a silent guess
    would be worse than reporting UNKNOWN.
    """
    profile = settings.hardware_profile
    try:
        resolve_profile(profile)
    except ValueError as exc:
        return LocalProcessingCheck(
            state=Readiness.UNKNOWN,
            reason=f"hardware profile '{profile}' is not one the engine recognises: {exc}",
            hardware_profile=profile,
        )
    return LocalProcessingCheck(
        state=Readiness.READY,
        reason=f"hardware profile '{profile}' is configured and resolves to a model profile",
        hardware_profile=profile,
    )
