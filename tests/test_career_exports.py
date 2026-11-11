from pathlib import Path
from zipfile import ZipFile
import pytest
from pypdf import PdfReader
from campus_agent.career_exports import export_run


def sample():
    return {'result': {'title': 'Community coordinator — Example Org', 'markdown': '# Role evidence\nPay: not stated. Checked 10 November 2026.\n\n[Employer source](https://example.org/role)\n\n# Interview practice\n- Proposed approach, not past experience: consult the team.\n- Cue: pause → evidence → outcome.\n- Unconfirmed: interview time.\n\nLiteral <b>markup</b> & evidence.', 'quick_markdown': '# Three reminders\n- Confirm the pay basis.\n- Use only supported examples.\n- Ask about team priorities.\n\nSource: https://example.org/role\nUnconfirmed: interview time.'}}


def test_exports_preserve_evidence_and_uncertainty(tmp_path):
    paths = export_run(tmp_path, sample())
    assert set(paths) == {'guide_docx', 'guide_pdf', 'quick_docx', 'quick_pdf'}
    pdf = PdfReader(paths['guide_pdf'])
    text = '\n'.join(p.extract_text() for p in pdf.pages)
    links = [a.get_object()['/A']['/URI'] for page in pdf.pages for a in page.get('/Annots', [])]
    assert links == ['https://example.org/role']
    for phrase in ['not stated', '10 November 2026', 'https://example.org/role', 'Proposed approach, not past experience', 'Unconfirmed: interview time', '<b>markup</b> & evidence']:
        assert phrase in text
    with ZipFile(paths['guide_docx']) as z:
        xml = z.read('word/document.xml').decode()
        assert 'https://example.org/role' in xml
        assert '&lt;b&gt;markup&lt;/b&gt; &amp; evidence' in xml
        assert 'Proposed approach, not past experience' in xml
        assert 'w:styleId="Title"' in z.read('word/styles.xml').decode()
    assert 1 <= len(PdfReader(paths['quick_pdf']).pages) <= 2


def test_oversize_quick_sheet_does_not_publish_partial_exports(tmp_path):
    run = sample()
    run['result']['quick_markdown'] = '\n'.join('- Evidence example ' + str(i) + ': confirm source and do not claim unverified experience.' for i in range(200))
    with pytest.raises(ValueError, match='two readable pages'):
        export_run(tmp_path, run)
    assert list(tmp_path.iterdir()) == []


def test_missing_content_is_not_exported(tmp_path):
    with pytest.raises(ValueError, match='required'):
        export_run(tmp_path, {'result': {'markdown': 'No quicksheet'}})
    assert not list(tmp_path.iterdir())
