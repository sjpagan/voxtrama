# Pico CSS — provenance

Vendored, not pulled from a CDN: ADR 0007 rules out CDN-hosted assets for
the shell, since a desktop build (ADR 0004) must work offline.

| | |
|---|---|
| Version | v2.1.1 |
| Source | https://raw.githubusercontent.com/picocss/pico/v2.1.1/css/pico.min.css |
| SHA-256 | `fbc9a63fc9fc9f72d12fd7fc9806e11fa9f77ae4f9cad146b27003a1119ba3db` |
| License | MIT — see `LICENSE` in this directory, taken from the same tag |

To update: change the tag in the URL above, re-download, recompute the
hash, and update both here. `voxtrama.scss` does not depend on Pico's
source files, only on the custom properties it publishes at runtime, so a
version bump never touches the SCSS.
