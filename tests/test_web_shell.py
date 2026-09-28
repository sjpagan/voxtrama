"""The shell, checked the way a rendering test can and a build cannot.

`make css` and the CI job that reruns it prove the SCSS compiles and stays
deterministic; they say nothing about the template that loads the result.
These tests are the ones that would catch base.html linking the two
stylesheets in the wrong order, a stray absolute URL sneaking into the
shell (no CDNs and no hosts allowed), or a generated artifact that
silently regressed to empty.
"""

from __future__ import annotations

import re
from pathlib import Path

import jinja2

from voxtrama.rendering.assets import static_url
from voxtrama.rendering.nav import BackLink, Crumb

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "voxtrama" / "web"


def _render_base(**context: object) -> str:
    # base.html now imports the sidebar and header components, and
    # both use {% trans %}, so the i18n extension has to be on this throwaway
    # Environment too, or Jinja fails to even parse them. install_null_
    # translations() is the environment-wide install voxtrama.i18n.jinja
    # deliberately avoids in the real app (see its own docstring on the
    # concurrency race that would cause); here there is only one render,
    # so there is nothing to race.
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(WEB_ROOT / "templates"))
    env.add_extension("jinja2.ext.i18n")
    env.install_null_translations(newstyle=True)
    # base.html calls static_url() for both stylesheets, the same
    # global api.templating registers on the real Environment.
    env.globals["static_url"] = static_url
    template = env.get_template("base.html")
    return template.render(**context)


def test_base_html_links_pico_before_voxtrama() -> None:
    """voxtrama.min.css overrides Pico's cascade, not the other way round."""
    rendered = _render_base()
    hrefs = re.findall(r'<link[^>]+href="([^"]+)"', rendered)
    stylesheet_hrefs = [href for href in hrefs if "pico" in href or "voxtrama" in href]
    # Each href now carries a `?v=<mtime>` cache-busting suffix,
    # asserted separately below, not part of the path this test checks.
    paths = [href.split("?", 1)[0] for href in stylesheet_hrefs]
    assert paths == [
        "/static/vendor/pico/pico.min.css",
        "/static/css/voxtrama.min.css",
    ], f"unexpected stylesheet order or hrefs: {stylesheet_hrefs}"
    assert all("?v=" in href for href in stylesheet_hrefs), stylesheet_hrefs


def test_base_html_declares_english() -> None:
    rendered = _render_base()
    assert re.search(r'<html[^>]+lang="en"', rendered)


def test_a_breadcrumb_replaces_the_back_link() -> None:
    """Two ways to climb on the same row is noise, not help."""
    rendered = _render_base(
        breadcrumb=[Crumb(key="runs", href="/"), Crumb(key="run", label="team-meeting.wav")],
        back_link=BackLink(key="all-runs", href="/"),
    )
    assert "vx-breadcrumb" in rendered
    assert "vx-back-link" not in rendered


def test_a_back_link_alone_still_renders() -> None:
    rendered = _render_base(back_link=BackLink(key="all-runs", href="/"))
    assert "vx-back-link" in rendered
    assert "vx-breadcrumb" not in rendered


# CSS url(...): the shape a CDN font or stylesheet import takes. Pico's
# inlined SVGs are `url("data:image/svg+xml,...")`, which does not start
# with http(s):// right after the paren, so they do not match.
_CSS_URL = re.compile(r'url\(\s*["\']?(https?://[^"\'\s)]+)')

# <link href="..."> / <script src="...">
_MARKUP_URL = re.compile(r'(?:href|src)\s*[=:]\s*["\']?(https?://[^"\'\s)]+)')

_ABSOLUTE_URL_PATTERNS = [_MARKUP_URL, _CSS_URL]


def test_no_absolute_url_or_cdn_host_under_web() -> None:
    """No host, no port, no CDN: the shell must work offline.

    The vendored pico.min.css is scanned too, but only for `url(http...)`:
    that is the shape a CDN font or import would take, and the one a
    future Pico bump could bring in unnoticed. Its `href=` patterns are
    skipped instead, because Pico's minified header links picocss.com in
    a comment: a credit line, not a resource this shell fetches.
    """
    vendored_pico = WEB_ROOT / "static" / "vendor" / "pico" / "pico.min.css"
    offenders: list[str] = []
    for path in WEB_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".html", ".scss", ".css"}:
            continue
        patterns = [_CSS_URL] if path == vendored_pico else _ABSOLUTE_URL_PATTERNS
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(1)}")

    assert not offenders, f"absolute URLs found where only relative ones belong: {offenders}"


def test_voxtrama_min_css_exists_and_is_not_empty() -> None:
    css = WEB_ROOT / "static" / "css" / "voxtrama.min.css"
    assert css.is_file(), "run `make css` to generate it"
    assert css.stat().st_size > 0, "voxtrama.min.css exists but is empty"


def test_voxtrama_min_css_is_marked_as_generated() -> None:
    """A loud comment (`/*!`) so the marker survives --style=compressed."""
    css = WEB_ROOT / "static" / "css" / "voxtrama.min.css"
    assert "GENERATED FILE" in css.read_text(encoding="utf-8")
