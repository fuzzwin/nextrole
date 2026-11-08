"""Sector-neutral wording helpers shared by scoring and letter writing.

Nothing here knows about a particular profession: it only recognises that a
bullet begins with something the candidate did, and folds inflections together.
"""
from __future__ import annotations

import re

# Irregular forms folded to a base verb so "led" meets "leading" and "made" meets "making".
IRREGULAR = {
    'led': 'lead', 'leading': 'lead', 'made': 'make', 'making': 'make', 'ran': 'run', 'running': 'run',
    'built': 'build', 'building': 'build', 'taught': 'teach', 'teaching': 'teach', 'kept': 'keep',
    'keeping': 'keep', 'held': 'hold', 'holding': 'hold', 'sold': 'sell', 'selling': 'sell',
    'wrote': 'write', 'written': 'write', 'writing': 'write', 'drove': 'drive', 'driving': 'drive',
    'took': 'take', 'taking': 'take', 'gave': 'give', 'giving': 'give', 'found': 'find', 'finding': 'find',
    'paid': 'pay', 'sent': 'send', 'sending': 'send', 'spoke': 'speak', 'met': 'meet', 'meeting': 'meet',
    'dealt': 'deal', 'dealing': 'deal', 'set': 'set', 'put': 'put', 'cut': 'cut', 'cutting': 'cut',
    'wore': 'wear', 'laid': 'lay', 'laying': 'lay', 'fitted': 'fit', 'fitting': 'fit',
}

# Past-tense work verbs that are not -ed words, or that start a bullet but do not show delivery.
IRREGULAR_PAST = {
    'led', 'made', 'ran', 'built', 'taught', 'kept', 'held', 'sold', 'wrote', 'drove', 'took', 'gave',
    'found', 'paid', 'sent', 'spoke', 'met', 'dealt', 'set', 'put', 'cut', 'laid', 'fitted', 'lead',
    'wrote', 'write', 'run', 'build', 'teach', 'make', 'drive', 'serve', 'served', 'sell', 'cook', 'cooked',
    'bake', 'baked', 'weld', 'welded', 'nursed', 'cared', 'treat', 'treated',
}

# Starting verbs that describe attendance, study or exposure rather than doing the work.
WEAK_STARTS = {
    'attended', 'observed', 'shadowed', 'exposed', 'introduced', 'learned', 'learnt', 'studied', 'enrolled',
    'interested', 'aspired', 'familiarised', 'familiarized', 'completed coursework', 'sat', 'watched',
    'reviewed', 'read', 'received', 'selected', 'nominated', 'awarded', 'named', 'invited', 'trained as',
    # Adjectives and status words that end in -ed but describe a person, not an action they took.
    'experienced', 'skilled', 'qualified', 'certified', 'licensed', 'accredited', 'registered', 'motivated',
    'dedicated', 'committed', 'accomplished', 'seasoned', 'talented', 'organised', 'organized', 'detailed',
    'focused', 'advanced', 'involved', 'passionate', 'respected', 'valued', 'based', 'related', 'limited',
}


def word_stem(word):
    """Fold inflections of one word together (administering/administered/administer),
    so a fact is never flagged for using another tense of the requirement's own verb."""
    word = word.lower()
    if word in IRREGULAR:
        word = IRREGULAR[word]
    for suffix in ('ing', 'ed', 'es', 's'):
        if word.endswith(suffix) and not (suffix == 's' and word.endswith('ss')) and len(word) - len(suffix) >= 4:
            word = word[:-len(suffix)]
            break
    return word[:-1] if len(word) > 4 and word.endswith('e') else word


def close_stems(a, b):
    """Two stems name the same idea when one is a prefix-extension of the other
    (manag/management, install/installation, licenc/licens)."""
    if a == b:
        return True
    if not (a.isalpha() and b.isalpha()):
        return False  # grade-a / grade-b, level 2 / level 3 are different things
    shorter = min(len(a), len(b))
    if shorter < 5:
        return False
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return common >= max(5, int(0.8 * shorter + 0.999))


def is_action_start(text):
    """True when a bullet opens with something the person did: 'Installed …', 'I led …'.

    Weak openers (attended, observed, learned…) never count as delivery.
    """
    match = re.match(r"^\s*(?:(?:I|We)\s+)?(?:have\s+)?(?:(?:successfully|independently|personally|currently|also|regularly|safely)\s+)?([A-Za-z][A-Za-z'-]*)", text)
    if not match:
        return False
    word = match[1].lower()
    if word in WEAK_STARTS:
        return False
    return word in IRREGULAR_PAST or bool(re.fullmatch(r'[a-z]{3,}ed', word))


def sentence_start(bullet):
    """Turn a bullet into a first-person sentence only when it opens with a verb."""
    first = bullet.split(maxsplit=1)[0] if bullet.split() else ''
    if first and is_action_start(bullet) and not re.match(r'(?i)^(?:I|We)\b', bullet):
        return 'I ' + first[0].lower() + first[1:] + bullet[len(first):]
    return bullet
