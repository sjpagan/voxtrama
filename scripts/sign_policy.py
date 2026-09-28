"""Sign the Community Edition's policy block at release time.

Usage: python scripts/sign_policy.py <private-key.pem>

Writes src/voxtrama/edition/policy.bin: the Ed25519 signature followed by
the compressed payload it covers. The private key is never committed: it
stays with whoever cuts the release. Changing the limits means editing
POLICY below, signing again and committing the new block. The server
refuses any block this key did not sign.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key

POLICY = {"w": 1, "p": ["family_name", "given_name"]}
TARGET = Path(__file__).resolve().parents[1] / "src" / "voxtrama" / "edition" / "policy.bin"


def main(key_path: str) -> None:
    key = load_pem_private_key(Path(key_path).read_bytes(), password=None)
    payload = zlib.compress(json.dumps(POLICY, separators=(",", ":")).encode(), 9)
    TARGET.write_bytes(key.sign(payload) + payload)
    print(f"signed {TARGET}")


if __name__ == "__main__":
    main(sys.argv[1])
