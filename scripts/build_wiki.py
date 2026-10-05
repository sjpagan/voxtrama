#!/usr/bin/env python3
"""Turn the MkDocs user guide into the pages of the GitHub wiki.

The wiki is a generated mirror of docs/guide/: nobody edits it. One page per
entry of the `nav` in mkdocs.yml, plus `_Sidebar.md` and `_Footer.md`. What
GitHub renders differently from MkDocs is rewritten (links between pages,
image addresses, admonitions, keyboard keys, attribute lists); anything the
script cannot convert makes it fail rather than publish a broken page.

    python scripts/build_wiki.py --out DIR --image-base URL

`--image-base` is the address that `docs/guide/` hangs from, for example
https://raw.githubusercontent.com/<repo>/<sha>, so images stay pinned to a commit.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
INVALID_NAME_CHARS = re.compile(r'[/\\:*?"<>|]')
FOOTER = (
    "This wiki is generated from `docs/guide` in the repository. "
    "Changes go through pull requests there.\n"
)
ALERTS = {
    "tip": "TIP",
    "hint": "TIP",
    "success": "TIP",
    "important": "IMPORTANT",
    "warning": "WARNING",
    "caution": "WARNING",
    "attention": "WARNING",
    "danger": "CAUTION",
    "error": "CAUTION",
    "failure": "CAUTION",
}
KEY_NAMES = {"cmd": "Cmd", "esc": "Esc", "escape": "Esc", "pgup": "Page Up", "pgdn": "Page Down"}

ADMONITION = re.compile(r'^!!!\s+([\w-]+)(?:\s+"(.*)")?\s*$')
UNSUPPORTED = re.compile(r'^\s*(\?\?\?\+?\s|===\s+")')
FENCE = re.compile(r"^(```|~~~)")
LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]*)((?:\s+\"[^\"]*\")?)\)(\{[^{}]*\})?")
KEYS = re.compile(r"\+\+([A-Za-z0-9-]+(?:\+[A-Za-z0-9-]+)*)\+\+")
HEADING_ATTRS = re.compile(r"^(#{1,6}\s.*?)\s*\{:?[^{}]*[=.#:][^{}]*\}\s*$")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+\1")
SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*:|//|/|#)", re.IGNORECASE)


class _Loader(yaml.SafeLoader):
    """SafeLoader that reads `!!python/...` tags (MkDocs configs use them) as plain data."""


_Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)


def load_config(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)


def page_name(title: str) -> str:
    return INVALID_NAME_CHARS.sub("", title.strip()).replace(" ", "-")


def flatten_nav(nav: list, depth: int = 0) -> list[tuple]:
    """Entries as ("page", title, md_path, depth) and ("section", title, None, depth)."""
    entries = []
    for item in nav:
        if isinstance(item, str):
            item = {Path(item).stem.replace("-", " ").capitalize(): item}
        for title, target in item.items():
            if isinstance(target, list):
                entries.append(("section", title, None, depth))
                entries.extend(flatten_nav(target, depth + 1))
            else:
                entries.append(("page", title, posixpath.normpath(target), depth))
    return entries


def page_names(entries: list[tuple]) -> dict[str, str]:
    names: dict[str, str] = {}
    for kind, title, path, _ in entries:
        if kind != "page":
            continue
        name = "Home" if path == "index.md" else page_name(title)
        if name in names.values():
            raise ValueError(f"two nav entries give the wiki page name {name!r}")
        names[path] = name
    return names


def sidebar(entries: list[tuple], names: dict[str, str]) -> str:
    entries = sorted(entries, key=lambda e: e[2] != "index.md") if "index.md" in names else entries
    lines = []
    for kind, title, path, depth in entries:
        indent = "  " * depth
        if kind == "section":
            lines.append(f"{indent}- **{title}**")
        else:
            lines.append(f"{indent}- [{title}]({names[path]})")
    return "\n".join(lines) + "\n"


def convert_admonitions(lines: list[str]) -> list[str]:
    out, i, fence = [], 0, False
    while i < len(lines):
        line = lines[i]
        match = None if fence else ADMONITION.match(line)
        if FENCE.match(line.lstrip()):
            fence = not fence
        if not match:
            out.append(line)
            i += 1
            continue
        kind, title = match.group(1).lower(), match.group(2)
        body, i = [], i + 1
        while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
            body.append(lines[i][4:] if lines[i].strip() else "")
            i += 1
        trailing = 0
        while body and not body[-1]:
            body.pop()
            trailing += 1
        out.append(f"> [!{ALERTS.get(kind, 'NOTE')}]")
        if title:
            out += [f"> **{title}**", ">"]
        out += [f"> {b}" if b else ">" for b in body]
        out += [""] * trailing
    return out


def _key(match: re.Match) -> str:
    keys = [KEY_NAMES.get(k.lower(), k.capitalize()) for k in match.group(1).split("+")]
    return "+".join(f"<kbd>{k}</kbd>" for k in keys)


def _split_code(line: str) -> list[tuple[bool, str]]:
    parts, pos = [], 0
    for span in CODE_SPAN.finditer(line):
        parts += [(False, line[pos : span.start()]), (True, span.group())]
        pos = span.end()
    return parts + [(False, line[pos:])]


def _offset(text: str, match: re.Match) -> int:
    return text.count("\n", 0, match.start())


class Converter:
    def __init__(self, names: dict[str, str], image_base: str, docs_prefix: str) -> None:
        self.names, self.image_base, self.docs_prefix = names, image_base.rstrip("/"), docs_prefix
        self.errors: list[str] = []

    def _link(self, match: re.Match, source: str, lineno: int) -> str:
        bang, text, target, title = match.group(1), match.group(2), match.group(3), match.group(4)
        if SCHEME.match(target) or not target:
            return f"{bang}[{text}]({target}{title})"
        path, _, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        if bang:
            return f"![{text}]({self.image_base}/{self.docs_prefix}/{resolved}{title})"
        if not path.endswith(".md"):
            return f"[{text}]({target}{title})"
        if resolved not in self.names:
            self.errors.append(f"{source}:{lineno}: link to {target} is not a page in the nav")
            return match.group(0)
        return f"[{text}]({self.names[resolved]}{'#' + anchor if anchor else ''}{title})"

    def _inline(self, block: str, source: str, first_line: int) -> str:
        pieces, line = [], first_line
        for is_code, text in _split_code(block):
            if not is_code:
                where = line
                text = LINK.sub(
                    lambda m, w=where, t=text: self._link(m, source, w + _offset(t, m)), text
                )
                text = KEYS.sub(_key, text)
            pieces.append(text)
            line += pieces[-1].count("\n")
        return "".join(pieces)

    def _prose(self, lines: list[str], source: str, first_line: int) -> list[str]:
        """Convert a run of lines outside fences; a link may wrap over several lines."""
        for i, line in enumerate(lines):
            bare = line.lstrip("> ").lstrip()
            if UNSUPPORTED.match(bare):
                self.errors.append(
                    f"{source}:{first_line + i}: unsupported MkDocs syntax: {bare[:20]}"
                )
        lines = [HEADING_ATTRS.sub(r"\1", line) for line in lines]
        return self._inline("\n".join(lines), source, first_line).split("\n")

    def convert(self, text: str, source: str) -> str:
        out, run, start, fence = [], [], 1, False
        for lineno, line in enumerate(convert_admonitions(text.split("\n")), 1):
            if FENCE.match(line.lstrip("> ").lstrip()):
                if not fence:
                    out += self._prose(run, source, start)
                    run = []
                out.append(line)
                fence = not fence
                start = lineno + 1
            elif fence:
                out.append(line)
            else:
                run.append(line)
        return "\n".join(out + self._prose(run, source, start))


def clean(out_dir: Path) -> None:
    for stale in out_dir.glob("*.md"):
        stale.unlink()


def build(config_path: Path, out_dir: Path, image_base: str) -> list[str]:
    config = load_config(config_path)
    root = config_path.parent
    docs_dir = config.get("docs_dir", "docs")
    entries = flatten_nav(config["nav"])
    names = page_names(entries)
    converter = Converter(names, image_base, posixpath.normpath(docs_dir))
    pages = {}
    for path, name in names.items():
        pages[name] = converter.convert((root / docs_dir / path).read_text(encoding="utf-8"), path)
    if converter.errors:
        return converter.errors
    out_dir.mkdir(parents=True, exist_ok=True)
    clean(out_dir)
    for name, body in pages.items():
        (out_dir / f"{name}.md").write_text(body, encoding="utf-8")
    (out_dir / "_Sidebar.md").write_text(sidebar(entries, names), encoding="utf-8")
    (out_dir / "_Footer.md").write_text(FOOTER, encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path, help="wiki checkout to write into")
    parser.add_argument("--image-base", required=True, help="address docs/guide hangs from")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "mkdocs.yml")
    args = parser.parse_args(argv)
    errors = build(args.config, args.out, args.image_base)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
