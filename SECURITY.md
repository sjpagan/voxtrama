# Security policy

## Supported versions

Voxtrama is an alpha. Only the latest release receives fixes.

## Reporting a vulnerability

Do not open a public issue. Report it privately through GitHub: on the
repository page, open **Security**, then **Report a vulnerability**. Only
the maintainer can read the report.

Include what an attacker can do, the steps to reproduce it, and the version
(`voxtrama version`). You will get an answer within seven days. Once a fix
is released, the report is published with credit to you, unless you ask
otherwise.

## What Voxtrama is designed to protect

- **Your recordings and transcripts stay on your machine.** They are sent
  only to a model server you configured, and a step marked `local_only`
  refuses a remote one.
- **The web interface listens on `127.0.0.1` only** and refuses requests
  from other sites and from unknown host names, including DNS rebinding.
- **Credentials for a model server** travel only over `https`, or to a
  server on the same machine, and are held as secrets that logs never show.

A way around any of these is a vulnerability. Exposing the interface on a
network yourself, for example through a reverse proxy, is outside what the
alpha protects: Voxtrama has no login.
