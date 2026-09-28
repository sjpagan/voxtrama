"""A run names a configured provider. A remote one never reaches a local_only skill."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from voxtrama.config.providers import ProviderConfig
from voxtrama.config.settings import Settings, get_settings
from voxtrama.engine.choice_check import check_choices
from voxtrama.providers.base import PrivacyViolation
from voxtrama.providers.registry import configured_providers, provider_named
from voxtrama.providers.selection import ProviderNotConfiguredError, text_provider_for
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.rejection import ChoicesRejected
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill

PROVIDERS = {
    "box": ProviderConfig(url="http://127.0.0.1:11434"),
    "cloud": ProviderConfig(url="https://llm.example.com", auth=SecretStr("t0ken")),
}


def _skill(name: str, privacy: Privacy, model_class=ModelClass.GENERATIVE) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=model_class,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=privacy,
    )


SKILLS: SkillRegistry = {
    "transcribe": {"1.0.0": _skill("transcribe", Privacy.LOCAL_ONLY, ModelClass.EXTRACTIVE)},
    "summarize": {"1.0.0": _skill("summarize", Privacy.ANY)},
    "secret_recap": {"1.0.0": _skill("secret_recap", Privacy.LOCAL_ONLY)},
}


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="wf", version="1.0.0", schema_version="v1", description="t", steps=list(steps)
    )


@pytest.fixture(autouse=True)
def settings(monkeypatch, tmp_path):
    settings = Settings(data_dir=tmp_path, providers=PROVIDERS)
    monkeypatch.setattr("voxtrama.engine.provider_choice.get_settings", lambda: settings)
    monkeypatch.setattr("voxtrama.providers.selection.get_settings", lambda: settings)
    return settings


def test_the_old_single_url_is_the_provider_called_default(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, ollama_url="http://localhost:11434")

    assert list(configured_providers(settings)) == ["default"]
    assert provider_named(settings, None).locality == "local"


def test_a_registry_names_its_providers_and_says_where_each_is(settings) -> None:
    assert {n: p.locality for n, p in configured_providers(settings).items()} == {
        "box": "local",
        "cloud": "remote",
    }
    assert provider_named(settings, None).name == "box"  # no default: the first


def test_a_name_nobody_configured_is_rejected() -> None:
    workflow = _workflow(Step(id="t", skill="transcribe", skill_version="1.0.0"))

    with pytest.raises(ChoicesRejected, match="not a configured provider"):
        check_choices(RunChoices(provider="elsewhere"), workflow, SKILLS)


def test_a_remote_provider_is_refused_for_a_local_only_skill_even_behind_a_condition() -> None:
    workflow = _workflow(
        Step(id="t", skill="transcribe", skill_version="1.0.0"),
        Step(id="s", skill="secret_recap", skill_version="1.0.0", condition="false"),
    )

    with pytest.raises(ChoicesRejected) as exc:
        check_choices(RunChoices(provider="cloud"), workflow, SKILLS)

    assert "skill secret_recap@1.0.0 (step s)" in str(exc.value)
    check_choices(RunChoices(provider="box"), workflow, SKILLS)


def test_transcription_s_own_local_only_does_not_forbid_a_remote_recap() -> None:
    workflow = _workflow(
        Step(id="t", skill="transcribe", skill_version="1.0.0"),
        Step(id="s", skill="summarize", skill_version="1.0.0"),
    )

    check_choices(RunChoices(provider="cloud"), workflow, SKILLS)


def test_the_provider_is_built_for_the_name_and_checked_before_any_call() -> None:
    secret = SKILLS["secret_recap"]["1.0.0"]

    with pytest.raises(PrivacyViolation, match="provider cloud is remote"):
        text_provider_for(secret, "cloud")
    with pytest.raises(ProviderNotConfiguredError, match="no provider named 'nowhere'"):
        text_provider_for(secret, "nowhere")
    assert text_provider_for(secret, "box") is not None


def test_the_registry_is_read_from_the_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VOXTRAMA_PROVIDERS", '{"box": {"url": "http://127.0.0.1:11434"}}')
    get_settings.cache_clear()
    try:
        assert list(Settings(data_dir=tmp_path).providers) == ["box"]
    finally:
        get_settings.cache_clear()


def test_naming_another_provider_reruns_the_model_steps_not_the_transcription() -> None:
    from types import SimpleNamespace

    from voxtrama.engine.step_hashing import _choices_read_by

    context = SimpleNamespace(choices=RunChoices(provider="cloud"), kept_local={})

    assert (
        _choices_read_by(SimpleNamespace(id="s", skill="summarize"), context)["provider"] == "cloud"
    )
    assert "provider" not in _choices_read_by(SimpleNamespace(id="t", skill="transcribe"), context)
