"""Candidate profile facts for each advert criterion.

This ranks saved facts by shared wording so the reviewer can find them quickly.
It never grades a criterion: a suggestion is a pointer for the person to check,
and the reviewed-fit guards in transfer_fit still apply when a review is saved.
"""
from __future__ import annotations

import math
import re

from . import semantic

VERSION = 'evidence-suggest-v1'

# Words that say nothing about the kind of work, in adverts or in résumé bullets.
GENERIC = set('''a an and are as at be been by can for from had has have in into is it its of on or our that the their this to
was were will with within you your we us they them he she his her i my who which what when where while than then also etc
experience experienced demonstrated demonstrable proven strong excellent good sound solid high highly ability able capable
skills skill knowledge understanding working work worked role roles position duties responsibilities responsible including include
includes required requirement requirements essential desirable preferred minimum least current currently relevant related similar
appropriate effective effectively successfully well must may should would across per using use used various other all any each
both more most new take part ensure ensuring provide providing support supporting help helping assist assisting join joining
year years month months day days time times level one two three four five six seven eight nine ten first line policy
safely safe busy team teams member members staff people person environment
manage managed managing management system systems process processes'''.split())

IRREGULAR = {'led': 'lead', 'ran': 'run', 'built': 'build', 'wrote': 'write', 'written': 'write', 'taught': 'teach',
             'sold': 'sell', 'bought': 'buy', 'kept': 'keep', 'held': 'hold', 'met': 'meet', 'drove': 'drive',
             'driven': 'drive', 'grew': 'grow', 'grown': 'grow', 'made': 'make', 'oversaw': 'oversee',
             'undertook': 'undertake', 'won': 'win', 'dealt': 'deal', 'gave': 'give', 'given': 'give'}


def stem(word):
    """Small suffix stripper: enough to line up 'precepted' with 'precept' and 'rostering' with 'roster'."""
    word = IRREGULAR.get(word, word)
    for suffix, replacement in (('isation', 'ise'), ('ization', 'ise'), ('ations', 'ate'), ('ation', 'ate'),
                                ('ments', ''), ('ment', ''), ('ities', 'ity'), ('ies', 'y'), ('ing', ''),
                                ('ed', ''), ('es', ''), ('s', '')):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[:len(word) - len(suffix)] + replacement
            break
    # 'administer' / 'administration', 'assess' / 'assessment', 'manage' / 'managed' share a five-letter-plus root.
    return word[:-1] if len(word) > 5 and word.endswith('e') else word


def terms(text):
    """Map each content stem to the first original word that produced it."""
    found = {}
    for word in re.findall(r"[a-z][a-z'+#.-]*[a-z+#]|[a-z]", text.lower()):
        word = word.strip(".'-")
        if len(word) < 3 or word in GENERIC:
            continue
        found.setdefault(stem(word), word)
    return found


def suggest(requirements, profile, limit=3):
    """Return {criterion id: [candidate facts]} ordered by shared distinctive wording."""
    facts = semantic.facts_from_profile(profile)
    indexed = [(fact, terms(fact['text'])) for fact in facts]
    frequency = {}
    for _, words in indexed:
        for key in words:
            frequency[key] = frequency.get(key, 0) + 1
    total = max(len(indexed), 1)
    weight = lambda key: 1 + math.log(total / frequency[key])
    result = {}
    for requirement in requirements:
        source = requirement.get('text') or requirement.get('quote') or ''
        wanted = terms(source)
        # A licence or registration is evidenced by a saved credential or qualification, not by a work bullet.
        formal = credential_like(source)
        ranked = []
        for fact, words in indexed:
            if formal and fact['kind'] not in {'credential', 'education'}:
                continue
            shared = [key for key in wanted if key in words]
            if not shared:
                continue
            score = sum(weight(key) for key in shared)
            # One shared word is only a pointer when the wording is specific to few facts.
            if len(shared) == 1 and frequency[shared[0]] > max(2, total // 4):
                continue
            # A work bullet says more than a bare skill label that repeats the same words.
            if fact['kind'] == 'work':
                score *= 1.15
            ranked.append((score, fact, shared))
        ranked.sort(key=lambda item: (-item[0], item[1]['id']))
        # Keep only candidates in the same league as the best one, so weak single-word echoes drop away.
        ranked = [item for item in ranked if item[0] >= ranked[0][0] * 0.5]
        result[requirement['id']] = [
            {'id': fact['id'], 'text': fact['text'], 'role': fact['role'], 'organisation': fact['organisation'],
             'kind': fact['kind'], 'matched': sorted(wanted[key] for key in shared)}
            for _, fact, shared in ranked[:limit]]
    return result


def credential_like(text):
    """True when a criterion reads as a licence, registration or check that belongs under saved credentials."""
    return bool(re.search(r'\b(?:registration|registered|licen[cs]e|certificate|certification|certified|accreditation|'
                          r'working with children|police check|clearance|permit|ticket|white card)\b', text, re.I))
