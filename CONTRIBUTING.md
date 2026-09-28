# Contributing to Voxtrama

Voxtrama is an alpha maintained by one person. The useful contributions
right now are, in this order: bug reports with a way to reproduce them,
measurements on real recordings, and small, focused changes.

## Reporting a bug

Open an issue with:

- What you did, what you expected, and what happened instead.
- The output of `docker compose exec web voxtrama doctor`.
- The job's `run.log` (`<data folder>/runs/<job id>/run.log`) if a job
  failed. Check it first: it can contain file names and model server
  addresses you may not want to publish.

Never attach a recording or a transcript you do not have the right to
share. A short clip you recorded yourself is enough to reproduce most
problems.

Security problems do not go in a public issue: see [SECURITY.md](SECURITY.md).

## Proposing a change

For anything larger than a typo, open an issue first and describe the
problem, not only the fix. A change nobody asked for is hard to review and
easy to decline.

Then:

1. Fork the repository and create a branch from the series branch
   (`0.1.x` today), named after the issue: `<issue number>-<short-slug>`,
   for example `7-zip-export`.
2. Install the development environment and check that everything passes
   before you change anything:

   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements-dev.lock
   .venv/bin/pip install --no-deps -e .
   .venv/bin/ruff check .
   .venv/bin/ruff format --check .
   .venv/bin/pytest
   ```

3. Make the change, with a test that fails without it.
4. If you change a `.scss` file, rebuild the stylesheet with `make css` and
   commit the result.
5. Open a pull request against that same series branch that says what
   changed, why, and how you checked it.

Commit messages start with the issue they belong to:
`Issue #7: Export a job as one ZIP`.

Keep a pull request to one change. Files stay under 150 lines and
functions under 40 (`tests/test_architecture_limits.py` checks it). Split
a module rather than raising the limit.

## Licence of contributions

Voxtrama is released under the [Apache License 2.0](LICENSE). By opening a
pull request you agree that your contribution is licensed under the same
terms, as section 5 of the licence says. There is no separate contributor
agreement.
