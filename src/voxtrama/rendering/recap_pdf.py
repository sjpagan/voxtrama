"""The recap as a PDF: text only, laid out by hand.

A PDF of paragraphs needs little: pages, the two standard Helvetica fonts
every reader carries (so nothing is embedded), and lines broken to the
page width. Widths are Helvetica's metrics (Adobe AFM, 1/1000 em). Text
is encoded as WinAnsi (cp1252), which covers Western European languages.
A character outside it prints as «?», a limit stated here instead of
hidden. See rendering.recap_docx for why this is not a dependency.
"""

from __future__ import annotations

from voxtrama.rendering.recap_document import Block

_PAGE_W, _PAGE_H, _MARGIN = 595, 842, 56
_WIDTHS = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 "
    "556 556 556 556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 "
    "556 833 722 778 667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 "
    "556 500 556 556 278 556 556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 "
    "500 500 500 334 260 334 584"
)
_WIDTH = {chr(32 + index): int(width) for index, width in enumerate(_WIDTHS.split())}
# (font, size, grey, space before) per block kind. F2 is the bold face.
_LOOK = {
    "title": ("F2", 20, 0.0, 0),
    "meta": ("F1", 9, 0.4, 4),
    "heading": ("F2", 14, 0.0, 16),
    "bullet": ("F1", 11, 0.0, 4),
    "note": ("F1", 8, 0.45, 4),
}


def _width(text: str, size: int) -> float:
    return sum(_WIDTH.get(char, 556) for char in text) * size / 1000


def _wrap(text: str, size: int, room: float) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and _width(candidate, size) > room:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines


def _literal(text: str) -> str:
    raw = text.encode("cp1252", errors="replace").decode("latin-1")
    return raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pages(blocks: list[Block]) -> list[list[str]]:
    """Each page as its content-stream operators."""
    pages: list[list[str]] = [[]]
    y = _PAGE_H - _MARGIN
    for block in blocks:
        font, size, grey, before = _LOOK[block.kind]
        indent = 14 if block.kind == "bullet" else 0
        y -= before
        for number, line in enumerate(_wrap(block.text, size, _PAGE_W - 2 * _MARGIN - indent)):
            if y - size < _MARGIN:
                pages.append([])
                y = _PAGE_H - _MARGIN
            y -= size * 1.3
            text = f"• {line}" if block.kind == "bullet" and number == 0 else line
            x = _MARGIN + (indent if number or block.kind != "bullet" else 4)
            pages[-1].append(
                f"BT /{font} {size} Tf {grey} g {x:.1f} {y:.1f} Td ({_literal(text)}) Tj ET"
            )
    return pages


def recap_pdf(blocks: list[Block]) -> bytes:
    """The PDF file's bytes."""
    pages = _pages(blocks)
    count = len(pages)
    kids = " ".join(f"{5 + 2 * index} 0 R" for index in range(count))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    for index, operators in enumerate(pages):
        stream = "\n".join(operators).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {6 + 2 * index} 0 R >>"
        )
        content = stream.decode("latin-1")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{content}\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    trailer = f"<< /Size {len(objects) + 1} /Root 1 0 R >>"
    out += f"trailer\n{trailer}\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
