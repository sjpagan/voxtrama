"""cpu_threads/num_workers reaching WhisperModel, and device staying "cpu"
regardless of what the selected tuning file declares.

Split from test_transcription_asr.py to stay under the project's 150-line file
cap: this file never loads a real Whisper model, unlike the two @slow tests
there, so it needs none of that file's audio-fixture helpers.
"""

from __future__ import annotations

import pytest
from fakes.machine import use_eight_cores
from fakes.whisper_model import FakeWhisperModel

from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.transcription import model_loading, transcribe


def _recording() -> Recording:
    return Recording(
        id="rec1",
        original_filename="meeting.wav",
        stored_path="recordings/rec1/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )


@pytest.fixture(autouse=True)
def _fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """No gigabytes of real weights: WhisperModel and fetch_weights are both
    doubles, so transcribe() runs against nothing but the fake's kwargs.
    """
    FakeWhisperModel.last_kwargs = None
    monkeypatch.setattr(model_loading, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(model_loading, "fetch_weights", lambda *args, **kwargs: None)
    use_eight_cores(monkeypatch)  # the numbers asked for must not be capped by the host


def test_transcribe_passes_settings_cores_and_workers_to_whisper_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cpu_threads is the full budget (3 * 2), never just cores_per_chunk:
    with no chunking, that product is the only number left claiming the
    cores a run declared for itself. num_workers stays 1: a second worker
    only runs if something calls transcribe() from another thread.
    """
    monkeypatch.setenv("VOXTRAMA_CORES_PER_CHUNK", "3")
    monkeypatch.setenv("VOXTRAMA_PARALLEL_CHUNKS", "2")
    get_settings.cache_clear()

    transcribe(_recording(), "low")

    assert FakeWhisperModel.last_kwargs["cpu_threads"] == 6
    assert FakeWhisperModel.last_kwargs["num_workers"] == 1


def test_transcribe_records_the_effective_values_on_the_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Transcript carries what was used, the
    same numbers WhisperModel was given, not what Settings asked for. The
    manifest needs that to explain a run that took twice as long as
    another differing only in parallelism.
    """
    monkeypatch.setenv("VOXTRAMA_CORES_PER_CHUNK", "3")
    monkeypatch.setenv("VOXTRAMA_PARALLEL_CHUNKS", "2")
    get_settings.cache_clear()

    transcript = transcribe(_recording(), "low")

    assert transcript.cpu_threads == 6
    assert transcript.num_workers == 1


def test_transcribe_falls_back_to_the_machine_s_tuning_proposal_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings.cores_per_chunk/.parallel_chunks are None (no guided setup
    has run yet): the fallback must be this machine's own tuning.selector
    proposal, never faster-whisper's own defaults (cpu_threads=0,
    num_workers=1): the "twenty cores and four cores behave the same"
    defect.
    """
    monkeypatch.delenv("VOXTRAMA_CORES_PER_CHUNK", raising=False)
    monkeypatch.delenv("VOXTRAMA_PARALLEL_CHUNKS", raising=False)
    get_settings.cache_clear()
    assert get_settings().cores_per_chunk is None

    transcribe(_recording(), "low")

    assert FakeWhisperModel.last_kwargs["cpu_threads"] >= 1
    assert FakeWhisperModel.last_kwargs["num_workers"] >= 1


def test_device_stays_cpu_even_when_the_selected_tuning_declares_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine uses an accelerator only if the
    configuration asks for one, and nothing does, since AsrTuning.device
    is never read here. Forcing tuning.selector to pick tuning/x86-cuda.yaml
    (a real file this repo ships, declaring asr.device: cuda) proves the
    constant in model_loading.load_model against the exact file that would
    otherwise tempt it, rather than against a mock with no opinion.
    """

    def _fake_read_machine(data_dir: object) -> MachineReport:
        return MachineReport(
            platform="test",
            architecture="x86_64",
            cpu_count=8,
            performance_cores=None,
            efficiency_cores=None,
            cpu_brand=None,
            total_memory_bytes=16 * 1024**3,
            unified_memory=False,
            free_disk_bytes=100 * 1024**3,
            gpu_available=True,
            accelerator="cuda",
            in_container=False,
        )

    # Patched where it is defined, not where it is used: resources.py
    # imports the diagnostics.machine module itself, not read_machine by
    # name, so the call inside resolve_engine_resources still resolves
    # this attribute at call time from voxtrama.diagnostics.machine.
    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", _fake_read_machine)

    transcribe(_recording(), "low")

    assert FakeWhisperModel.last_kwargs["device"] == "cpu"
