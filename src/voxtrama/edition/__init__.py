"""The edition's limits: what this installation is allowed to do.

See edition.policy for how the limits are read and why they are signed.
"""

from voxtrama.edition.policy import (
    MINIMUM_POLICY,
    EditionPolicy,
    PolicyLimitError,
    current_policy,
    read_policy,
)

__all__ = [
    "MINIMUM_POLICY",
    "EditionPolicy",
    "PolicyLimitError",
    "current_policy",
    "read_policy",
]
