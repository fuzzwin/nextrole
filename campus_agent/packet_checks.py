"""Executable packet rules. Failed checks hold delivery instead of guessing."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream

from .documents import DOCUMENT_STYLE_VERSION
from .tailor import grounded_cover

RULESET_VERSION = 'packet-rules-v3'


def check_content(job, profile, prepared):
    errors, pending = [], []
    from .role_types import matched_types
    families = matched_types(job)
    allowed_roles = [family['id'] for family in families] or [None]
    if prepared.get('role_type_id') not in allowed_roles:
        errors.append('Application focus does not match the job role type')
    if prepared.get('document_style_version') != DOCUMENT_STYLE_VERSION:
        errors.append('Document style is outdated; regenerate the packet')
    if prepared.get('profile') != profile.model_dump():
        errors.append('Packet profile differs from the current confirmed profile')
    if Counter(prepared.get('skills', [])) != Counter(profile.skills):
        errors.append('Skills were added, removed or changed from the confirmed profile')
    def facts(experiences):
        return Counter((e['organization'], e['role'], e['dates'], b) for e in experiences for b in e['bullets'])
    if facts(prepared.get('experience', [])) != facts([e.model_dump() for e in profile.experience]):
        errors.append('Experience or factual qualifiers differ from the confirmed source')
    if prepared.get('cover_letter') != grounded_cover(job, profile, prepared):
        errors.append('Cover letter differs from the grounded writing rules')
    if prepared.get('job_identity') != job.identity or prepared.get('job_revision') != job.revision:
        errors.append('Packet was prepared for a different or older job listing')
    for label, value in [('title', job.title), ('employer', job.employer)]:
        if re.search(r'[<>\r\n]|https?://|\|\s*(?:LinkedIn|SEEK|Indeed)', value, re.I):
            errors.append(f'Job {label} contains markup or job-board metadata')
        if re.search(r'\b(?:employer on job listing|employer in job alert|unknown|tbd|your company)\b', value, re.I):
            errors.append(f'Job {label} needs confirmation')
    letter = '\n'.join(prepared.get('cover_letter', []))
    if re.search(r'\bI I\b|\[insert[^]]*\]|lorem ipsum|\bTODO\b|\bYOUR NAME\b', letter, re.I):
        errors.append('Cover letter contains a placeholder or repeated pronoun')
    if profile.references_mode == 'named':
        if not profile.referees:
            pending.append('Named referee details are still missing')
        for ref in profile.referees:
            if not ref.sharing_confirmed:
                pending.append(f'Sharing confirmation is missing for referee {ref.name}')
            if not (ref.email or ref.phone) or not (ref.role or ref.organization):
                pending.append(f'Contact or professional details are missing for referee {ref.name}')
            if ref.email and not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', ref.email):
                pending.append(f'Email format needs correction for referee {ref.name}')
    return {'ruleset': RULESET_VERSION, 'passed': not errors, 'delivery_ready': not errors and not pending,
            'errors': errors, 'pending': pending}


def _black_text(reader, page):
    """Follow graphics-state fill colour through text-show operations."""
    colour, stack = (0.0, 0.0, 0.0), []
    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b'q':
            stack.append(colour)
        elif operator == b'Q' and stack:
            colour = stack.pop()
        elif operator == b'rg':
            colour = tuple(float(v) for v in operands)
        elif operator == b'g':
            colour = (float(operands[0]),) * 3
        elif operator == b'k':
            c, m, y, k = map(float, operands)
            colour = (1 - min(1, c + k), 1 - min(1, m + k), 1 - min(1, y + k))
        elif operator in {b'Tj', b'TJ', b"'", b'"'} and any(abs(v) > 0.001 for v in colour):
            return False
    return True


def check_pdfs(directory, job, profile):
    errors, files = [], {}
    for filename, limit in [('Resume.pdf', 3), ('Cover Letter.pdf', 1)]:
        path = directory / filename
        reader = PdfReader(path)
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        files[filename] = {'pages': len(reader.pages), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if not 1 <= len(reader.pages) <= limit:
            errors.append(f'{filename}: exceeds the {limit}-page review limit')
        for page in reader.pages:
            if abs(float(page.mediabox.width) - 595.276) > 1 or abs(float(page.mediabox.height) - 841.89) > 1:
                errors.append(f'{filename}: paper must be A4')
            if not _black_text(reader, page):
                errors.append(f'{filename}: text must be black')
        compact = re.sub(r'\s+', ' ', text)
        if profile.name not in compact or profile.email not in compact:
            errors.append(f'{filename}: candidate identity is missing')
        if filename == 'Cover Letter.pdf' and (job.title.upper() not in compact or job.employer not in compact):
            errors.append('Cover letter employer or role does not match the listing')
        if filename == 'Resume.pdf' and profile.references_mode == 'named':
            for ref in profile.referees:
                if ref.sharing_confirmed and any(value and value not in compact for value in [ref.name, ref.email, ref.phone]):
                    errors.append(f'Resume.pdf: referee details missing for {ref.name}')
        if filename == 'Resume.pdf':
            facts = [profile.summary, *profile.skills, *profile.education,
                     *(b for entry in profile.experience for b in entry.bullets)]
            if any(re.sub(r'\s+', ' ', fact).strip() not in compact for fact in facts):
                errors.append('Resume.pdf: a confirmed fact is missing or changed in the rendered document')
    return {'errors': errors, 'files': files}


def validate_packet(directory, job, profile, prepared, write_report=True):
    report = check_content(job, profile, prepared)
    pdfs = check_pdfs(directory, job, profile)
    report['errors'] += pdfs['errors']
    report['files'] = pdfs['files']
    report['passed'] = not report['errors']
    report['delivery_ready'] = report['passed'] and not report['pending']
    if write_report:
        (directory / 'quality-report.json').write_text(json.dumps(report, indent=2))
    return report


def require_delivery(directory, job, profile):
    path = directory / 'tailoring.json'
    if not path.is_file():
        raise ValueError('Packet quality evidence is missing; prepare this packet again')
    prepared = json.loads(path.read_text())
    report = validate_packet(directory, job, profile, prepared)
    if not report['delivery_ready']:
        raise ValueError('Packet held by quality rules: ' + '; '.join(report['errors'] + report['pending']))
    saved = prepared.get('artifact_hashes', {})
    if saved != {name: info['sha256'] for name, info in report['files'].items()}:
        raise ValueError('Packet PDFs changed after preparation; regenerate before delivery')
    return report
