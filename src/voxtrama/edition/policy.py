"""The Community Edition's limits, read from a signed block.

The CE is free to download and
works within limits: the profile edits only first and last name, and at
most one custom workflow sits beside the three the package ships. Those
limits are enforced on the server, not by hiding a button, and nothing a
user can set raises them: no setting, no environment variable.

So the numbers are not in the code. They live in `policy.bin`, a block
shipped inside the package: 64 bytes of Ed25519 signature followed by the
compressed payload it signs. The server checks the signature against the
public key below. The private key never enters the repository: the block
is signed at release time (scripts/sign_policy.py). A block that is
missing, altered or unreadable does not raise the limits: it drops them to
MINIMUM_POLICY and says so in the log.

Every place that enforces a limit reads it from current_policy(), so
deleting one check leaves the others in force. None of this is absolute
on a program that runs on the user's own machine. It raises the effort,
which is what it is asked to do. An Enterprise Edition replaces this module
rather than chasing checks scattered across the code.
"""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

logger = logging.getLogger(__name__)

_BLOCK_NAME = "policy.bin"
_SIGNATURE_BYTES = 64
_PUBLIC_KEY = bytes.fromhex("fed373c5e4c86ad7a1482a959bbd5e5a49e5b8d3cc687961911e5e1ee2adf6d6")


class PolicyLimitError(Exception):
    """An action the edition's policy does not allow."""


@dataclass(frozen=True)
class EditionPolicy:
    """What this installation may do: custom workflows, and profile fields."""

    custom_workflows: int
    profile_fields: frozenset[str]

    def allows_profile_field(self, field: str) -> bool:
        return field in self.profile_fields


# The floor a broken block falls to: no custom workflow at all, and a name
# can still be written, since without it the product would not be usable.
MINIMUM_POLICY = EditionPolicy(
    custom_workflows=0, profile_fields=frozenset({"given_name", "family_name"})
)


def _decode(raw: bytes, public_key: bytes) -> EditionPolicy:
    signature, payload = raw[:_SIGNATURE_BYTES], raw[_SIGNATURE_BYTES:]
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)
    data = json.loads(zlib.decompress(payload))
    return EditionPolicy(custom_workflows=int(data["w"]), profile_fields=frozenset(data["p"]))


def read_policy(raw: bytes | None, public_key: bytes = _PUBLIC_KEY) -> EditionPolicy:
    """The policy `raw` carries if its signature holds, MINIMUM_POLICY otherwise."""
    if raw is None:
        logger.warning("edition policy block missing: limits set to the minimum")
        return MINIMUM_POLICY
    try:
        return _decode(raw, public_key)
    except (InvalidSignature, ValueError, KeyError, TypeError, zlib.error):
        logger.warning("edition policy block not valid: limits set to the minimum")
        return MINIMUM_POLICY


@cache
def current_policy() -> EditionPolicy:
    """The policy shipped with this package, verified once per process."""
    try:
        raw = files("voxtrama.edition").joinpath(_BLOCK_NAME).read_bytes()
    except OSError:
        raw = None
    return read_policy(raw)
