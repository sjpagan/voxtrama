"""The contract every text-generation provider satisfies, and what it declares.

Skills are split into extractive and generative, and the second sits
behind a *provider*: something that turns a prompt into text and says where
that text came from. `TextProvider` is that contract. One implementation
exists today (`providers/ollama.py`). The split exists so a second one would
never have to touch the engine. A second one is not expected soon.

Each failure gets its own exception rather than one generic error with a
code attached, for the same reason `engine.anchoring.EvidenceNotAnchored` is
its own class: `providers/http.py` and `ollama.py` map onto these at the one
point that knows which is which, and `error_code_for` tells them apart by
type, never by inspecting a message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from voxtrama.providers.probe import GenerationSpeed, ProviderProbe


@dataclass(frozen=True)
class GenerationResult:
    """What generate() produced, and what Ollama said about reading and writing it.

    `prompt_eval_count` is how many prompt tokens the model
    read (proves a truncated input, against an estimate, instead
    of guessing one), and `done_reason == "length"` means the generation
    hit its output cap. Both None when omitted, never a stand-in.
    """

    text: str
    done_reason: str | None
    prompt_eval_count: int | None


@dataclass(frozen=True)
class ModelProvenance:
    """Where a generated text came from.

    `fingerprint` is the model's digest, never its tag: two hosts can serve
    different weights under the same name, so `None` here is
    honest and a tag standing in for it would not be. `remote` and
    `profile_check_skipped` both derive from which host the provider talked
    to, carried here already computed rather than left to re-derive.
    """

    provider: str
    host: str
    model: str
    fingerprint: str | None
    remote: bool
    profile_check_skipped: bool


class TextProvider(Protocol):
    """Turns a prompt into text, once, and says where it ran.

    One call, one answer: a generative step is never retried
    when it may already have produced something, so there is no streaming and
    nothing partial to resume.
    """

    def generate(
        self,
        prompt: str,
        model: str,
        json_output: bool = False,
        *,
        options: dict[str, Any] | None = None,
    ) -> tuple[GenerationResult, ModelProvenance]:
        """Return what was generated and the provenance it ran under.

        `json_output` sets two fields together. A measurement
        found that OllamaProvider must set `format: json` and
        `think: false` at once, because either alone corrupts a
        thinking-capable model's output. Two parameters would invite
        setting only one of them.

        `options` is passed unchanged into Ollama's `options` object, for
        example `num_ctx` chosen per call instead of the server's default.

        Raises one of this module's errors instead of a bare exception from
        the transport.
        """
        ...

    def probe(self) -> ProviderProbe:
        """Reachability, latency, declared version and models. Never raises.

        What doctor asks the remote node: asked once, by a person, before any workflow
        step runs. Every ProviderError hit internally becomes
        ProviderProbe.error instead of propagating.
        """
        ...

    def measure_generation(self, model: str) -> GenerationSpeed:
        """Time one short, real generation on `model`.

        Unlike probe(), this can raise: a missing model or a host that
        stops answering mid-measurement is a fact its caller decides how
        to report, not one probe() already covers.
        """
        ...


class ProviderError(RuntimeError):
    """Base class for every way a TextProvider call, or its selection, can fail."""


class ProviderCredentialsError(ProviderError):
    """The provider answered 401 or 403: it wants credentials we do not have.

    Names the host, never the credential or the raw
    body. The raw body is the "expecting value: line 1 column 1" trap.
    """


class ProviderModelNotFoundError(ProviderError):
    """The provider answered 404: the requested model is not on that host."""


class ProviderResponseError(ProviderError):
    """The provider's response could not be used: bad JSON, or an unmapped status.

    Covers a 200 whose body is not the JSON expected, and any 4xx/5xx other
    than 401, 403 and 404: code plus a truncated body, so no one reads a
    raw traceback to learn what the provider said.
    """


class ProviderTimeoutError(ProviderError):
    """The provider did not answer within provider_timeout_seconds."""


class ProviderTransportError(ProviderError):
    """The provider could not be reached at all: DNS, refused connection, TLS."""


class PrivacyViolation(ProviderError):
    """A local_only skill would have used a remote provider.

    Raised by providers.selection.text_provider_for before any provider is
    constructed or connected. See that module's docstring.
    """
