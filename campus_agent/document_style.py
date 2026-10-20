"""Small, explicit document choices; never instructions to invent or omit facts."""
from __future__ import annotations
import hashlib
import json
from typing import Literal
from .models import StrictModel


class DocumentStyle(StrictModel):
    layout: Literal['classic', 'compact', 'comfortable'] = 'classic'
    resume_pages: Literal[2, 3] = 3
    tone: Literal['professional', 'warm', 'direct'] = 'professional'
    letter_length: Literal['standard', 'brief'] = 'standard'
    fact_order: Literal['relevant', 'original'] = 'relevant'


def style_fingerprint(profile, style):
    from .documents import DOCUMENT_STYLE_VERSION
    from .packet_checks import RULESET_VERSION
    data = {'profile': profile.model_dump() if profile else None,
            'style': style.model_dump(), 'review_engine': 'rendered-pages-v1', 'document_engine': DOCUMENT_STYLE_VERSION,
            'ruleset': RULESET_VERSION}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


# PDFium calls are serialized; sample PDFs are generated locally by ReportLab.
import threading
PDF_RENDER_LOCK = threading.Lock()


def render_sample_pages(directory):
    import pypdfium2 as pdfium
    counts = {}
    with PDF_RENDER_LOCK:
        for kind, name in [('resume', 'Resume.pdf'), ('cover', 'Cover Letter.pdf')]:
            pdf = pdfium.PdfDocument(str(directory / name))
            try:
                counts[kind] = len(pdf)
                for index in range(len(pdf)):
                    page = pdf[index]
                    try:
                        bitmap = page.render(scale=1.5)
                        try:
                            with bitmap.to_pil() as picture:
                                picture.save(directory / f'{kind}-page-{index + 1}.png')
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
            finally:
                pdf.close()
    return counts
