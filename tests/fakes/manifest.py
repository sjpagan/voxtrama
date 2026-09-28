"""A complete, schema-valid manifest dict, for the manifest comparison tests.

Every field the walker or the determinism gate can look at has to be
present and internally consistent: built once as a Manifest and dumped to
the dict the comparison reads, rather than a literal copied into every
test file, where a typo would silently make a test check nothing.

The two ManifestStep fixtures live in fakes.manifest_steps, split out once
ManifestChoices/ManifestRun gained new fields to set here.
"""

from __future__ import annotations

from fakes.manifest_steps import build_steps
from voxtrama.manifest.choices import ManifestChoices
from voxtrama.manifest.evidence import ManifestEvidence
from voxtrama.manifest.schema import (
    LanguageProvenance,
    Manifest,
    ManifestDestination,
    ManifestEnvironment,
    ManifestInput,
    ManifestLanguage,
    ManifestLanguages,
    ManifestOutput,
    ManifestRun,
    ManifestWorkflow,
)


def _run() -> ManifestRun:
    return ManifestRun(
        id="run-1",
        state="succeeded",
        final=True,
        created_at="t0",
        started_at="t1",
        finished_at="t2",
        destination=ManifestDestination(root="data_dir", path="runs/run-1"),
        label=None,
    )


def _choices() -> ManifestChoices:
    return ManifestChoices(
        hardware_profile=None,
        generative_model=None,
        step_skills={},
        diarize=None,
        max_speakers=None,
        cores_per_chunk=None,
        parallel_chunks=None,
    )


def manifest_dict(*, all_same_host: bool = False) -> dict:
    """A fresh manifest. See fakes.manifest_steps.build_steps for what `all_same_host` changes."""
    return Manifest(
        run=_run(),
        input=ManifestInput(
            recording_id="rec-1",
            sha256="a" * 64,
            duration_seconds=12.5,
            media_format="wav",
            provenance="local_file",
            source_url=None,
            source_title=None,
        ),
        environment=ManifestEnvironment(
            voxtrama_version="0.1.0",
            hardware_profile_requested="base",
            hardware_profile_used="base",
            device="cpu",
            cpu_threads=4,
            num_workers=2,
        ),
        languages=ManifestLanguages(
            interface=ManifestLanguage(value=None, provenance=LanguageProvenance.NOT_RECORDED),
            audio=ManifestLanguage(value="en", provenance=LanguageProvenance.DETECTED),
            output=ManifestLanguage(value=None, provenance=LanguageProvenance.NOT_RECORDED),
        ),
        workflow=ManifestWorkflow(name="demo", version="1.0.0", definition_sha256="d" * 64),
        choices=_choices(),
        steps=build_steps(all_same_host=all_same_host),
        outputs=[ManifestOutput(path="output.json", sha256="e" * 64)],
        evidence=ManifestEvidence(claims=3, needs_review=1),
        failure=None,
    ).model_dump(mode="json")
