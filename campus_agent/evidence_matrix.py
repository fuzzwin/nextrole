"""Source-preserving requirement matrix shared by both evidence review methods."""
import re

from .listing_view import HEADINGS, heading_key, requirement_heading

VERSION = 'source-matrix-v1'


def _key(text):
    return heading_key(text).replace('&', 'and')


def section_kind(heading):
    key = _key(heading)
    if re.search(r'benefits|what we offer|company|about us|who we are|recruitment|how to apply|join or sign|base pay|compensation', key):
        return 'excluded'
    if re.search(r'desirable|preferred|nice to have|bonus|highly regarded|helpful.*not required', key):
        return 'optional'
    if re.search(r'responsibilit|duties|what you.{0,8}(?:do|own)|your (?:role|impact)|in this role|focus of the role|core to the role|the opportunity|about the role', key):
        return 'duty'
    if (requirement_heading(heading) or re.search(
            r'requirement|qualification|skills|experience|selection criteria|about you|what (?:you|we).{0,16}(?:bring|need|looking)|your (?:profile|background)|essential|must have|successful', key)):
        return 'requirement'
    return 'context'


# Document structure and statement polarity are classified before evidence matching.
# These expressions describe source functions, rather than particular occupations.
ADMIN = re.compile(
    r'^(?:apply\b|how to apply\b|to apply\b|resume required\b|résumé required\b|'
    r'when you contact us\b|please (?:apply|contact|submit|indicate)\b|'
    r'by submitting\b|follow (?:the|this) link\b|(?:source|url|link)\s*:|'
    r'create a job alert\b|(?:you must )?(?:create|register for) (?:an? )?[^.!?]{0,50}\baccount\b[^.!?]{0,100}\bapply\b|'
    r'(?:the successful candidate|you) will participate in a comprehensive onboarding, training and development program\b|'
    r'https?://|join or sign in\b|ignore (?:the|all|previous)\b|give (?:the )?candidate\b)', re.I)
CONDITION = re.compile(
    r'^(?:work mode\b|work (?:arrangement|location)\b|location\s*:|salary\b|'
    r'(?:excellent|competitive|attractive) (?:salary|remuneration|package)\b|'
    r'(?:(?:the (?:role|position) is |(?:you )?(?:must|will) be )?(?:based|located) (?:onshore )?(?:in|at)\b)|'
    r'reliable (?:internet|internet connection)\b|(?:own|your own) (?:computer|equipment)\b|'
    r'(?:a )?(?:current|valid) driver[’\']?s licen[cs]e\b|'
    r'(?:must (?:have|hold|be)|current|hold|have|eligible for|eligibility for)?\s*'
    r'(?:(?:permanent[, ]+)?unrestricted )?'
    r'(?:Australian citizenship|Australian citizen|right to work|working rights|work rights|AGSVA|NV[12]|security clearance)\b)', re.I)
UNNECESSARY = re.compile(
    r'\b(?:not required|not necessary|not needed|no .{0,60}(?:needed|required)|without requiring)\b', re.I)
PREFERRED = re.compile(r'^bonus\s*:|\b(?:preferred|desirable|an advantage|advantageous|highly regarded|nice to have|is a plus|would be beneficial)\b', re.I)
EXPLICIT = re.compile(
    r'^(?:must|minimum|at least|requires?|you (?:need|must|will)|demonstrated|proven|'
    r'ability|experience|strong|excellent|working knowledge|hands.on|'
    r'coordinate|facilitate|assist|organise|organize|provide|develop|design|build|maintain|'
    r'administer|improve|ensure|lead|collaborate|deliver|implement|create|monitor|'
    r'troubleshoot|resolve|conduct|engage|analyse|analyze|identify)\b', re.I)
KNOWN_HEADINGS = {_key(heading) for heading in HEADINGS} | {
    'skills and experience', 'your responsibilities', 'skills', 'what is the focus of the role',
}
OPTIONAL_HEADING = re.compile(r'(?:desirable|preferred|optional|bonus) (?:certifications|qualifications|credentials|skills|experience)')


def matrix_requirements(view):
    """Capture all explicit duties/requirements with source text and section provenance.

    Keep AND/OR groups intact. Splitting them by keywords can remove common
    qualifiers or turn alternatives into multiple mandatory obligations.
    """
    rows = []
    seen = {}
    for section_index, section in enumerate(view.get('sections', [])):
        heading = section.get('title') or section.get('heading', '')
        category = section_kind(heading)
        for block_index, block in enumerate(section['blocks']):
            texts = [block['text']] if block['kind'] == 'paragraph' else block['items']
            for item_index, original in enumerate(texts):
                text = original.strip()
                key = _key(text)
                inline_heading = (len(text) < 90 and not re.search(r'[.!?]', text)
                                  and re.match(r'^(?:key|core|your|our|what|who|skills|requirements|qualifications|responsibilities|duties|we.re looking for|you.ll bring)\b', key)
                                  and section_kind(text) != 'context')
                if OPTIONAL_HEADING.fullmatch(key):
                    heading, category = text, 'optional'
                    continue
                if len(text) < 110 and (key in KNOWN_HEADINGS or inline_heading):
                    heading, category = text, section_kind(text)
                    continue
                if len(text) < 12:
                    continue
                # Ignore source navigation and explicit instructions to the scorer.
                kind = 'competency'
                importance = 'standard'
                reason = ''
                if ADMIN.search(text):
                    kind, reason = 'administrative', 'Application, source or navigation text.'
                elif CONDITION.search(text):
                    kind, reason = 'condition', 'Confirm logistics or eligibility separately.'
                elif UNNECESSARY.search(text) and not PREFERRED.search(text):
                    if re.search(r'\bbut\b|\bhowever\b|;', text, re.I):
                        kind, reason = 'review', 'Positive and negative requirement scope share this clause.'
                    else:
                        kind, reason = 'administrative', 'The advert explicitly says this is unnecessary.'
                elif category == 'excluded':
                    continue
                elif category == 'context' and not EXPLICIT.search(text):
                    continue
                elif (block['kind'] == 'paragraph' and not EXPLICIT.search(text)
                      and not (category in {'requirement', 'optional'} and re.search(r'\b(?:experience|knowledge|certification|qualification)\b', text, re.I))):
                    continue
                if category == 'optional' or PREFERRED.search(text):
                    importance = 'optional'
                elif re.search(r'\b(?:must|required|essential|mandatory|minimum)\b', heading + ' ' + text, re.I):
                    importance = 'essential'
                # A mixed required/preferred clause needs an explicit human decision.
                mixed = bool((PREFERRED.search(text) or category == 'optional') and re.search(
                    r'\b(?:must|required|essential)\b|,\s*with\b', text, re.I))
                if mixed and kind == 'competency':
                    kind, reason = 'review', 'Mandatory and preferred scope share this source clause.'
                normalized = re.sub(r'\W+', ' ', text.casefold()).strip()
                identity = (normalized, kind)
                if identity in seen:
                    previous = rows[seen[identity]]
                    # A repeated essential version must not lose its stronger weight.
                    if importance == 'essential':
                        previous['importance'] = importance
                    previous['source_locations'].append([section_index, block_index, item_index])
                    continue
                seen[identity] = len(rows)
                logic = 'any' if re.search(r'\bor\b', text, re.I) else 'all' if re.search(r'\band\b|;', text, re.I) else 'single'
                rows.append({'id': str(len(rows)), 'text': text, 'quote': text,
                             'heading': heading, 'category': category, 'kind': kind,
                             'importance': importance, 'logic': logic, 'review_reason': reason,
                             'source_locations': [[section_index, block_index, item_index]]})
    return rows


def summarise_matrix(requirements):
    scored = [row for row in requirements if row['kind'] == 'competency' and row['importance'] != 'optional']
    return {
        'version': VERSION, 'scored': len(scored),
        'duties': sum(row.get('category') == 'duty' for row in scored),
        'essential': sum(row['importance'] == 'essential' for row in scored),
        'optional': sum(row['kind'] == 'competency' and row['importance'] == 'optional' for row in requirements),
        'conditions': sum(row['kind'] == 'condition' for row in requirements),
        'administrative': sum(row['kind'] == 'administrative' for row in requirements),
        'needs_review': sum(row['kind'] == 'review' for row in requirements),
        'compound': sum(row.get('logic') == 'all' for row in scored),
    }


def unconfirmed_group_scope(requirement, evidence):
    """Flag residual obligations in a proposed fully supported AND/list group.

    This is a conservative literal cross-check. It may flag equivalent wording,
    so the outcome is partial/review, never a conclusion that the person cannot do it.
    """
    if requirement.get('logic') != 'all':
        return []
    from .fit import unsupported_clauses
    return unsupported_clauses(requirement['text'], evidence)
