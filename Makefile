# The version lives here and nowhere else: sass-install downloads it, css
# checks a PATH-installed `sass` against it, and the CI pipeline installs
# the same tarball this Makefile would. One number, three consumers.
SASS_VERSION := 1.104.1

# dart-sass's own release naming (sass/dart-sass on GitHub), not ours:
# dart-sass-$(SASS_VERSION)-<os>-<arch>.tar.gz.
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
  SASS_OS := macos
else ifeq ($(UNAME_S),Linux)
  SASS_OS := linux
else
  $(error unsupported OS for dart-sass: $(UNAME_S))
endif

ifeq ($(UNAME_M),arm64)
  SASS_ARCH := arm64
else ifeq ($(UNAME_M),aarch64)
  SASS_ARCH := arm64
else ifeq ($(UNAME_M),x86_64)
  SASS_ARCH := x64
else
  $(error unsupported architecture for dart-sass: $(UNAME_M))
endif

SASS_ARCHIVE := dart-sass-$(SASS_VERSION)-$(SASS_OS)-$(SASS_ARCH).tar.gz
SASS_URL := https://github.com/sass/dart-sass/releases/download/$(SASS_VERSION)/$(SASS_ARCHIVE)

# .tools/ is gitignored: it holds a downloaded binary, not source.
VENDORED_SASS := .tools/dart-sass/sass

SCSS_ENTRY := src/voxtrama/web/scss/voxtrama.scss
CSS_OUTPUT := src/voxtrama/web/static/css/voxtrama.min.css

.PHONY: sass-install css up down lock licences docs docs-serve

# Picks a free host port when VOXTRAMA_HOST_PORT is not already set,
# brings the stack up detached, then waits for the *published* URL to
# answer before printing it, not for the container's own healthcheck,
# which never touches the port mapping. See scripts/up.sh for the reasoning.
up:
	scripts/up.sh

# Regenerate the locks from pyproject.toml's ranges. Run it when a
# dependency changes in pyproject.toml, and once a month otherwise; commit
# the two files together, with the test suite green on them. Needs
# pip-tools (`pip install pip-tools`) and the Python the image uses (3.11).
PIP_COMPILE = pip-compile --quiet --strip-extras --extra-index-url https://download.pytorch.org/whl/cpu
lock:
	$(PIP_COMPILE) --upgrade --output-file requirements.lock pyproject.toml
	$(PIP_COMPILE) --upgrade --extra dev --output-file requirements-dev.lock pyproject.toml
	pip-compile --quiet --strip-extras --upgrade --output-file requirements-docs.lock requirements-docs.in

# THIRD_PARTY_LICENSES.md from requirements.lock; run it after `make lock`
# (tests/test_third_party_licenses.py fails until it is).
licences:
	python scripts/generate_third_party_licenses.py

# The documentation site, built from docs/guide/ by mkdocs.yml. Needs
# `pip install -r requirements-docs.lock` first. --strict turns a broken
# link or a page missing from the navigation into an error, as in CI.
docs:
	mkdocs build --strict

# The same site served on http://127.0.0.1:8001, rebuilt on every save.
docs-serve:
	mkdocs serve --dev-addr 127.0.0.1:8001

# The other half of `up`: `up -d` leaves the stack running in the
# background, so stopping it needs its own command too.
down:
	docker compose down

# Downloads the locked dart-sass build into .tools/, never touching the
# system's PATH. Kept separate from `css` so that a developer who already
# ran it once is not paying for a re-download on every build.
sass-install:
	rm -rf .tools/dart-sass
	mkdir -p .tools
	curl -fsSL -o .tools/$(SASS_ARCHIVE) $(SASS_URL)
	tar -xzf .tools/$(SASS_ARCHIVE) -C .tools
	rm .tools/$(SASS_ARCHIVE)

# Prefers the vendored binary so a build is reproducible without anything
# on PATH. Falls back to a PATH `sass` only if its version matches exactly:
# `brew install sass` or an npm install would otherwise compile against
# whatever happens to be newest that day, silently. No fallback resolves
# to a failure with a message, not a guess.
css:
ifneq (,$(wildcard $(VENDORED_SASS)))
	$(VENDORED_SASS) --style=compressed --no-source-map $(SCSS_ENTRY) $(CSS_OUTPUT)
else
	@PATH_SASS_VERSION=$$(sass --version 2>/dev/null); \
	if [ "$$PATH_SASS_VERSION" = "$(SASS_VERSION)" ]; then \
		sass --style=compressed --no-source-map $(SCSS_ENTRY) $(CSS_OUTPUT); \
	else \
		echo "dart-sass $(SASS_VERSION) not found: run 'make sass-install' first" >&2; \
		exit 1; \
	fi
endif
