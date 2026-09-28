"""edition.policy: the Community Edition's limits come from a signed block.

The shipped block must verify and say one custom workflow. Any change to it
(a byte flipped, a block signed by another key, no block at all) must
leave the limits at the minimum, never above what was signed.
"""

from __future__ import annotations

import json
import zlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from voxtrama.edition import MINIMUM_POLICY, current_policy, read_policy
from voxtrama.edition import policy as policy_module


def _block(key: Ed25519PrivateKey, data: dict) -> bytes:
    payload = zlib.compress(json.dumps(data).encode())
    return key.sign(payload) + payload


def _public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def test_the_shipped_block_verifies_and_allows_one_custom_workflow() -> None:
    policy = current_policy()

    assert policy.custom_workflows == 1
    assert policy.profile_fields == {"given_name", "family_name"}


def test_a_block_signed_by_the_right_key_is_read() -> None:
    key = Ed25519PrivateKey.generate()
    block = _block(key, {"w": 3, "p": ["given_name"]})

    assert read_policy(block, _public(key)).custom_workflows == 3


def test_an_altered_block_falls_to_the_minimum() -> None:
    raw = (policy_module.files("voxtrama.edition") / "policy.bin").read_bytes()
    tampered = raw[:-1] + bytes([raw[-1] ^ 0x01])

    assert read_policy(tampered) == MINIMUM_POLICY


def test_a_block_signed_by_another_key_falls_to_the_minimum() -> None:
    forged = _block(Ed25519PrivateKey.generate(), {"w": 99, "p": ["given_name"]})

    assert read_policy(forged) == MINIMUM_POLICY


def test_a_missing_or_garbled_block_falls_to_the_minimum() -> None:
    assert read_policy(None) == MINIMUM_POLICY
    assert read_policy(b"short") == MINIMUM_POLICY
    assert MINIMUM_POLICY.custom_workflows == 0


def test_no_environment_variable_raises_the_limit(monkeypatch) -> None:
    monkeypatch.setenv("VOXTRAMA_CUSTOM_WORKFLOWS", "50")
    current_policy.cache_clear()

    assert current_policy().custom_workflows == 1
