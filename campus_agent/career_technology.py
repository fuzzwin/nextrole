"""Collect and render literal technology evidence with its original scope."""

import re

from .fit import TOOLS

LABELS = {
    'vacancy': 'Named in this vacancy',
    'related': 'Related posting',
    'company': 'Company context',
    'candidate': 'Your experience',
}
KINDS = {'related': 'related_posting', 'company': 'company_example', 'candidate': 'candidate'}
ASK = 'Which systems, devices and access would I use on the first workflow or assignment?'

_EXTRA = re.compile(
    r'\b(?:AWS|Amazon Web Services|Microsoft Fabric|Databricks|Snowflake|SAP|Salesforce|'
    r'Google Cloud|GCP|Oracle Sales Cloud|Microsoft Copilot|APIs?|MCP|company[- ]provided equipment|endpoint management|'
    r'ticketing system|operating system|hardware (?:support|troubleshooting)|'
    r'Lean|Six Sigma|process mining|service design|ITIL)\b', re.I,
)


def _key(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def _terms(text):
    found = {_key(m[0]) for m in _EXTRA.finditer(text)}
    for name, pattern in TOOLS.items():
        if name in {'Azure development', 'Exchange', 'REST APIs', 'React'}:
            continue
        found.update(_key(match[0]) for match in re.finditer(pattern, text, re.I))
    return found


def _passages(quotes, scope):
    for quote in quotes:
        quote = ' '.join(quote.split())
        if scope in {'vacancy','related'} and len(quote.split())>25:
            yield from re.split(r'(?<=[.!?]) +(?=[A-Z])', quote)
        elif scope!='company' or not re.search(r'\b(?:startup fund|venture fund|investment round|investors?|valuation|fundrais\w*)\b',quote,re.I):
            yield quote


def technology_rows(quotes, scope, source, limit=3, relevant=None):
    """Keep complete short passages, preserving qualifications and alternatives."""
    result = []
    seen = set()
    quotes = _passages(quotes, scope)
    if scope in {'related', 'company'}:
        quotes = sorted(quotes, key=lambda quote: -len(_terms(quote)-{'api','apis','mcp'}))
    for quote in quotes:
        terms = _terms(quote)
        if relevant is not None:
            terms &= relevant
        if not terms-seen or len(quote.split()) > 25:
            continue
        result.append({'scope': scope, 'source': source, 'quote': quote})
        seen.update(terms)
        if len(result) == limit:
            break
    return result


def add_candidate_technology(report, sources):
    from .fit import positive_evidence

    rows = report['technology']
    relevant = {name for row in rows for name in _terms(row['quote'])}
    if not relevant:
        return
    for ref, source in sources.items():
        if not ref.startswith('experience_') or not positive_evidence(source['excerpt']):
            continue
        matches = technology_rows([source['excerpt']], 'candidate', ref, relevant=relevant)
        if matches:
            rows.extend(matches)
            return


def technology_lines(report, sources, compact=False):
    if 'technology' not in report:
        return []
    rows = report['technology']
    if compact:
        by_scope = {scope: next((row for row in rows if row['scope']==scope), None) for scope in LABELS}
        rows = [row for row in by_scope.values() if row][:2]
    lines = ['## Possible technology stack']
    if not rows:
        lines.append('Stack details remain open.')
    for entry in rows:
        source = sources.get(entry['source'], {})
        label = LABELS.get(entry['scope'], 'Source needs review')
        ref = source.get('url')
        link = f"[{source.get('label') or 'Source'}]({ref})" if ref else f"[{entry['source']}]"
        lines.append(f"- **{label}** {entry['quote']} {link}")
    if not compact:
        lines.extend('- **Source needs review** '+note for note in report.get('technology_notes', []))
    lines.append(f"- **Ask to confirm** {ASK}")
    return lines


def check_technology(report, sources):
    findings = []
    for entry in report.get('technology', []):
        ref, scope = entry['source'], entry['scope']
        source = sources.get(ref, {})
        valid = ref == 'advert' if scope == 'vacancy' else scope in KINDS and source.get('kind') == KINDS[scope]
        quote = _key(entry['quote'])
        evidence = _key(source.get('excerpt', ''))
        if not valid or not quote or f' {quote} ' not in f' {evidence} ':
            findings.append('Technology entries need a source of the stated scope and a matching passage.')
    return findings
