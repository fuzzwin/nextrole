"""Private, evidence-preserving career guide exports; no network or model calls."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .documents import font_names

INVALID_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


def _markup(text: str) -> str:
    return escape(INVALID_XML.sub(' ', text))


def _plain(text: str) -> str:
    # Retain citation destinations, even in readers that do not follow hyperlinks.
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    return re.sub(r'(\*\*|__|`)', '', text).strip()


def _blocks(markdown: str):
    """Small deliberately non-executing Markdown subset, preserving all text."""
    paragraph = []
    for raw in markdown.splitlines():
        line = raw.strip()
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        bullet = re.match(r'^(?:[-*+]\s+|\d+[.)]\s+)(.*)', line)
        if not line or heading or bullet:
            if paragraph:
                yield 'body', _plain(' '.join(paragraph))
                paragraph = []
            if heading:
                yield 'heading', _plain(heading[2])
            elif bullet:
                yield 'bullet', _plain(bullet[1])
        elif line not in ('---', '```'):
            paragraph.append(line)
    if paragraph:
        yield 'body', _plain(' '.join(paragraph))


def _pdf(path: Path, title: str, content: str, notice: str):
    regular, bold = font_names()
    styles = {
        'title': ParagraphStyle('CareerTitle', fontName=bold, fontSize=17, leading=21, spaceAfter=9, textColor=colors.black),
        'heading': ParagraphStyle('CareerHeading', fontName=bold, fontSize=11, leading=14, spaceBefore=8, spaceAfter=4, keepWithNext=True),
        'body': ParagraphStyle('CareerBody', fontName=regular, fontSize=10, leading=13, spaceAfter=5, splitLongWords=True, alignment=TA_LEFT),
        'bullet': ParagraphStyle('CareerBullet', fontName=regular, fontSize=10, leading=13, leftIndent=10, firstLineIndent=-7, spaceAfter=4),
    }
    story = [Paragraph(_markup(title), styles['title']), Paragraph(_markup(notice), styles['body']), Spacer(1, 3 * mm)]
    for kind, text in _blocks(content):
        story.append(Paragraph(('• ' if kind == 'bullet' else '') + _markup(text), styles[kind]))
    def footer(canvas, doc):
        canvas.setFont(regular, 8)
        canvas.drawString(18 * mm, 12 * mm, 'NextRole · Career preparation · Verify evidence before use')
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=20 * mm, title=title, author='NextRole').build(story, onFirstPage=footer, onLaterPages=footer)


def _docx(path: Path, title: str, content: str, notice: str):
    # Standard OOXML keeps this editable without a new runtime dependency.
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def para(text, style='Normal'):
        return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{_markup(text)}</w:t></w:r></w:p>'
    body = para(title, 'Title') + para(notice)
    for kind, text in _blocks(content):
        body += para(('• ' if kind == 'bullet' else '') + text, 'Heading1' if kind == 'heading' else 'Normal')
    body += '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="907" w:right="1021" w:bottom="1134" w:left="1021"/></w:sectPr>'
    styles = f'''<w:styles xmlns:w="{ns}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="20"/><w:color w:val="000000"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="260" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val="34"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style></w:styles>'''
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>')
        z.writestr('word/styles.xml', styles)
        z.writestr('word/_rels/document.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')


def export_run(directory: str | Path, run: dict) -> dict[str, str]:
    """Export supplied result text only, staging all four outputs before publishing.

    Caller supplies a private per-run directory. A too-long quicksheet is rejected,
    never silently clipped or shrunk to unreadable type.
    """
    result = run.get('result') or {}
    markdown = result.get('markdown', '')
    quick = result.get('quick_markdown') or result.get('quick_sheet', '')
    if not isinstance(markdown, str) or not markdown.strip() or not isinstance(quick, str) or not quick.strip():
        raise ValueError('Both guide markdown and quick_markdown are required for export.')
    title = str(result.get('title') or run.get('title') or 'Career opportunity guide')
    notice = 'Draft preparation material. Check source evidence and personal claims before use.'
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    names = {'guide_docx': 'career-guide.docx', 'guide_pdf': 'career-guide.pdf',
             'quick_docx': 'career-quicksheet.docx', 'quick_pdf': 'career-quicksheet.pdf'}
    with tempfile.TemporaryDirectory(prefix='.career-export-', dir=directory) as tmp:
        stage = Path(tmp)
        for stem, content, label in [('guide', markdown, title), ('quick', quick, title + ' — quicksheet')]:
            _docx(stage / names[stem + '_docx'], label, content, notice)
            _pdf(stage / names[stem + '_pdf'], label, content, notice)
        if len(PdfReader(stage / names['quick_pdf']).pages) > 2:
            raise ValueError('Quicksheet exceeds two readable pages; shorten its content before exporting.')
        for name in names.values():
            (stage / name).replace(directory / name)
    return {key: str(directory / name) for key, name in names.items()}
