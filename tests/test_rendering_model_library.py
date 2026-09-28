"""rendering.model_library: the /models library's own rows and its
installation summary.
"""

from __future__ import annotations

from voxtrama.rendering.model_library import installation_summary_view, weight_row
from voxtrama.setup.installation import InstallationConfig
from voxtrama.weights import ecapa_weights


def test_a_weight_row_carries_the_weight_sets_own_facts() -> None:
    view = weight_row("ecapa", ecapa_weights(), installed=True, redownload_notice=True)

    assert view.key == "ecapa"
    assert view.label == "speaker model ECAPA-TDNN"
    assert view.licence == "Apache-2.0"
    assert "huggingface.co" in view.page_url
    assert view.installed is True
    assert view.redownload_notice is True


def test_no_installation_config_yet_leaves_every_field_none() -> None:
    view = installation_summary_view(None)

    assert view.configured is False
    assert view.profile_label is None
    assert view.parallelism_label is None
    assert view.generative_model is None
    assert view.context_cap_label is None


def test_a_written_config_reads_as_the_summary_line() -> None:
    config = InstallationConfig(
        hardware_profile="high",
        cores_per_chunk=6,
        parallel_chunks=2,
        ollama_model="qwen3:30b-a3b-instruct",
        model_context_limits={"qwen3:30b-a3b-instruct": 8192},
    )

    view = installation_summary_view(config)

    assert view.configured is True
    assert view.profile_label == "Maximum accuracy"
    assert view.parallelism_label == "2 chunks × 6 cores"
    assert view.generative_model == "qwen3:30b-a3b-instruct"
    assert view.context_cap_label == "8192 tokens"


def test_a_generative_model_with_no_stored_context_cap_shows_none() -> None:
    config = InstallationConfig(
        hardware_profile="base",
        cores_per_chunk=4,
        parallel_chunks=2,
        ollama_model="qwen3:30b-a3b-instruct",
    )

    view = installation_summary_view(config)

    assert view.context_cap_label is None
