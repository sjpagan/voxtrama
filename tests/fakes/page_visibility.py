"""Splits a rendered page's own text into what a person would see
and what sits inside a closed `<details>` (a defect found once: a page can
expose a control that only exists inside a disclosure widget nobody has a
reason to open).

Stdlib only, the same choice providers/http.py explains for itself: this
project does not add an HTML-parsing dependency for one test's sake.
"""

from __future__ import annotations

from html.parser import HTMLParser


class VisibilityWalker(HTMLParser):
    """Tags text as hidden while inside any `<details>` lacking `open`."""

    def __init__(self) -> None:
        super().__init__()
        self._closed_stack: list[bool] = []
        self.visible_chunks: list[str] = []
        self.hidden_chunks: list[str] = []

    @property
    def _hidden(self) -> bool:
        return any(self._closed_stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "details":
            is_open = any(name == "open" for name, _ in attrs)
            self._closed_stack.append(not is_open)

    def handle_endtag(self, tag: str) -> None:
        if tag == "details" and self._closed_stack:
            self._closed_stack.pop()

    def handle_data(self, data: str) -> None:
        (self.hidden_chunks if self._hidden else self.visible_chunks).append(data)


def visible_text(html: str) -> str:
    """Everything in `html` a person sees without opening a closed `<details>`."""
    walker = VisibilityWalker()
    walker.feed(html)
    return "".join(walker.visible_chunks)


def hidden_text(html: str) -> str:
    """Everything in `html` that only a closed `<details>` holds."""
    walker = VisibilityWalker()
    walker.feed(html)
    return "".join(walker.hidden_chunks)
