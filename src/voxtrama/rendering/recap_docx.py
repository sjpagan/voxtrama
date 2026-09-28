"""The recap as a Word document: the smallest valid .docx, by hand.

A .docx is a zip of a few XML parts (ECMA-376). Four are enough for text
with a title, headings and bullets: the content types, the package
relationships, the document and its styles. Written with zipfile and an
XML escape instead of a dependency: the recap is a handful of paragraphs,
and the three formats must stay installable anywhere the app runs (the
same reasoning the page itself follows).
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

from voxtrama.rendering.recap_document import Block

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_PACKAGE = "http://schemas.openxmlformats.org/package/2006"
_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml"

_CONTENT_TYPES = (
    f'{_HEAD}<Types xmlns="{_PACKAGE}/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    f'<Override PartName="/word/document.xml" ContentType="{_WORD}.document.main+xml"/>'
    f'<Override PartName="/word/styles.xml" ContentType="{_WORD}.styles+xml"/>'
    "</Types>"
)


def _relationship(kind: str, target: str) -> str:
    return (
        f'{_HEAD}<Relationships xmlns="{_PACKAGE}/relationships">'
        f'<Relationship Id="rId1" Type="{_OFFICE}/{kind}" Target="{target}"/></Relationships>'
    )


_PACKAGE_RELS = _relationship("officeDocument", "word/document.xml")
_DOCUMENT_RELS = _relationship("styles", "styles.xml")


def _style(style_id: str, name: str, size: int, bold: bool, color: str = "000000") -> str:
    weight = "<w:b/>" if bold else ""
    return (
        f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/>'
        f'<w:pPr><w:spacing w:before="120" w:after="80"/></w:pPr>'
        f'<w:rPr>{weight}<w:color w:val="{color}"/><w:sz w:val="{size}"/></w:rPr></w:style>'
    )


_STYLES = (
    f'{_HEAD}<w:styles xmlns:w="{_W}">'
    + _style("Normal", "Normal", 22, False)
    + _style("Title", "Title", 40, True)
    + _style("Heading1", "heading 1", 28, True)
    + _style("Subtitle", "Subtitle", 18, False, "666666")
    + "</w:styles>"
)

_STYLE_OF = {"title": "Title", "meta": "Subtitle", "heading": "Heading1", "note": "Subtitle"}


def _paragraph(block: Block) -> str:
    text = escape(block.text)
    if block.kind == "bullet":
        return (
            '<w:p><w:pPr><w:ind w:left="360" w:hanging="240"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">•\t{text}</w:t></w:r></w:p>'
        )
    style = _STYLE_OF.get(block.kind, "Normal")
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def recap_docx(blocks: list[Block]) -> bytes:
    """The .docx file's bytes."""
    body = "".join(_paragraph(block) for block in blocks)
    document = f'{_HEAD}<w:document xmlns:w="{_W}"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _CONTENT_TYPES)
        package.writestr("_rels/.rels", _PACKAGE_RELS)
        package.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        package.writestr("word/document.xml", document)
        package.writestr("word/styles.xml", _STYLES)
    return buffer.getvalue()
